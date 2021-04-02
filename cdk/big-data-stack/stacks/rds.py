from aws_cdk import core as cdk, aws_ec2 as ec2, aws_rds as rds


class RDSStack(cdk.Stack):
    instance: rds.DatabaseInstance

    def __init__(self, scope: cdk.Construct, construct_id: str, vpc: ec2.IVpc, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.instance = rds.DatabaseInstance(
            self,
            construct_id,
            engine=rds.DatabaseInstanceEngine.mysql(
                version=rds.MysqlEngineVersion.VER_8_0
            ),
            vpc=vpc,
            database_name="metastore",
            removal_policy=cdk.RemovalPolicy.DESTROY,
            deletion_protection=False
        )

        self.instance.connections.allow_from_any_ipv4(ec2.Port.tcp(3306), "Allow mysql from anywhere")

        # May be able to do this in EMR stack
        # .connections.security_groups[0].add_ingress_rule(
        #     peer = ec2.Peer.ipv4(vpc.vpc_cidr_block),
        #     connection = ec2.Port.tcp(80),
        #     description="Allow http inbound from VPC"
        # )
