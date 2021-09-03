# Amazon EMR on EKS examples

## Purpose

Shows how to use the AWS SDK for Java with Amazon EMR on EKS.

_Amazon EMR on EKS allows users to easily submit Spark jobs on Kubernetes._

## Running the code

### Prerequisites

- You must have an AWS account, and have your default credentials and AWS Region
    configured as described in the [AWS Tools and SDKs Shared Configuration and
    Credentials Reference Guide](https://docs.aws.amazon.com/credref/latest/refdocs/creds-config-files.html).

### Building

- Run `mvn package` and then `./run_example.sh` with the class name of the code example.

## Code examples

- [Submit an EMR on EKS job](./src/main/java/aws/example/emrcontainers/StartJobRunExample.java)
  
    `./run_example.sh StartJobRunExample "<VIRTUAL_CLUSTER_ID> <JOB_ROLE_ARN>"`

## Additional Information
- [Amazon EMR on EKS documentatin](https://docs.aws.amazon.com/emr/latest/EMR-on-EKS-DevelopmentGuide/emr-eks.html)
- [Amazon EMR on EKS Best Practices Guide](https://aws.github.io/aws-emr-containers-best-practices/)