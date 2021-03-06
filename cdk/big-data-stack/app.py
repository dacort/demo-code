#!/usr/bin/env python3
import os
from stacks.emr_studio import EMRStudio
from stacks.emr_containers import EMRContainersStack

from aws_cdk import core as cdk

from stacks.vpc import VPCStack
from stacks.rds import RDSStack
from stacks.emr import EMRStack
from stacks.eks import EKSStack
from stacks.emr_containers import EMRContainersStack


app = cdk.App()

vpc = VPCStack(app, "VPCStack")

# These two stacks are disabled by default
# I use them when to demo EMR with a MySQL-backed Hive metastore
# rds = RDSStack(app, "RDSStack", vpc.vpc)
# emr = EMRStack(
#     app,
#     "EMRStack",
#     vpc.vpc,
#     name="EMR with Hive Metastore",
#     release_label="emr-5.32.0",
#     rds_secret=rds.instance.secret,
#     rds_connections=rds.instance.connections,
# )

# The EKS stack requires bootstrapping
# Run "cdk bootstrap aws://account/region"
# You can also optionally specify an IAM role name to be mapped to a cluster admin
# `-c eks_admin_role_name=AdminRole`
eks = EKSStack(app, "EKSStack", vpc.vpc)

# Now add a virtual EMR cluster!
emr_containers = EMRContainersStack(app, "EMRContainers", vpc.vpc, eks.cluster)


# We want to add EMR Studio to the mix as well :)
emr_studio = EMRStudio(app, "EMRStudio", vpc.vpc, "big-data-studio")


app.synth()
