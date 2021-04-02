from aws_cdk import core as cdk, aws_ec2 as ec2


class VPCStack(cdk.Stack):
    vpc: ec2.Vpc

    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # We create a simple VPC here
        self.vpc = ec2.Vpc(self, "EMRDemos", max_azs=3)  # default is all AZs in region