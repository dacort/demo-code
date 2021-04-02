from aws_cdk import (
    core as cdk,
    aws_emr as emr,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_secretsmanager as secrets,
)

from stacks.utils import get_or_create_bucket


class EMRStack(cdk.Stack):
    cluster: emr.CfnCluster

    def __init__(
        self,
        scope: cdk.Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        name: str,
        release_label: str,
        rds_secret: secrets.Secret,
        rds_connections: ec2.Connections,
        log_bucket_name: str = None,
        ssh_key_name: str = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.tag_vpc(vpc)

        job_role = self.get_job_role()
        service_role = self.get_service_role()
        instance_profile = self.create_instance_profile(job_role)
        log_bucket = get_or_create_bucket(self, "emr_logs", log_bucket_name)

        # Assign necessary permissions
        # EMR needs to be able to PutObject to the log bucket
        log_bucket.grant_put(job_role)

        # EMR needs to be able to PassRole to the instance profile role
        # https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-iam-role-for-ec2.html#emr-ec2-role-least-privilege
        # https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-iam-role.html
        service_role.add_to_policy(
            iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=[job_role.role_arn],
                conditions={
                    "StringEquals": {"iam:PassedToService": "ec2.amazonaws.com"}
                },
            )
        )

        # Database configuration variables
        rds_hostname = rds_secret.secret_value_from_json("host").to_string()
        rds_port = rds_secret.secret_value_from_json("port").to_string()
        rds_dbname = rds_secret.secret_value_from_json("dbname").to_string()

        # Desired subnet for the EMR cluster
        emr_subnet = vpc.public_subnets[0]

        self.cluster = emr.CfnCluster(
            self,
            construct_id,
            instances=emr.CfnCluster.JobFlowInstancesConfigProperty(
                master_instance_group=emr.CfnCluster.InstanceGroupConfigProperty(
                    instance_count=1, instance_type="m5.xlarge"
                ),
                core_instance_group=emr.CfnCluster.InstanceGroupConfigProperty(
                    instance_count=2, instance_type="m5.xlarge"
                ),
                ec2_subnet_id=emr_subnet.subnet_id,
            ),
            name=name,
            release_label=release_label,
            log_uri=f"s3://{log_bucket.bucket_name}/elasticmapreduce/",
            job_flow_role=job_role.role_name,
            service_role=service_role.role_name,
            applications=[
                emr.CfnCluster.ApplicationProperty(name=n)
                for n in [
                    "Spark",
                    "Hive",
                    "Zeppelin",
                    "Livy",
                    "JupyterEnterpriseGateway",
                ]
            ],
            visible_to_all_users=True, # Required for EMR Notebooks
            configurations=[
                emr.CfnCluster.ConfigurationProperty(
                    classification="hive-site",
                    configuration_properties={
                        "javax.jdo.option.ConnectionURL": f"jdbc:mysql://{rds_hostname}:{rds_port}/{rds_dbname}?createDatabaseIfNotExist=true",
                        "javax.jdo.option.ConnectionDriverName": "org.mariadb.jdbc.Driver",
                        "javax.jdo.option.ConnectionUserName": rds_secret.secret_value_from_json(
                            "username"
                        ).to_string(),
                        "javax.jdo.option.ConnectionPassword": rds_secret.secret_value_from_json(
                            "password"
                        ).to_string(),
                    },
                ),
            ],
            tags=[
                cdk.CfnTag(
                    key="for-use-with-amazon-emr-managed-policies", value="true"
                ),
            ],
        )

        # Wait for the instance profile to be created
        self.cluster.add_depends_on(instance_profile)

        # Allow EMR to connect to the RDS database
        self.add_rds_ingres(emr_subnet.ipv4_cidr_block, rds_connections)

    def tag_vpc(
        self,
        vpc: ec2.IVpc,
    ) -> None:
        # The VPC requires a Tag to allow EMR to create the relevant security groups
        cdk.Tags.of(vpc).add("for-use-with-amazon-emr-managed-policies", "true")

    def add_rds_ingres(self, subnet, conn: ec2.Connections) -> None:
        conn.security_groups[0].add_ingress_rule(
            peer=ec2.Peer.ipv4(subnet),
            connection=ec2.Port.tcp(3306),
            description="EMR MySQL Access",
        )

    def get_service_role(self) -> iam.Role:
        return iam.Role(
            self,
            "emr_service_role",
            assumed_by=iam.ServicePrincipal("elasticmapreduce.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonEMRServicePolicy_v2"
                )
            ],
        )

    def get_job_role(self) -> iam.Role:
        """
        Create a new EC2 instance profile role for EMR instances.
        This role allows full read-only access to S3.
        """
        return iam.Role(
            self,
            "EMRJobRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonS3ReadOnlyAccess"
                )
            ]
        )

    def create_instance_profile(self, job_role: iam.Role) -> iam.CfnInstanceProfile:
        return iam.CfnInstanceProfile(
            self,
            "emr_instance_profile",
            instance_profile_name=job_role.role_name,
            roles=[job_role.role_name],
        )

    def log_writer_policy(self, bucket: str) -> iam.PolicyStatement:
        return iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["s3:PutObject"],
            resources=[f"arn:aws:s3:::{bucket}/*"],
        )