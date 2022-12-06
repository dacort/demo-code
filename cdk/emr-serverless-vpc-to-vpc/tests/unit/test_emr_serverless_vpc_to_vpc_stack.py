import aws_cdk as core
import aws_cdk.assertions as assertions

from emr_serverless_vpc_to_vpc.emr_serverless_vpc_to_vpc_stack import EmrServerlessVpcToVpcStack

# example tests. To run these tests, uncomment this file along with the example
# resource in emr_serverless_vpc_to_vpc/emr_serverless_vpc_to_vpc_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = EmrServerlessVpcToVpcStack(app, "emr-serverless-vpc-to-vpc")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
