from aws_cdk import (
    core as cdk,
    aws_emrcontainers as emrc,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_eks as eks,
)


class EMRContainersStack(cdk.Stack):
    virtual_cluster: emrc.CfnVirtualCluster
    eks_cluster: eks.Cluster

    def __init__(
        self,
        scope: cdk.Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        eks_cluster: eks.Cluster,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The EKS cluster is used throughout, so we add it here
        self.eks_cluster = eks_cluster

        # EMR requires several modifications to the EKS cluster to allow containers to run
        self.configure_eks(eks_cluster, "emr-jobs")

    def configure_eks(self, eks: eks.Cluster, namespace: str):
        # First we create a namespace for EMR to use
        ns = self.create_namespace(namespace)

        # Then we create a k8s cluster role for EMR
        role = self.create_cluster_role(namespace)
        role.node.add_dependency(ns)

        # Now bind the cluster role to the "emr-containers" user
        bind = self.bind_role_to_user(namespace)
        bind.node.add_dependency(role)

        # Create a (nicely-named) job execution role
        self.create_job_execution_role("emr_eks_default_role", namespace)

        # Finally we create our cluster!
        self.virtual_cluster = self.create_virtual_cluster(namespace)
        self.virtual_cluster.node.add_dependency(ns)
        self.virtual_cluster.node.add_dependency(bind)

        # Let's try to create a managed endpoint
        self.create_managed_endpoint()

    def create_namespace(self, name: str) -> eks.KubernetesManifest:
        return self.eks_cluster.add_manifest(
            name,
            {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {"name": name},
            },
        )

    def create_cluster_role(self, namespace: str) -> eks.KubernetesManifest:
        # fmt: off
        return self.eks_cluster.add_manifest(
            "emrrole",
            {
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "Role",
                "metadata": {"name": "emr-containers", "namespace": namespace},
                "rules": [
                    {"apiGroups": [""], "resources": ["namespaces"], "verbs": ["get"]},
                    {
                        "apiGroups": [""],
                        "resources": [ "serviceaccounts", "services", "configmaps", "events", "pods", "pods/log", ],
                        "verbs": [ "get", "list", "watch", "describe", "create", "edit", "delete", "deletecollection", "annotate", "patch", "label", ],
                    },
                    {
                        "apiGroups": [""],
                        "resources": ["secrets"],
                        "verbs": ["create", "patch", "delete", "watch"],
                    },
                    {
                        "apiGroups": ["apps"],
                        "resources": ["statefulsets", "deployments"],
                        "verbs": [ "get", "list", "watch", "describe", "create", "edit", "delete", "annotate", "patch", "label", ],
                    },
                    {
                        "apiGroups": ["batch"],
                        "resources": ["jobs"],
                        "verbs": [ "get", "list", "watch", "describe", "create", "edit", "delete", "annotate", "patch", "label", ],
                    },
                    {
                        "apiGroups": ["extensions"],
                        "resources": ["ingresses"],
                        "verbs": [ "get", "list", "watch", "describe", "create", "edit", "delete", "annotate", "patch", "label", ],
                    },
                    {
                        "apiGroups": ["rbac.authorization.k8s.io"],
                        "resources": ["roles", "rolebindings"],
                        "verbs": [ "get", "list", "watch", "describe", "create", "edit", "delete", "deletecollection", "annotate", "patch", "label", ],
                    },
                ],
            },
        )
        # fmt: on

    def bind_role_to_user(self, namespace: str) -> eks.KubernetesManifest:
        return self.eks_cluster.add_manifest(
            "emrrolebind",
            {
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "RoleBinding",
                "metadata": {"name": "emr-containers", "namespace": namespace},
                "subjects": [
                    {
                        "kind": "User",
                        "name": "emr-containers",
                        "apiGroup": "rbac.authorization.k8s.io",
                    }
                ],
                "roleRef": {
                    "kind": "Role",
                    "name": "emr-containers",
                    "apiGroup": "rbac.authorization.k8s.io",
                },
            },
        )

    def create_job_execution_role(self, role_name: str, namespace: str) -> None:
        job_role = iam.Role(
            self,
            "EMR_EKS_Job_Role",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonS3FullAccess"
                ),  # Yes, yes...I know. :)
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2FullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AWSGlueConsoleFullAccess"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchFullAccess"),
            ],
            role_name=role_name,
        )
        cdk.CfnOutput(self, "JobRoleArn", value=job_role.role_arn)

        # Modify trust policy
        string_like = cdk.CfnJson(
            self,
            "ConditionJson",
            value={
                f"{self.eks_cluster.cluster_open_id_connect_issuer}:sub": f"system:serviceaccount:{namespace}:emr-containers-sa-*-*-{cdk.Aws.ACCOUNT_ID}-*"
            },
        )
        job_role.assume_role_policy.add_statements(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["sts:AssumeRoleWithWebIdentity"],
                principals=[
                    iam.OpenIdConnectPrincipal(
                        self.eks_cluster.open_id_connect_provider,
                        conditions={"StringLike": string_like},
                    )
                ],
            )
        )
        string_aud = cdk.CfnJson(
            self,
            "ConditionJsonAud",
            value={
                f"{self.eks_cluster.cluster_open_id_connect_issuer}:aud": "sts.amazon.com"
            },
        )
        job_role.assume_role_policy.add_statements(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["sts:AssumeRoleWithWebIdentity"],
                principals=[
                    iam.OpenIdConnectPrincipal(
                        self.eks_cluster.open_id_connect_provider,
                        conditions={"StringEquals": string_aud},
                    )
                ],
            )
        )

    def create_virtual_cluster(self, namespace: str) -> None:
        return emrc.CfnVirtualCluster(
            scope=self,
            id="EMRCluster",
            container_provider=emrc.CfnVirtualCluster.ContainerProviderProperty(
                id=self.eks_cluster.cluster_name,
                info=emrc.CfnVirtualCluster.ContainerInfoProperty(
                    eks_info=emrc.CfnVirtualCluster.EksInfoProperty(namespace=namespace)
                ),
                type="EKS",
            ),
            name="EMRCluster",
        )

    def create_managed_endpoint(self) -> None:
        sa = self.eks_cluster.add_service_account(
            "studio-aws-load-balancer-controller",
            name="studio-aws-load-balancer-controller",
            namespace="kube-system",
        )
        sa.add_to_principal_policy(
            iam.PolicyStatement(
                actions=[
                    "iam:CreateServiceLinkedRole",
                    "ec2:DescribeAccountAttributes",
                    "ec2:DescribeAddresses",
                    "ec2:DescribeInternetGateways",
                    "ec2:DescribeVpcs",
                    "ec2:DescribeSubnets",
                    "ec2:DescribeSecurityGroups",
                    "ec2:DescribeInstances",
                    "ec2:DescribeNetworkInterfaces",
                    "ec2:DescribeTags",
                    "elasticloadbalancing:DescribeLoadBalancers",
                    "elasticloadbalancing:DescribeLoadBalancerAttributes",
                    "elasticloadbalancing:DescribeListeners",
                    "elasticloadbalancing:DescribeListenerCertificates",
                    "elasticloadbalancing:DescribeSSLPolicies",
                    "elasticloadbalancing:DescribeRules",
                    "elasticloadbalancing:DescribeTargetGroups",
                    "elasticloadbalancing:DescribeTargetGroupAttributes",
                    "elasticloadbalancing:DescribeTargetHealth",
                    "elasticloadbalancing:DescribeTags",
                ],
                resources=["*"],
            )
        )
        sa.add_to_principal_policy(
            iam.PolicyStatement(
                actions=[
                    "cognito-idp:DescribeUserPoolClient",
                    "acm:ListCertificates",
                    "acm:DescribeCertificate",
                    "iam:ListServerCertificates",
                    "iam:GetServerCertificate",
                    "waf-regional:GetWebACL",
                    "waf-regional:GetWebACLForResource",
                    "waf-regional:AssociateWebACL",
                    "waf-regional:DisassociateWebACL",
                    "wafv2:GetWebACL",
                    "wafv2:GetWebACLForResource",
                    "wafv2:AssociateWebACL",
                    "wafv2:DisassociateWebACL",
                    "shield:GetSubscriptionState",
                    "shield:DescribeProtection",
                    "shield:CreateProtection",
                    "shield:DeleteProtection",
                ],
                resources=["*"],
            )
        )
        sa.add_to_principal_policy(
            iam.PolicyStatement(
                actions=[
                    "ec2:AuthorizeSecurityGroupIngress",
                    "ec2:RevokeSecurityGroupIngress",
                    "ec2:CreateSecurityGroup",
                ],
                resources=["*"],
            )
        )
        sa.add_to_principal_policy(
            iam.PolicyStatement(
                actions=["ec2:CreateTags"],
                resources=["arn:aws:ec2:*:*:security-group/*"],
                conditions={
                    "StringEquals": {"ec2:CreateAction": "CreateSecurityGroup"},
                    "Null": {"aws:RequestTag/elbv2.k8s.aws/cluster": "false"},
                },
            )
        )
        sa.add_to_principal_policy(
            iam.PolicyStatement(
                actions=["ec2:CreateTags", "ec2:DeleteTags"],
                resources=["arn:aws:ec2:*:*:security-group/*"],
                conditions={
                    "Null": {
                        "aws:RequestTag/elbv2.k8s.aws/cluster": "true",
                        "aws:ResourceTag/elbv2.k8s.aws/cluster": "false",
                    }
                },
            )
        )
        sa.add_to_principal_policy(
            iam.PolicyStatement(
                actions=[
                    "ec2:AuthorizeSecurityGroupIngress",
                    "ec2:RevokeSecurityGroupIngress",
                    "ec2:DeleteSecurityGroup",
                ],
                resources=["*"],
                conditions={"Null": {"aws:ResourceTag/elbv2.k8s.aws/cluster": "false"}},
            )
        )
        sa.add_to_principal_policy(
            iam.PolicyStatement(
                actions=[
                    "elasticloadbalancing:CreateLoadBalancer",
                    "elasticloadbalancing:CreateTargetGroup",
                ],
                resources=["*"],
                conditions={"Null": {"aws:RequestTag/elbv2.k8s.aws/cluster": "false"}},
            )
        )
        sa.add_to_principal_policy(
            iam.PolicyStatement(
                actions=[
                    "elasticloadbalancing:CreateListener",
                    "elasticloadbalancing:DeleteListener",
                    "elasticloadbalancing:CreateRule",
                    "elasticloadbalancing:DeleteRule",
                ],
                resources=["*"],
            )
        )
        sa.add_to_principal_policy(
            iam.PolicyStatement(
                actions=[
                    "elasticloadbalancing:AddTags",
                    "elasticloadbalancing:RemoveTags",
                ],
                resources=[
                    "arn:aws:elasticloadbalancing:*:*:targetgroup/*/*",
                    "arn:aws:elasticloadbalancing:*:*:loadbalancer/net/*/*",
                    "arn:aws:elasticloadbalancing:*:*:loadbalancer/app/*/*",
                ],
                conditions={
                    "Null": {
                        "aws:RequestTag/elbv2.k8s.aws/cluster": "true",
                        "aws:ResourceTag/elbv2.k8s.aws/cluster": "false",
                    }
                },
            )
        )
        sa.add_to_principal_policy(
            iam.PolicyStatement(
                actions=[
                    "elasticloadbalancing:ModifyLoadBalancerAttributes",
                    "elasticloadbalancing:SetIpAddressType",
                    "elasticloadbalancing:SetSecurityGroups",
                    "elasticloadbalancing:SetSubnets",
                    "elasticloadbalancing:DeleteLoadBalancer",
                    "elasticloadbalancing:ModifyTargetGroup",
                    "elasticloadbalancing:ModifyTargetGroupAttributes",
                    "elasticloadbalancing:DeleteTargetGroup",
                ],
                resources=["*"],
                conditions={"Null": {"aws:ResourceTag/elbv2.k8s.aws/cluster": "false"}},
            )
        )
        sa.add_to_principal_policy(
            iam.PolicyStatement(
                actions=[
                    "elasticloadbalancing:RegisterTargets",
                    "elasticloadbalancing:DeregisterTargets",
                ],
                resources=["arn:aws:elasticloadbalancing:*:*:targetgroup/*/*"],
            )
        )
        sa.add_to_principal_policy(
            iam.PolicyStatement(
                actions=[
                    "elasticloadbalancing:SetWebAcl",
                    "elasticloadbalancing:ModifyListener",
                    "elasticloadbalancing:AddListenerCertificates",
                    "elasticloadbalancing:RemoveListenerCertificates",
                    "elasticloadbalancing:ModifyRule",
                ],
                resources=["*"],
            )
        )

        chart = self.eks_cluster.add_helm_chart(
            "alb",
            namespace="kube-system",
            chart="aws-load-balancer-controller",
            repository="https://aws.github.io/eks-charts",
            values={
                "clusterName": self.eks_cluster.cluster_name,
                "serviceAccount": {"create": False, "name": "studio-aws-load-balancer-controller"}
            }
        )



# Helpful references
# https://github.com/aws-samples/aws-cdk-for-emr-on-eks