from aws_cdk import (
    core as cdk,
    aws_emr as emr,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_s3 as s3,
    aws_servicecatalog as servicecatalog,
)


class EMRStudio(cdk.Stack):
    studio: emr.CfnStudio

    def __init__(
        self,
        scope: cdk.Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Studios require the following
        # - An engine security group
        # - A workspace security group
        # - An s3 bucket for notebook assets
        # - Service role and user role
        engine_sg = ec2.SecurityGroup(self, "EMRStudioEngine", vpc=vpc)

        # The workspace security group requires explicit egress access to the engine security group.
        # For that reason, we disable the default allow all.
        workspace_sg = ec2.SecurityGroup(
            self, "EMRWorkspaceEngine", vpc=vpc, allow_all_outbound=False
        )
        engine_sg.add_ingress_rule(
            workspace_sg,
            ec2.Port.tcp(18888),
            "Allow inbound traffic to EngineSecurityGroup ( from notebook to cluster for port 18888 )",
        )
        workspace_sg.add_egress_rule(
            engine_sg,
            ec2.Port.tcp(18888),
            "Allow outbound traffic from WorkspaceSecurityGroup ( from notebook to cluster for port 18888 )",
        )
        workspace_sg.connections.allow_to_any_ipv4(
            ec2.Port.tcp(443), "Required for outbound git access"
        )

        # This is here Studio assests live like ipynb notebooks and git repos
        studio_bucket = s3.Bucket(self, "EMRStudioAssets")

        service_role = iam.Role(
            self,
            "EMRStudioServiceRole",
            assumed_by=iam.ServicePrincipal("elasticmapreduce.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy(
                    self,
                    "EMRStudioServiceRolePolicy",
                    statements=[
                        iam.PolicyStatement(
                            sid="AllowEMRReadOnlyActions",
                            actions=[
                                "elasticmapreduce:ListInstances",
                                "elasticmapreduce:DescribeCluster",
                                "elasticmapreduce:ListSteps",
                            ],
                            resources=["*"],
                        ),
                        iam.PolicyStatement(
                            sid="AllowEC2ENIActionsWithEMRTags",
                            actions=[
                                "ec2:CreateNetworkInterfacePermission",
                                "ec2:DeleteNetworkInterface",
                            ],
                            resources=[
                                cdk.Stack.format_arn(
                                    self,
                                    service="ec2",
                                    resource_name="network-interface/*",
                                )
                            ],
                            conditions={
                                "StringEquals": {
                                    "aws:ResourceTag/for-use-with-amazon-emr-managed-policies": "true"
                                }
                            },
                        ),
                        iam.PolicyStatement(
                            sid="AllowEC2ENIAttributeAction",
                            actions=["ec2:ModifyNetworkInterfaceAttribute"],
                            resources=[
                                [
                                    cdk.Stack.format_arn(
                                        self, service="ec2", resource_name=f"{name}/*"
                                    )
                                    for name in [
                                        "instance",
                                        "network-interface",
                                        "security-group",
                                    ]
                                ]
                            ],
                        ),
                        iam.PolicyStatement(
                            sid='AllowEC2SecurityGroupActionsWithEMRTags',
                            actions=[
                                "ec2:AuthorizeSecurityGroupEgress",
                                "ec2:AuthorizeSecurityGroupIngress",
                                "ec2:RevokeSecurityGroupEgress",
                                "ec2:RevokeSecurityGroupIngress",
                                "ec2:DeleteNetworkInterfacePermission",
                            ],
                            resources=['*'],
                            conditions={
                                "StringEquals": {
                                    "aws:ResourceTag/for-use-with-amazon-emr-managed-policies": "true"
                                }
                            },
                        ),
                        iam.PolicyStatement(
                            sid="AllowDefaultEC2SecurityGroupsCreationWithEMRTags",
                            actions=["ec2:CreateSecurityGroup"],
                            resources=[
                                cdk.Stack.format_arn(
                                    self,
                                    service="ec2",
                                    resource_name="security-group/*",
                                )
                            ],
                            conditions={
                                "StringEquals": {
                                    "aws:ResourceTag/for-use-with-amazon-emr-managed-policies": "true"
                                }
                            },
                        ),
                        iam.PolicyStatement(
                            sid="AllowDefaultEC2SecurityGroupsCreationInVPCWithEMRTags",
                            actions=["ec2:CreateSecurityGroup"],
                            resources=[
                                cdk.Stack.format_arn(
                                    self,
                                    service="ec2",
                                    resource_name="vpc/*",
                                )
                            ],
                            conditions={
                                "StringEquals": {
                                    "aws:ResourceTag/for-use-with-amazon-emr-managed-policies": "true"
                                }
                            },
                        ),
                        iam.PolicyStatement(
                            sid="AllowAddingEMRTagsDuringDefaultSecurityGroupCreation",
                            actions=["ec2:CreateTags"],
                            resources=[
                                cdk.Stack.format_arn(
                                    self,
                                    service="ec2",
                                    resource_name="security-group/*",
                                )
                            ],
                            conditions={
                                "StringEquals": {
                                    "aws:ResourceTag/for-use-with-amazon-emr-managed-policies": "true",
                                    "ec2:CreateAction": "CreateSecurityGroup"
                                }
                            },
                        ),
                        iam.PolicyStatement(
                            sid="AllowEC2ENICreationWithEMRTags",
                            actions=["ec2:CreateNetworkInterface"],
                            resources=[
                                cdk.Stack.format_arn(
                                    self,
                                    service="ec2",
                                    resource_name="network-interface/*",
                                )
                            ],
                            conditions={
                                "StringEquals": {
                                    "aws:ResourceTag/for-use-with-amazon-emr-managed-policies": "true"
                                }
                            },
                        ),
                        iam.PolicyStatement(
                            sid="AllowEC2ENICreationInSubnetAndSecurityGroupWithEMRTags",
                            actions=["ec2:CreateNetworkInterface"],
                            resources=[
                                [cdk.Stack.format_arn(
                                    self,
                                    service="ec2",
                                    resource_name=f"{name}/*",
                                ) for name in ['subnet', 'security-group']]
                            ],
                            conditions={
                                "StringEquals": {
                                    "aws:ResourceTag/for-use-with-amazon-emr-managed-policies": "true"
                                }
                            },
                        ),
                        iam.PolicyStatement(
                            sid="AllowAddingTagsDuringEC2ENICreation",
                            actions=["ec2:CreateTags"],
                            resources=[
                                cdk.Stack.format_arn(
                                    self,
                                    service="ec2",
                                    resource_name="network-interface/*",
                                )
                            ],
                            conditions={
                                "StringEquals": {
                                    "ec2:CreateAction": "CreateNetworkInterface"
                                }
                            },
                        ),
                        iam.PolicyStatement(
                            sid="AllowEC2ReadOnlyActions",
                            actions=[
                                "ec2:DescribeSecurityGroups",
                                "ec2:DescribeNetworkInterfaces",
                                "ec2:DescribeTags",
                                "ec2:DescribeInstances",
                                "ec2:DescribeSubnets",
                                "ec2:DescribeVpcs",
                            ],
                            resources=['*'],
                        ),
                        iam.PolicyStatement(
                            sid="AllowSecretsManagerReadOnlyActionsWithEMRTags",
                            actions=["secretsmanager:GetSecretValue"],
                            resources=[
                                cdk.Stack.format_arn(
                                    self,
                                    service="secretsmanager",
                                    resource_name="secret:*",
                                )
                            ],
                            conditions={
                                "StringEquals": {
                                    "aws:ResourceTag/for-use-with-amazon-emr-managed-policies": "true"
                                }
                            },
                        ),
                        iam.PolicyStatement(
                            sid="S3permission",
                            actions=[
                                "s3:PutObject",
                                "s3:GetObject",
                                "s3:GetEncryptionConfiguration",
                                "s3:ListBucket",
                                "s3:DeleteObject",
                            ],
                            resources=["arn:aws:s3:::*"],
                        ),
                    ],
                )
            ],
        )
        user_role = iam.Role(
            self,
            "EMRStudioUserRole",
            assumed_by=iam.ServicePrincipal("elasticmapreduce.amazonaws.com"),
        )

        # TODO: PAUSED HERE UPDATING TEMPLATE
        basic_user_policy = iam.ManagedPolicy(
            self,
            "studio_basic_user_policy",
            roles=[user_role],
            document=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        actions=[
                            "elasticmapreduce:CreateEditor",
                            "elasticmapreduce:DescribeEditor",
                            "elasticmapreduce:ListEditors",
                            "elasticmapreduce:StartEditor",
                            "elasticmapreduce:StopEditor",
                            "elasticmapreduce:DeleteEditor",
                            "elasticmapreduce:OpenEditorInConsole",
                            "elasticmapreduce:AttachEditor",
                            "elasticmapreduce:DetachEditor",
                            "elasticmapreduce:CreateRepository",
                            "elasticmapreduce:DescribeRepository",
                            "elasticmapreduce:DeleteRepository",
                            "elasticmapreduce:ListRepositories",
                            "elasticmapreduce:LinkRepository",
                            "elasticmapreduce:UnlinkRepository",
                            "elasticmapreduce:DescribeCluster",
                            "elasticmapreduce:ListInstanceGroups",
                            "elasticmapreduce:ListBootstrapActions",
                            "elasticmapreduce:ListClusters",
                            "elasticmapreduce:ListSteps",
                            "elasticmapreduce:CreatePersistentAppUI",
                            "elasticmapreduce:DescribePersistentAppUI",
                            "elasticmapreduce:GetPersistentAppUIPresignedURL",
                            "secretsmanager:CreateSecret",
                            "secretsmanager:ListSecrets",
                            "emr-containers:DescribeVirtualCluster",
                            "emr-containers:ListVirtualClusters",
                            "emr-containers:DescribeManagedEndpoint",
                            "emr-containers:ListManagedEndpoints",
                            "emr-containers:CreateAccessTokenForManagedEndpoint",
                            "emr-containers:DescribeJobRun",
                            "emr-containers:ListJobRuns",
                        ],
                        resources=["*"],
                    ),
                    iam.PolicyStatement(
                        actions=["iam:PassRole"], resources=[service_role.role_arn]
                    ),
                    iam.PolicyStatement(
                        actions=[
                            "s3:ListAllMyBuckets",
                            "s3:ListBucket",
                            "s3:GetBucketLocation",
                        ],
                        resources=["arn:aws:s3:::*"],
                    ),
                    iam.PolicyStatement(
                        actions=["s3:GetObject"],
                        resources=[
                            f"arn:aws:s3:::{studio_bucket.bucket_name}/*",
                            f"arn:aws:s3:::aws-logs-{cdk.Aws.ACCOUNT_ID}-{cdk.Aws.REGION}/elasticmapreduce/*",
                        ],
                    ),
                ]
            ),
        )
        advanced_user_policy = iam.ManagedPolicy(
            self,
            "studio_advanced_user_policy",
            roles=[user_role],
            document=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        actions=[
                            "elasticmapreduce:CreateEditor",
                            "elasticmapreduce:DescribeEditor",
                            "elasticmapreduce:ListEditors",
                            "elasticmapreduce:StartEditor",
                            "elasticmapreduce:StopEditor",
                            "elasticmapreduce:DeleteEditor",
                            "elasticmapreduce:OpenEditorInConsole",
                            "elasticmapreduce:AttachEditor",
                            "elasticmapreduce:DetachEditor",
                            "elasticmapreduce:CreateRepository",
                            "elasticmapreduce:DescribeRepository",
                            "elasticmapreduce:DeleteRepository",
                            "elasticmapreduce:ListRepositories",
                            "elasticmapreduce:LinkRepository",
                            "elasticmapreduce:UnlinkRepository",
                            "elasticmapreduce:DescribeCluster",
                            "elasticmapreduce:ListInstanceGroups",
                            "elasticmapreduce:ListBootstrapActions",
                            "elasticmapreduce:ListClusters",
                            "elasticmapreduce:ListSteps",
                            "elasticmapreduce:CreatePersistentAppUI",
                            "elasticmapreduce:DescribePersistentAppUI",
                            "elasticmapreduce:GetPersistentAppUIPresignedURL",
                            "secretsmanager:CreateSecret",
                            "secretsmanager:ListSecrets",
                            "emr-containers:DescribeVirtualCluster",
                            "emr-containers:ListVirtualClusters",
                            "emr-containers:DescribeManagedEndpoint",
                            "emr-containers:ListManagedEndpoints",
                            "emr-containers:CreateAccessTokenForManagedEndpoint",
                            "emr-containers:DescribeJobRun",
                            "emr-containers:ListJobRuns",
                        ],
                        resources=["*"],
                    ),
                    iam.PolicyStatement(
                        actions=[
                            "servicecatalog:DescribeProduct",
                            "servicecatalog:DescribeProductView",
                            "servicecatalog:DescribeProvisioningParameters",
                            "servicecatalog:ProvisionProduct",
                            "servicecatalog:SearchProducts",
                            "servicecatalog:UpdateProvisionedProduct",
                            "servicecatalog:ListProvisioningArtifacts",
                            "servicecatalog:DescribeRecord",
                            "cloudformation:DescribeStackResources",
                        ],
                        resources=["*"],
                        sid="AllowIntermediateActions",
                    ),
                    iam.PolicyStatement(
                        actions=["elasticmapreduce:RunJobFlow"],
                        resources=["*"],
                        sid="AllowAdvancedActions",
                    ),
                    iam.PolicyStatement(
                        actions=["iam:PassRole"],
                        resources=[
                            service_role.role_arn,
                            f"arn:aws:iam::{cdk.Aws.ACCOUNT_ID}:role/EMR_DefaultRole",
                            f"arn:aws:iam::{cdk.Aws.ACCOUNT_ID}:role/EMR_EC2_DefaultRole",
                        ],
                    ),
                    iam.PolicyStatement(
                        actions=[
                            "s3:ListAllMyBuckets",
                            "s3:ListBucket",
                            "s3:GetBucketLocation",
                        ],
                        resources=["arn:aws:s3:::*"],
                    ),
                    iam.PolicyStatement(
                        actions=["s3:GetObject"],
                        resources=[
                            f"arn:aws:s3:::{studio_bucket.bucket_name}/*",
                            f"arn:aws:s3:::aws-logs-{cdk.Aws.ACCOUNT_ID}-{cdk.Aws.REGION}/elasticmapreduce/*",
                        ],
                    ),
                ]
            ),
        )

        studio = emr.CfnStudio(
            self,
            construct_id,
            name=name,
            auth_mode="SSO",
            vpc_id=vpc.vpc_id,
            default_s3_location=studio_bucket.s3_url_for_object(),
            engine_security_group_id=engine_sg.security_group_id,
            workspace_security_group_id=workspace_sg.security_group_id,
            service_role=service_role.role_arn,
            user_role=user_role.role_arn,
            subnet_ids=vpc.select_subnets().subnet_ids,
        )

        # TODO: Remove this hard-coded user :(
        mapping = emr.CfnStudioSessionMapping(
            self,
            "dacort_studio_mapping",
            identity_name="dacort",
            identity_type="USER",
            session_policy_arn=advanced_user_policy.managed_policy_arn,
            studio_id=studio.attr_studio_id,
        )

        cdk.CfnOutput(self, "EMRStudioURL", value=studio.attr_url)

        ## Now it's time for service catalog stuff
        sc_role = iam.Role(
            self,
            "EMRStudioClusterTemplateLaunchRole",
            assumed_by=iam.ServicePrincipal("servicecatalog.amazonaws.com"),
        )
        sc_policy = iam.ManagedPolicy(
            self,
            "EMRStudioClusterTemplatePolicy",
            roles=[sc_role],
            document=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        actions=[
                            "cloudformation:CreateStack",
                            "cloudformation:DeleteStack",
                            "cloudformation:DescribeStackEvents",
                            "cloudformation:DescribeStacks",
                            "cloudformation:GetTemplateSummary",
                            "cloudformation:SetStackPolicy",
                            "cloudformation:ValidateTemplate",
                            "cloudformation:UpdateStack",
                            "elasticmapreduce:RunJobFlow",
                            "elasticmapreduce:DescribeCluster",
                            "elasticmapreduce:TerminateJobFlows",
                            "servicecatalog:*",
                            "s3:GetObject",
                        ],
                        resources=["*"],
                    ),
                    iam.PolicyStatement(
                        actions=["iam:PassRole"],
                        resources=[
                            f"arn:aws:iam::{cdk.Aws.ACCOUNT_ID}:role/EMR_DefaultRole",
                            f"arn:aws:iam::{cdk.Aws.ACCOUNT_ID}:role/EMR_EC2_DefaultRole",
                        ],
                    ),
                ]
            ),
        )

        sc_portfolio = servicecatalog.CfnPortfolio(
            self,
            "EMRStudioClusterTemplatePortfolio",
            display_name="ClusterTemplatePortfolio",
            provider_name="emr-studio-examples",
        )
        sc_portfolio_assoction = servicecatalog.CfnPortfolioPrincipalAssociation(
            self,
            "EMRStudioClusterTemplatePortfolioPrincipalAssociationForEndUser",
            principal_arn=user_role.role_arn,
            portfolio_id=sc_portfolio.ref,
            principal_type="IAM",
        )
        sc_portfolio_assoction.node.add_dependency(sc_portfolio)

        basemap_cluster = servicecatalog.CfnCloudFormationProduct(
            self,
            "EMRStudioBasemapProduct",
            name="matplotlib-cluster",
            description="An emr-6.2.0 cluster that has matplotlib pre-installed.",
            owner="emr-studio-examples",
            provisioning_artifact_parameters=[
                servicecatalog.CfnCloudFormationProduct.ProvisioningArtifactPropertiesProperty(
                    name="Matplotlib Cluster Template",
                    description="Matplotlib Cluster Template",
                    info={
                        "LoadTemplateFromURL": "https://gist.githubusercontent.com/dacort/14466352d025c7fcdeafda438de1384b/raw/17a2e8980b5629c390155a65116cec9f056bda31/matplotlib-cluster.yaml"
                    },
                )
            ],
        )
        sc_productassoc = servicecatalog.CfnPortfolioProductAssociation(
            self,
            "EMRStudioBasemapProductPortfolioMapping",
            portfolio_id=sc_portfolio.ref,
            product_id=basemap_cluster.ref,
        )

        sc_productassoc.node.add_dependency(sc_portfolio)
        sc_productassoc.node.add_dependency(basemap_cluster)

        sc_constraint = servicecatalog.CfnLaunchRoleConstraint(
            self,
            "EMRStudioPortfolioLaunchRoleConstraint",
            portfolio_id=sc_portfolio.ref,
            product_id=basemap_cluster.ref,
            role_arn=sc_role.role_arn,
        )
        sc_constraint.node.add_dependency(sc_portfolio)
        sc_constraint.node.add_dependency(basemap_cluster)
