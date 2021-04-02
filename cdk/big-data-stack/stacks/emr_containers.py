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
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess"),
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
        return emrc.CfnVirtualCluster(scope=self,
            id="EMRCluster",
            container_provider=emrc.CfnVirtualCluster.ContainerProviderProperty(id=self.eks_cluster.cluster_name,
                info=emrc.CfnVirtualCluster.ContainerInfoProperty(eks_info=emrc.CfnVirtualCluster.EksInfoProperty(namespace=namespace)),
                type="EKS"
            ),
            name="EMRCluster"
        )

# Helpful references
# https://github.com/aws-samples/aws-cdk-for-emr-on-eks