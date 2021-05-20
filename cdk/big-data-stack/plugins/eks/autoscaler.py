from aws_cdk import core as cdk, aws_eks as eks, aws_iam as iam


class ClusterAutoscaler:
    eks_cluster_name: str
    eks_stack: cdk.Stack
    eks_cluster: eks.Cluster
    node_group: eks.Nodegroup

    def __init__(
        self,
        cluster_name: str,
        eks: cdk.Stack,
        cluster: eks.Cluster,
        node_groups: list[eks.Nodegroup],
    ) -> None:
        self.eks_cluster_name = cluster_name
        self.eks_stack = eks
        self.eks_cluster = cluster
        self.node_groups = node_groups

    def enable_autoscaling(self):
        """
        Performs the following steps in order to enable the cluster autoscaler on an EKS cluster:
        - Adds tags to the passed node group to enable auto discovery
        - Creates a new IAM Role that can change Auto Scaling Groups
        - Creates a Kubernetes service account
        - Creates a new cluster-autoscaler deployment
        - Creates the corresponding rbac rules
        """
        self.tag_nodegroups()
        self.create_service_account()
        self.add_manifest()

    def tag_nodegroups(self) -> None:
        for ng in self.node_groups:
            self.tag_nodegroup(ng)

    def tag_nodegroup(self, node_group: eks.Nodegroup) -> None:
        """
        This tags the EKS Node Groups with the tags required for the Cluster Autoscaler to mangae them.
        """
        cdk.Tags.of(node_group).add(
            f"k8s.io/cluster-autoscaler/{self.eks_cluster_name}",
            "owned",
            apply_to_launched_instances=True,
        )
        cdk.Tags.of(node_group).add(
            "k8s.io/cluster-autoscaler/enabled",
            "true",
            apply_to_launched_instances=True,
        )

    def create_service_account(self) -> None:
        """
        Creates the k8s `cluster-autoscaler` service account.

        This _also_ creates a corresponding IAM Role with the policies to manage the autoscaling group
        that has the proper trust relationships defined.
        """
        sa = self.eks_cluster.add_service_account(
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

    def add_manifest(self) -> None:
        deployment_spec = self._generate_deployment_spec()
        rbac_rules = self._generate_rbac_rules()

        self.eks_cluster.add_manifest("cluster-autoscaler", deployment_spec)
        for i, rule in enumerate(rbac_rules):
            self.eks_cluster.add_manifest(f"autoscaler-rule-{i}", rule)

    def _generate_deployment_spec(self) -> dict:
        return {
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
                                    f"--node-group-auto-discovery=asg:tag=k8s.io/cluster-autoscaler/enabled,k8s.io/cluster-autoscaler/{self.eks_cluster_name}",
                                ],
                                "env": [
                                    {"name": "AWS_REGION", "value": cdk.Aws.REGION}
                                ],
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
                    },
                },
            },
        }

    def _generate_rbac_rules(self) -> dict:
        return [
            {
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "ClusterRole",
                "metadata": {
                    "name": "cluster-autoscaler",
                    "labels": {
                        "k8s-addon": "cluster-autoscaler.addons.k8s.io",
                        "k8s-app": "cluster-autoscaler",
                    },
                },
                "rules": [
                    {
                        "apiGroups": [""],
                        "resources": ["events", "endpoints"],
                        "verbs": ["create", "patch"],
                    },
                    {
                        "apiGroups": [""],
                        "resources": ["pods/eviction"],
                        "verbs": ["create"],
                    },
                    {
                        "apiGroups": [""],
                        "resources": ["pods/status"],
                        "verbs": ["update"],
                    },
                    {
                        "apiGroups": [""],
                        "resources": ["endpoints"],
                        "resourceNames": ["cluster-autoscaler"],
                        "verbs": ["get", "update"],
                    },
                    {
                        "apiGroups": [""],
                        "resources": ["nodes"],
                        "verbs": ["watch", "list", "get", "update"],
                    },
                    {
                        "apiGroups": [""],
                        "resources": [
                            "pods",
                            "services",
                            "replicationcontrollers",
                            "persistentvolumeclaims",
                            "persistentvolumes",
                        ],
                        "verbs": ["watch", "list", "get"],
                    },
                    {
                        "apiGroups": ["extensions"],
                        "resources": ["replicasets", "daemonsets"],
                        "verbs": ["watch", "list", "get"],
                    },
                    {
                        "apiGroups": ["policy"],
                        "resources": ["poddisruptionbudgets"],
                        "verbs": ["watch", "list"],
                    },
                    {
                        "apiGroups": ["apps"],
                        "resources": ["statefulsets", "replicasets", "daemonsets"],
                        "verbs": ["watch", "list", "get"],
                    },
                    {
                        "apiGroups": ["storage.k8s.io"],
                        "resources": ["storageclasses", "csinodes"],
                        "verbs": ["watch", "list", "get"],
                    },
                    {
                        "apiGroups": ["batch", "extensions"],
                        "resources": ["jobs"],
                        "verbs": ["get", "list", "watch", "patch"],
                    },
                    {
                        "apiGroups": ["coordination.k8s.io"],
                        "resources": ["leases"],
                        "verbs": ["create"],
                    },
                    {
                        "apiGroups": ["coordination.k8s.io"],
                        "resourceNames": ["cluster-autoscaler"],
                        "resources": ["leases"],
                        "verbs": ["get", "update"],
                    },
                ],
            },
            {
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "Role",
                "metadata": {
                    "name": "cluster-autoscaler",
                    "namespace": "kube-system",
                    "labels": {
                        "k8s-addon": "cluster-autoscaler.addons.k8s.io",
                        "k8s-app": "cluster-autoscaler",
                    },
                },
                "rules": [
                    {
                        "apiGroups": [""],
                        "resources": ["configmaps"],
                        "verbs": ["create", "list", "watch"],
                    },
                    {
                        "apiGroups": [""],
                        "resources": ["configmaps"],
                        "resourceNames": [
                            "cluster-autoscaler-status",
                            "cluster-autoscaler-priority-expander",
                        ],
                        "verbs": ["delete", "get", "update", "watch"],
                    },
                ],
            },
            {
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "ClusterRoleBinding",
                "metadata": {
                    "name": "cluster-autoscaler",
                    "labels": {
                        "k8s-addon": "cluster-autoscaler.addons.k8s.io",
                        "k8s-app": "cluster-autoscaler",
                    },
                },
                "roleRef": {
                    "apiGroup": "rbac.authorization.k8s.io",
                    "kind": "ClusterRole",
                    "name": "cluster-autoscaler",
                },
                "subjects": [
                    {
                        "kind": "ServiceAccount",
                        "name": "cluster-autoscaler",
                        "namespace": "kube-system",
                    }
                ],
            },
            {
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "RoleBinding",
                "metadata": {
                    "name": "cluster-autoscaler",
                    "namespace": "kube-system",
                    "labels": {
                        "k8s-addon": "cluster-autoscaler.addons.k8s.io",
                        "k8s-app": "cluster-autoscaler",
                    },
                },
                "roleRef": {
                    "apiGroup": "rbac.authorization.k8s.io",
                    "kind": "Role",
                    "name": "cluster-autoscaler",
                },
                "subjects": [
                    {
                        "kind": "ServiceAccount",
                        "name": "cluster-autoscaler",
                        "namespace": "kube-system",
                    }
                ],
            },
        ]


# Helpful References
# https://itnext.io/amazon-eks-upgrade-journey-from-1-18-to-1-19-cca82de84333
# https://github.com/marcincuber/eks/blob/master/k8s_templates/cluster-autoscaler/autoscaler-deployment.yaml
#
# https://github.com/aws-samples/aws-cdk-for-emr-on-eks/blob/main/emr_eks_cdk/emr_eks_cdk_stack.py