from aws_cdk import Stack
from aws_cdk import aws_emrserverless as emrs
from aws_cdk import aws_iam as iam  # Duration,
from aws_cdk import custom_resources as custom
from constructs import Construct


class EmrServerlessJobRunStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create a serverless Spark app
        serverless_app = emrs.CfnApplication(
            self,
            "spark_app",
            release_label="emr-6.9.0",
            type="SPARK",
            name="cdk-spark",
        )

        # We need an execution role to run the job, this one has no access to anything
        # But will be granted PassRole access by the Lambda that's starting the job.
        role = iam.Role(
            scope=self,
            id="spark_job_execution_role",
            assumed_by=iam.ServicePrincipal("emr-serverless.amazonaws.com"),
        )

        # Create a custom resource that starts a job run
        myjobrun = custom.AwsCustomResource(
            self,
            "serverless-job-run",
            on_create={
                "service": "EMRServerless",
                "action": "startJobRun",
                "parameters": {
                    "applicationId": serverless_app.attr_application_id,
                    "executionRoleArn": role.role_arn,
                    "name": "cdkJob",
                    "jobDriver": {"sparkSubmit": {"entryPoint": "local:///usr/lib/spark/examples/src/main/python/pi.py"}},
                },
                "physical_resource_id": custom.PhysicalResourceId.from_response(
                    "jobRunId"
                ),
            },
            policy=custom.AwsCustomResourcePolicy.from_sdk_calls(
                resources=custom.AwsCustomResourcePolicy.ANY_RESOURCE
            ),
        )

        # Ensure the Lambda can call startJobRun with the earlier-created role
        myjobrun.grant_principal.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                resources=[role.role_arn],
                actions=["iam:PassRole"],
                conditions={
                    "StringLike": {
                        "iam:PassedToService": "emr-serverless.amazonaws.com"
                    }
                },
            )
        )
