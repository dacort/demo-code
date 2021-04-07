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
        )

        self.add_admin_role_to_cluster()
        self.enable_dashboard()
        self.enable_airflow()

        # Cluster AutoScaling FTW
        ClusterAutoscaler(
            self.cluster_name, self, self.cluster, ng
        ).enable_autoscaling()

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

    def enable_dashboard(self, namespace: str = "kube-system"):
        self.cluster.add_helm_chart(
            "kubernetes-dashboard",
            namespace=namespace,
            chart="kubernetes-dashboard",
            repository="https://kubernetes.github.io/dashboard/",
            values={
                "fullnameOverride": "kubernetes-dashboard",  # This must be set to acccess the UI via `kubectl proxy`
                "extraArgs": ["--token-ttl=0"],
            },
        )
        self.cluster.add_manifest(
            "eks-admin-sa",
            {
                "apiVersion": "v1",
                "kind": "ServiceAccount",
                "metadata": {
                    "name": "eks-admin",
                    "namespace": namespace,
                },
            },
        )
        self.cluster.add_manifest(
            "eks-admin-rbac",
            {
                "apiVersion": "rbac.authorization.k8s.io/v1beta1",
                "kind": "ClusterRoleBinding",
                "metadata": {"name": "eks-admin"},
                "roleRef": {
                    "apiGroup": "rbac.authorization.k8s.io",
                    "kind": "ClusterRole",
                    "name": "cluster-admin",
                },
                "subjects": [
                    {
                        "kind": "ServiceAccount",
                        "name": "eks-admin",
                        "namespace": namespace,
                    }
                ],
            },
        )

    def map_iam_to_eks(self):
        service_role_name = f"arn:aws:iam::{cdk.Aws.ACCOUNT_ID}:role/AWSServiceRoleForAmazonEMRContainers"
        emrsvcrole = iam.Role.from_role_arn(
            self, "EmrSvcRole", service_role_name, mutable=False
        )
        self.cluster.aws_auth.add_role_mapping(
            emrsvcrole, groups=[], username="emr-containers"
        )

    def enable_airflow(self, namespace: str = "airflow"):
        volume = self.cluster.add_manifest("multiaz-volume", self.gp2_multiazvolume())
        chart = self.cluster.add_helm_chart(
            "airflow",
            namespace=namespace,
            chart="airflow",
            repository="https://airflow-helm.github.io/charts",
            version="8.0.5",
            values={
                "airflow": {
                    "executor": "KubernetesExecutor",
                    "image": {
                        "repository": "ghcr.io/dacort/airflow-emr-eks",
                        "tag": "latest",
                        "pullPolicy": "Always",
                    },
                    "extraEnv": [
                        {
                            "name": "AIRFLOW__CORE__FERNET_KEY",
                            "valueFrom": {
                                "secretKeyRef": {
                                    "name": "airflow-fernet-key",
                                    "key": "value",
                                }
                            },
                        }
                    ],
                },
                "web": {"resources": {"limits": {"cpu": "1", "memory": "1Gi"}}},
                "workers": {"enabled": False},
                "flower": {"enabled": False},
                "redis": {"enabled": False},
                "dags": {
                    "gitSync": {
                        "enabled": True,
                        "repo": "https://github.com/dacort/airflow-example-dags.git",
                        "branch": "main",
                        "resources": {"requests": {"cpu": "50m", "memory": "64Mi"}},
                    }
                },
                "postgresql": {"persistence": {"storageClass": "multiazvolume"}},
            },
        )
        chart.node.add_dependency(volume)

        # Display the command necessarty to port-forward the Airflow Web UI
        airflow_forward_cmd = f'kubectl port-forward --namespace {namespace} $(kubectl get pods --namespace {namespace} -l "component=web,app=airflow" -o jsonpath="{{.items[0].metadata.name}}") 8080:8080'
        cdk.CfnOutput(self, "AirflowLoginCommand", value=airflow_forward_cmd)

    def gp2_multiazvolume(self):
        return {
            "kind": "StorageClass",
            "apiVersion": "storage.k8s.io/v1",
            "metadata": {"name": "multiazvolume"},
            "provisioner": "kubernetes.io/aws-ebs",
            "parameters": {"type": "gp2", "iopsPerGB": "10", "fsType": "ext4"},
            "volumeBindingMode": "WaitForFirstConsumer",
        }


# Helpful references
# https://betterprogramming.pub/how-to-organize-your-aws-cdk-project-f1c463aa966e
# https://github.com/aftouh/cdk-template
#
# https://faun.pub/spawning-an-autoscaling-eks-cluster-52977aa8b467