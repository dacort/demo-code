# Run EMR jobs with Airflow

Associated video: [https://youtu.be/Z--sNHqkM7c](https://youtu.be/Z--sNHqkM7c)

Airflow is a popular open source workflow management tool. Amazon EMR is a service that allows you to run various big data frameworks like Spark, Hive, and Presto on top of EC2 or EKS. In this demonstration, we'll show you how to schedule a PySpark job using Airflow on:

- EMR on EC2
- EMR on EKS

What we want to do is run a sample job on both.

Let's get started.

## Pre-requisites

- Pre-existing VPC and [EMR default roles](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-iam-roles.html)
- EMR on EKS virtual cluster and execution role (see my [big data stack blog post](https://dacort.dev/posts/cdk-big-data-stack/) for how to deploy this with CDK)

## Airflow Operators

Airflow has several [EMR Operators](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/operators/emr.html) that can be used to create a cluster, run a job, and terminate a cluster.

In addition, there's currently an open pull request to integrate EMR on EKS as well.

For this demo, we'll show how to use:
1. `EmrCreateJobFlowOperator` to create a new EMR on EC2 cluster, run a job, and automatically terminate the cluster.
2. `EMRContainerOperator` to submit a job to a pre-existing EMR on EKS virtual cluster.

## Configuring Airflow

### IAM Permissions

IAM will need access to start and monitor EMR clusters as well as start and monitor EMR on EKS jobs.

In addition to the standard permissions for the [MWAA service execution role](https://docs.aws.amazon.com/mwaa/latest/userguide/mwaa-create-role.html), we'll also give it access to create these jobs.

EMR on EC2 will also need access to `iam:PassRole` for the default EMR roles.

```python
iam.PolicyStatement(
    actions=[
        "emr-containers:StartJobRun",
        "emr-containers:DescribeJobRun",
        "emr-containers:CancelJobRun",
    ],
    effect=iam.Effect.ALLOW,
    resources=["*"],
),
iam.PolicyStatement(
    actions=[
        "elasticmapreduce:RunJobFlow",
        "elasticmapreduce:DescribeStep",
        "elasticmapreduce:DescribeCluster",
    ],
    effect=iam.Effect.ALLOW,
    resources=["*"],
),
iam.PolicyStatement(
    actions=["iam:PassRole"],
    effect=iam.Effect.ALLOW,
    resources=[
        f"arn:aws:iam::{self.account}:role/EMR_DemoRole",
        f"arn:aws:iam::{self.account}:role/EMR_EC2_DemoRole",
        f"arn:aws:iam::{self.account}:role/EMR_EC2_DefaultRole",
        f"arn:aws:iam::{self.account}:role/EMR_DefaultRole",
    ],
),
```

### Airflow Connections

If you like, you can hard-code your connection options in your job or you can store them in a connection.

At the very least, you need to add `region_name` in the Extra section in your `aws_default` connection.

```json
{"region_name":"us-east-1"}
```

EMR on EC2 doesn't need any additional configuration than this because we're going to create the cluster from scratch and use a default set of roles, security groups, and VPC.

EMR on EKS, however, requires you to already have an execution role and virtual cluster set up.

Here's an example connection that defines a different region, EMR virtual cluster, and execution role ARN for EMR on EKS.

```json
{"region_name":"us-east-2","virtual_cluster_id":"wfto7bwu9n8ajdohqkri06pc1","job_role_arn":"arn:aws:iam::111122223333:role/emr_eks_default_role"}
```

## Running Jobs

### EMR on EC2

ONe mistake I made while working on this was I used an instance size of `c5.xlarge` - unfortunately that didn't work with the default SparkPi job, so I had to change it to an `m5.xlarge`. 

Other than that, the example EMR on EC2 job is pretty straight-forward! It'll create a small cluster with a Step (job) defined by default, wait until that step finishes and then EMR will terminate the cluster.

Let's try to trigger the DAG and see what happens.

### EMR on EKS

Since the pull request has not been merged, we had to deploy our own custom set of plugins to be able to run the EMR on EKS job.

To do this, we made use of my [example EMR on EKS plugin](https://github.com/dacort/emr-eks-airflow2-plugin) repository and added a reference to this in our `requirements.txt` file.

```
emr-containers @ https://github.com/dacort/emr-eks-airflow2-plugin/archive/main.zip
apache-airflow[amazon]==2.0.2
```

The `apache-airflow[amazon]` requirement is needed for the EMR on EC2 Operator.

So, with our requirements installed, our connection defined, let's go ahead and trigger the DAG!
