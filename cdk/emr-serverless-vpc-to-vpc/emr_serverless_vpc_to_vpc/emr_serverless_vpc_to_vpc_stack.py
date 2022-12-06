from aws_cdk import Stack
from aws_cdk import aws_ec2 as ec2  # Duration,
from aws_cdk import aws_emrserverless as emrs
from aws_cdk import aws_iam as iam
from constructs import Construct


class EmrServerlessVpcToVpcStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create two VPCs, ensure their CIDRs don't overlap
        vpc1 = ec2.Vpc(self, "EMRServerless_VPC1", max_azs=3, cidr="10.0.0.0/16")
        vpc2 = ec2.Vpc(self, "EMRServerless_VPC2", max_azs=3, cidr="10.1.0.0/16")

        # This is necessary on Ubuntu instances to install cfn-init and cfn-signal
        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            "apt-get update -y",
            "apt-get install -y -o DPkg::Lock::Timeout=60 git python3-pip",
            "python3 -m pip install -U pip",
            "python3 -m pip install https://s3.amazonaws.com/cloudformation-examples/aws-cfn-bootstrap-py3-latest.tar.gz",
            "mkdir -p /opt/aws/bin/",
            "ln -s /usr/local/bin/cfn-* /opt/aws/bin/",
        )

        # Create a an EC2 instance running postgres in VPC1 and an inbound security group
        svc_sg = ec2.SecurityGroup(self, "VPC1_Service", vpc=vpc1)
        instance = ec2.Instance(
            self,
            "pg",
            vpc=vpc1,
            instance_type=ec2.InstanceType("t2.micro"),
            machine_image=ec2.MachineImage.lookup(
                name="ubuntu/images/hvm-ssd/ubuntu-focal-20.04-amd64-server-20211129"
            ),
            security_group=svc_sg,
            init=ec2.CloudFormationInit.from_elements(
                ec2.InitCommand.shell_command(
                    "sudo apt-get install -o DPkg::Lock::Timeout=60 -y postgresql"
                ),
                ec2.InitCommand.shell_command(
                    "sudo sh -c 'echo listen_addresses = '*' >> /etc/postgresql/12/main/postgresql.conf'"
                ),
                ec2.InitCommand.shell_command(
                    "sudo sh -c 'echo host  all  all 0.0.0.0/0 md5 >> /etc/postgresql/12/main/postgresql.conf'"
                ),
                ec2.InitCommand.shell_command(
                    "sudo systemctl restart postgresql.service"
                ),
                ec2.InitCommand.shell_command(
                    "sudo -u postgres psql -c \"CREATE USER remote WITH PASSWORD 'remote';\""
                ),
            ),
            user_data=user_data,
        )

        # Add SSM policy so we can remote in without SSH
        instance.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AmazonSSMManagedInstanceCore"
            )
        )

        # Create a test EC2 instance in VPC2 with the same security group as our EMR Serverless application
        # We can use this to validate connectivity
        test_sg = ec2.SecurityGroup(self, "VPC2_Service", vpc=vpc2)
        instance2 = ec2.Instance(
            self,
            "test",
            vpc=vpc2,
            instance_type=ec2.InstanceType("t2.micro"),
            machine_image=ec2.MachineImage.lookup(
                name="ubuntu/images/hvm-ssd/ubuntu-focal-20.04-amd64-server-20211129"
            ),
            security_group=test_sg,
            init=ec2.CloudFormationInit.from_elements(
                ec2.InitCommand.shell_command(
                    "sudo apt-get install -o DPkg::Lock::Timeout=60 -y netcat"
                ),
            ),
            user_data=user_data,
        )
        instance2.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AmazonSSMManagedInstanceCore"
            )
        )

        # Peer the two VPCs
        fn_vPCPeering_connection = ec2.CfnVPCPeeringConnection(
            self,
            "MyCfnVPCPeeringConnection",
            peer_vpc_id=vpc1.vpc_id,
            vpc_id=vpc2.vpc_id,
        )

        # Then create routes between eachof the subnets in each VPC
        for idx, subnet in enumerate(vpc2.private_subnets):
            ec2.CfnRoute(
                self,
                f"PeerRoute-{idx}",
                route_table_id=subnet.route_table.route_table_id,
                destination_cidr_block=vpc1.vpc_cidr_block,
                vpc_peering_connection_id=fn_vPCPeering_connection.ref,
            )

        for idx, subnet in enumerate(vpc1.private_subnets):
            ec2.CfnRoute(
                self,
                f"PeerRoute-2-{idx}",
                route_table_id=subnet.route_table.route_table_id,
                destination_cidr_block=vpc2.vpc_cidr_block,
                vpc_peering_connection_id=fn_vPCPeering_connection.ref,
            )

        # Allow postgres from vpc2 to vpc1
        svc_sg.add_ingress_rule(
            peer=test_sg,
            connection=ec2.Port.tcp(5432),
            description="Allow Postgres from VPC2",
        )

        # Finally create an EMR Serverless app to test this on with the appropriate subnets and security group
        emrs.CfnApplication(
            self,
            "spark_app",
            release_label="emr-6.9.0",
            type="SPARK",
            name="cdk-spark",
            network_configuration=emrs.CfnApplication.NetworkConfigurationProperty(
                subnet_ids=vpc2.select_subnets().subnet_ids,
                security_group_ids=[test_sg.security_group_id],
            ),
        )
