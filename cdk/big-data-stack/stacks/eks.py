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

        # Add a Spot node group as well for additional capacity
        spot_ng = self.cluster.add_nodegroup_capacity(
            "spot-node-group",
            capacity_type=eks.CapacityType.SPOT,
            instance_types=[ec2.InstanceType(it) for it in ['c4.2xlarge', 'c5.2xlarge', 'c5d.2xlarge', 'c5a.2xlarge', 'c5n.2xlarge']],
            min_size=1,
            max_size=20,
        )

        self.add_admin_role_to_cluster()
        self.add_cluster_admin()

        # Cluster AutoScaling FTW
        ClusterAutoscaler(
            self.cluster_name, self, self.cluster, [ng, spot_ng]
        ).enable_autoscaling()

        # We like to use the Kubernetes Dashboard
        self.enable_dashboard()

        # Install Airflow as well
        # TODO: Make this optional
        # self.enable_airflow()

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

    def add_cluster_admin(self, name="eks-admin"):
        # Add admin privileges so we can sign in to the dashboard as the service account
        sa = self.cluster.add_manifest(
            "eks-admin-sa",
            {
                "apiVersion": "v1",
                "kind": "ServiceAccount",
                "metadata": {
                    "name": name,
                    "namespace": "kube-system",
                },
            },
        )
        binding = self.cluster.add_manifest(
            "eks-admin-rbac",
            {
                "apiVersion": "rbac.authorization.k8s.io/v1beta1",
                "kind": "ClusterRoleBinding",
                "metadata": {"name": name},
                "roleRef": {
                    "apiGroup": "rbac.authorization.k8s.io",
                    "kind": "ClusterRole",
                    "name": "cluster-admin",
                },
                "subjects": [
                    {
                        "kind": "ServiceAccount",
                        "name": name,
                        "namespace": "kube-system",
                    }
                ],
            },
        )

    def enable_dashboard(self, namespace: str = "kubernetes-dashboard"):
        chart = self.cluster.add_helm_chart(
            "kubernetes-dashboard",
            namespace=namespace,
            chart="kubernetes-dashboard",
            repository="https://kubernetes.github.io/dashboard/",
            values={
                "fullnameOverride": "kubernetes-dashboard",  # This must be set to acccess the UI via `kubectl proxy`
                "extraArgs": ["--token-ttl=0"],
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

    def add_emr_containers_for_airflow(self) -> eks.ServiceAccount:
        sa = self.cluster.add_service_account(
            "AirflowServiceAccount", namespace="airflow"
        )

        sa.add_to_principal_policy(
            iam.PolicyStatement(
                actions=[
                    "emr-containers:StartJobRun",
                    "emr-containers:ListJobRuns",
                    "emr-containers:DescribeJobRun",
                    "emr-containers:CancelJobRun",
                ],
                resources=["*"],
            )
        )

        return sa

    def enable_airflow(self, namespace: str = "airflow"):
        # While `add_helm_chart` will create the namespace for us if it doesn't exist,
        # we have to create it here because we need to create a service role for emr-containers.
        ns = self.cluster.add_manifest(
            "airflow-namespace",
            {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": namespace}},
        )
        # This is specific to emr-containers and Airflow so we can run EMR on EKS jobs
        service_role = self.add_emr_containers_for_airflow()
        service_role.node.add_dependency(ns)

        volume = self.cluster.add_manifest("multiaz-volume", self.gp2_multiazvolume())
        chart = self.cluster.add_helm_chart(
            "airflow",
            namespace=namespace,
            chart="airflow",
            repository="https://airflow-helm.github.io/charts",
            version="8.0.5",
            values={
                "airflow": {
                    "config": {
                        "AIRFLOW__LOGGING__REMOTE_LOGGING": "False",
                    },
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
                        },
                        {
                            "name": "AWS_DEFAULT_REGION",
                            "value": cdk.Aws.REGION,
                        },
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
                "serviceAccount": {
                    "create": False,
                    "name": service_role.service_account_name,
                    "annotations": {
                        "eks.amazonaws.com/role-arn": service_role.role.role_arn
                    },
                },
            },
        )
        chart.node.add_dependency(ns)
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