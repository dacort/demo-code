from aws_cdk import (
    core as cdk,
    aws_eks as eks,
    aws_ec2 as ec2,
    aws_iam as iam,
)

from plugins.eks.autoscaler import ClusterAutoscaler


class EKSStack(cdk.Stack):
    cluster_name: str
    cluster: eks.Cluster

    def __init__(
        self,
        scope: cdk.Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        instance_type: str = "m5.xlarge",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.cluster_name = "data-team"

        # EKS cluster
        self.cluster = eks.Cluster(
            self,
            "EksForSpark",
            cluster_name=self.cluster_name,
            version=eks.KubernetesVersion.V1_19,
            default_capacity=0,
            endpoint_access=eks.EndpointAccess.PUBLIC_AND_PRIVATE,
            vpc=vpc,
            vpc_subnets=[ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE)],
        )

        # Default node group
        ng = self.cluster.add_nodegroup_capacity(
            "base-node-group",
            instance_types=[ec2.InstanceType(instance_type)],
            min_size=1,
            max_size=20,
            disk_size=50,
            # tags={
            #     f'k8s.io/cluster-autoscaler/{cluster_name}': "owned",
            #     'k8s.io/cluster-autoscaler/enabled': 'TRUE'
            # }
        )

        self.add_admin_role_to_cluster()
        # self.enable_autoscaling(ng)
        self.enable_dashboard()

        # Cluster AutoScaling FTW
        ClusterAutoscaler(self.cluster_name, self, self.cluster, ng).enable_autoscaling()

        # This is emr-specific, but we have to do it here to prevent circular dependencies
        self.map_iam_to_eks()

    def add_admin_role_to_cluster(self) -> None:
        admin_role_name = self.node.try_get_context("eks_admin_role_name")
        if admin_role_name is None:
            return

        account_id = cdk.Aws.ACCOUNT_ID
        admin_role = iam.Role.from_role_arn(
            self, "admin_role", f"arn:aws:iam::{account_id}:role/{admin_role_name}"
        )
        self.cluster.aws_auth.add_masters_role(admin_role)

    def enable_autoscaling(self, node_group: eks.Nodegroup) -> None:
        # First we need to create a policy to handle the autoscaling
        policy = self.autoscaling_policy()
        # policy.attach_to_role(node_group.role)
        role = self.autoscaler_role(policy)

        # Then we need to map the IAM role to a service account
        sa = self.cluster.add_service_account(
            "cluster-autoscaler", name="cluster-autoscaler", namespace="kube-system"
        )
        sa.add_to_principal_policy(
            iam.PolicyStatement(
                actions=[
                    "autoscaling:DescribeAutoScalingGroups",
                    "autoscaling:DescribeAutoScalingInstances",
                    "autoscaling:DescribeLaunchConfigurations",
                    "autoscaling:DescribeTags",
                    "autoscaling:SetDesiredCapacity",
                    "autoscaling:TerminateInstanceInAutoScalingGroup",
                ],
                resources=["*"],
            )
        )

        cdk.Tag.add(
            node_group,
            f"k8s.io/cluster-autoscaler/{self.cluster_name}",
            "owned",
            apply_to_launched_instances=True,
        )
        cdk.Tag.add(
            node_group,
            "k8s.io/cluster-autoscaler/enabled",
            "true",
            apply_to_launched_instances=True,
        )
        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "cluster-autoscaler",
                "namespace": "kube-system",
                "labels": {"app": "cluster-autoscaler"},
            },
            "spec": {
                "replicas": 1,
                "selector": {"matchLabels": {"app": "cluster-autoscaler"}},
                "template": {
                    "metadata": {"labels": {"app": "cluster-autoscaler"}},
                    "spec": {
                        "serviceAccountName": "cluster-autoscaler",
                        "containers": [
                            {
                                "image": "us.gcr.io/k8s-artifacts-prod/autoscaling/cluster-autoscaler:v1.19.1",
                                "name": "cluster-autoscaler",
                                "resources": {
                                    "limits": {"cpu": "100m", "memory": "300Mi"},
                                    "requests": {"cpu": "100m", "memory": "300Mi"},
                                },
                                "command": [
                                    "./cluster-autoscaler",
                                    "--v=4",
                                    "--stderrthreshold=info",
                                    "--cloud-provider=aws",
                                    "--balance-similar-node-groups=true",
                                    "--skip-nodes-with-local-storage=false",
                                    "--skip-nodes-with-system-pods=false",
                                    "--ignore-daemonsets-utilization=true",
                                    "--expander=random",
                                    "--node-group-auto-discovery=asg:tag=k8s.io/cluster-autoscaler/enabled,k8s.io/cluster-autoscaler/data-team",
                                ],
                                "env": [{"name": "AWS_REGION", "value": "us-east-1"}],
                                "volumeMounts": [
                                    {
                                        "name": "ssl-certs",
                                        "mountPath": "/etc/ssl/certs/ca-certificates.crt",
                                        "readOnly": True,
                                    }
                                ],
                                "imagePullPolicy": "Always",
                            }
                        ],
                        "volumes": [
                            {
                                "name": "ssl-certs",
                                "hostPath": {"path": "/etc/ssl/certs/ca-bundle.crt"},
                            }
                        ],
                        "affinity": {
                            "nodeAffinity": {
                                "requiredDuringSchedulingIgnoredDuringExecution": {
                                    "nodeSelectorTerms": [
                                        {
                                            "matchExpressions": [
                                                {
                                                    "key": "node.kubernetes.io/instance-type",
                                                    "operator": "In",
                                                    "values": [
                                                        "m5.xlarge",
                                                    ],
                                                }
                                            ]
                                        }
                                    ]
                                }
                            }
                        },
                    },
                },
            },
        }
        self.cluster.add_manifest('cluster-autoscaler', deployment)
        # self.cluster.add_helm_chart(
        #     "cluster-autoscaler",
        #     chart="cluster-autoscaler",
        #     repository="https://kubernetes.github.io/autoscaler",
        #     values={
        #         "autoDiscovery.clusterName": self.cluster_name,
        #         'rbac.serviceAccount.annotations."eks.amazonaws.com/role-arn"': role.role_arn,
        #     },
        #     namespace="kube-system",
        # )

    def autoscaling_policy(self) -> iam.Policy:
        policy_statement = iam.PolicyStatement(
            actions=[
                "autoscaling:DescribeAutoScalingGroups",
                "autoscaling:DescribeAutoScalingInstances",
                "autoscaling:DescribeLaunchConfigurations",
                "autoscaling:DescribeTags",
                "autoscaling:SetDesiredCapacity",
                "autoscaling:TerminateInstanceInAutoScalingGroup",
            ],
            resources=["*"],
        )
        return iam.Policy(
            self,
            "cluster-autoscaler-policy",
            statements=[policy_statement],
            policy_name="cluster-autoscaler-policy",
        )

    def autoscaler_role(self, policy: iam.Policy) -> iam.Role:
        oidc_arn = cdk.CfnJson(
            self,
            "oidc-provider",
            value=self.cluster.open_id_connect_provider.open_id_connect_provider_arn,
        )

        oidc_arn_condition = cdk.CfnJson(
            self,
            "oidc-provider-condition",
            value={
                f"{self.cluster.open_id_connect_provider.open_id_connect_provider_issuer}:sub": "system:serviceaccount:kube-system:cluster-autoscaler"
            },
        )
        role = iam.Role(
            self,
            "ClusterAutoscalerRole",
            assumed_by=iam.FederatedPrincipal(
                oidc_arn.value.to_string(),
                {"StringEquals": oidc_arn_condition},
                "sts:AssumeRoleWithWebIdentity",
            ),
        )
        role.attach_inline_policy(policy)
        return role

    def enable_dashboard(self):
        self.cluster.add_helm_chart(
            "kubernetes-dashboard",
            namespace='kube-system',
            chart="kubernetes-dashboard",
            repository="https://kubernetes.github.io/dashboard/",
        )

    def map_iam_to_eks(self):
        service_role_name = f"arn:aws:iam::{cdk.Aws.ACCOUNT_ID}:role/AWSServiceRoleForAmazonEMRContainers"
        emrsvcrole = iam.Role.from_role_arn(
            self, "EmrSvcRole", service_role_name, mutable=False
        )
        self.cluster.aws_auth.add_role_mapping(
            emrsvcrole, groups=[], username="emr-containers"
        )

# Helpful references
# https://betterprogramming.pub/how-to-organize-your-aws-cdk-project-f1c463aa966e
# https://github.com/aftouh/cdk-template
# 
# https://faun.pub/spawning-an-autoscaling-eks-cluster-52977aa8b467