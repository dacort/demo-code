import aws_cdk as core
import aws_cdk.assertions as assertions

from emr_serverless_job_run.emr_serverless_job_run_stack import EmrServerlessJobRunStack

# example tests. To run these tests, uncomment this file along with the example
# resource in emr_serverless_job_run/emr_serverless_job_run_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = EmrServerlessJobRunStack(app, "emr-serverless-job-run")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
