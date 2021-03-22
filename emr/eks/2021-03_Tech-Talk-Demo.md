# EMR on EKS Tech Talk : Demo : Job Creation

Create a simple job using a built-in PySpark script.

```shell
aws emr-containers start-job-run \
    --virtual-cluster-id ${EMR_EKS_CLUSTER_ID} \
    --name sample-pi \
    --execution-role-arn ${EMR_EKS_EXECUTION_ARN} \
    --release-label emr-6.2.0-latest \
    --job-driver '{
        "sparkSubmitJobDriver": {
            "entryPoint": "local:///usr/lib/spark/examples/src/main/python/pi.py",
            "sparkSubmitParameters": "--conf spark.executor.instances=2 --conf spark.executor.memory=2G --conf spark.executor.cores=2 --conf spark.driver.cores=1"
        }
    }'
```

Let's highlight a few of the [configuration options](https://docs.aws.amazon.com/emr/latest/EMR-on-EKS-DevelopmentGuide/emr-eks-jobs-CLI.html#emr-eks-jobs-parameters):

1. `--virtual-cluster-id` - This is the [virtual cluster](https://docs.aws.amazon.com/emr/latest/EMR-on-EKS-DevelopmentGuide/setting-up-registration.html) that maps EMR to an associated Amazon EKS cluster and namespace.
2. `--release-label` - Specific EMR version to run. You can deploy Amazon EMR on EKS with Amazon EMR versions 5.32.0 and 6.2.0 and later. The 5.x series runs Spark 2.4 and the 6.x series runs Spark 3.0.
3. `--job-driver` - This is how you specify your Spark code and associated job or Spark parameters.

What this command does is it tells the EMR virtual cluster to create a new job in the associated Kubernetes cluster. This first starts a "job submitter" pod that is responsible for submitting the Spark job to the Kubernetes cluster with the necessary configuration. Spark driver and executor pods will then start on the cluster in order to run the Spark job!
# EMR on EKS Tech Talk : Demo : Logging and Monitoring

For this portion of the demo, we'll show how to add different log output mechanisms to your Spark jobs.

There are two additional mechanisms we can use to monitor Spark output. For both of these, we'll be adding a new parameter to the `emr-containers start-job-run` command: `--configuration-overrides`. With that parameter, we can provide CloudWatch or S3 locations for Spark to log its output to.

## CloudWatch logs

_Prerequisites_:
- Ensure that you have your desired CloudWatch Log Group created.
- Ensure the Role you're using to run the job has the appropriate permissions to write to the log stream.

Now let's run the same job as before, but just add a `cloudWatchMonitoringConfiguration` section. Everything else remains the same.

```shell
aws emr-containers start-job-run \
    --virtual-cluster-id ${EMR_EKS_CLUSTER_ID} \
    --name dacort-pi-cloudwatch \
    --execution-role-arn ${EMR_EKS_EXECUTION_ARN} \
    --release-label emr-6.2.0-latest \
    --job-driver '{
        "sparkSubmitJobDriver": {
            "entryPoint": "local:///usr/lib/spark/examples/src/main/python/pi.py",
            "sparkSubmitParameters": "--conf spark.executor.instances=1 --conf spark.executor.memory=2G --conf spark.executor.cores=1 --conf spark.driver.cores=1"
        }
    }' \
    --configuration-overrides '{
        "monitoringConfiguration": {
            "cloudWatchMonitoringConfiguration": {
                "logGroupName": "/aws/eks/dacort-emr/eks-spark",
                "logStreamNamePrefix": "pi"
            }
        }
    }'
```

As the job runs, we can see driver and executor output, for both `stdout` and `stderr` show up in our [CloudWatch console](https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/$252Faws$252Feks$252Fdacort-emr$252Feks-spark$3FlogStreamNameFilter$3Dpi).

## S3 Logs

_Prerequisites_:
- Ensure that you have created the S3 bucket.
- Ensure the Role you're using to run the job has the appropriate permissions to write to the bucket.

Now let's add an `s3MonitoringConfiguration` section to the `--configuration-overrides`.

```shell
aws emr-containers start-job-run \
    --virtual-cluster-id ${EMR_EKS_CLUSTER_ID} \
    --name dacort-pi-s3 \
    --execution-role-arn ${EMR_EKS_EXECUTION_ARN} \
    --release-label emr-6.2.0-latest  \
    --job-driver '{
        "sparkSubmitJobDriver": {
            "entryPoint": "local:///usr/lib/spark/examples/src/main/python/pi.py",
            "sparkSubmitParameters": "--conf spark.executor.instances=1 --conf spark.executor.memory=2G --conf spark.executor.cores=1 --conf spark.driver.cores=1"
        }
    }' \
    --configuration-overrides '{
        "monitoringConfiguration": {
            "cloudWatchMonitoringConfiguration": { "logGroupName": "/aws/eks/dacort-emr/eks-spark", "logStreamNamePrefix": "pi" },
            "s3MonitoringConfiguration": { 
                "logUri": "s3://'${S3_BUCKET}'/emr-eks-logs/pi/"
            }
        }
    }'
```

```shell
aws s3 ls s3://${S3_BUCKET}/emr-eks-logs/pi/
```

Again, if we continuously list the output of the bucket, we can see logs start to show up as the job is running. The format is as follows:

```
s3://<BUCKET>/<PREFIX>/<CLUSTER_ID>/jobs/<JOB_ID>/containers/spark-<UNIQUE_ID>/(driver|exec-num)/(stdout|stderr).gz
```

As an example, here's how we can view the output of the Spark driver from the `pi.py` job:

```shell
➜ aws s3 cp s3://${S3_BUCKET}/emr-eks-logs/pi/b05e9sj03vp81ed2115jau5hi/jobs/00000002ttskj186g7r/containers/spark-91ed951e58eb4b609ab6a7c96b12c4ae/spark-00000002ttskj186g7r-driver/stdout.gz - | gunzip
Pi is roughly 3.143740
```

# EMR on EKS Tech Talk : Demo : Optimization

There are a few ways of customizing how Spark jobs run on EMR on EKS. 

1. Manually specify Spark executor cores and memory
2. Utilize Dynamic Resource Allocation (Spark >= 3.0 only on Kubernetes)
3. Explicit instance placement with Kubernetes labels

Let's walk through how we do that. One quick assumption: Much of what we discuss below assumes you are either using the Cluster Autoscaler to dynamically add resources or are utilizing a serverless approach with Fargate.

## Customize spark-submit parameters

This is no different than standard Spark, but there are a couple things I want to call out that are specific to EMR on EKS.

1. You need to be aware of what instance types are in your EKS cluster. If you request `spark.executor.cores=10` but all the instance types in your EKS cluster are `xlarge` or smaller (4 vCPUs or less), your Kubernetes Pods will get stuck in the `Pending` state waiting for CPU cores.


```shell
aws emr-containers start-job-run \
    --virtual-cluster-id ${EMR_EKS_CLUSTER_ID} \
    --name sample-pi-10-cores \
    --execution-role-arn ${EMR_EKS_EXECUTION_ARN} \
    --release-label emr-6.2.0-latest \
    --job-driver '{
        "sparkSubmitJobDriver": {
            "entryPoint": "local:///usr/lib/spark/examples/src/main/python/pi.py",
            "sparkSubmitParameters": "--conf spark.executor.instances=2 --conf spark.executor.memory=2G --conf spark.executor.cores=10 --conf spark.driver.cores=1"
        }
    }'
```

2. If you are running EKS with Fargate, you cannot use a value greater than `3` for `spark.executor.cores`. This is due to Fargate having a max supported configuration of 4 vCPU and additional vCPU overhead leaving 3 cores the jobs.

Other than that, just tweak as is necessary for your job. To get a quick example, let's run the job with a greater number of `spark.executor.instances`. First, bump it up to 10. I'm also going to add a Spark parameter that increases the number of partitions in the `pi.py` job.

```shell
aws emr-containers start-job-run \
    --virtual-cluster-id ${EMR_EKS_CLUSTER_ID} \
    --name sample-pi-10-executors \
    --execution-role-arn ${EMR_EKS_EXECUTION_ARN} \
    --release-label emr-6.2.0-latest \
    --job-driver '{
        "sparkSubmitJobDriver": {
            "entryPoint": "local:///usr/lib/spark/examples/src/main/python/pi.py",
            "entryPointArguments": ["10"],
            "sparkSubmitParameters": "--conf spark.executor.instances=10 --conf spark.executor.memory=2G --conf spark.executor.cores=3 --conf spark.driver.cores=1"
        }
    }'
```

If we keep an eye on the Kubernetes Dashboard, we'll see 10 executors start to spin up instead of the 2 we had previously. Depending on your cluster capacity, you may see a delay as additional compute resources are brought online.

## Dynamic Resource Allocation

Dynamic Resource Allocation (DRA) provides a mechanism to dynamically adjust the resources your application occupies based on the workload.

Spark on Kubernetes doesn't support the external shuffle service, typically required for DRA, but DRA can be achieved by enabling shuffle tracking.

DRA can be useful if you're not familiar with your workload or want to make use of the flexibility of Kubernetes to request resources as necessary.

To enable DRA, we'll add an `applicationConfiguration` section to the `--configuration-overrides` parameter to specifically enable it and define the executor behavior. This is the section we'll add:

```json
{
    "classification": "spark-defaults",
    "properties": {
        "spark.dynamicAllocation.enabled": "true",
        "spark.dynamicAllocation.shuffleTracking.enabled":"true",
        "spark.dynamicAllocation.minExecutors":"5",
        "spark.dynamicAllocation.maxExecutors":"100",
        "spark.dynamicAllocation.initialExecutors":"10"
    }
}
```

This configuration enables DRA and shuffle tracking, requests an initial executor count of 5, and allows it to scale up to 100 executors and down to 2. Notice that we _also_ leave off the `spark.executor.instances` spark-submit configuration option, but leave the others.

For this specific job, we're going to use a different Spark job that takes a little bit longer to run so we can see the effects of DRA. And we're going to decrease the amount of cores per executor to artificially limit performance so we can watch the dynamic scaling.


```shell
aws emr-containers start-job-run \
    --virtual-cluster-id ${EMR_EKS_CLUSTER_ID} \
    --name dacort-windycity \
    --execution-role-arn ${EMR_EKS_EXECUTION_ARN} \
    --release-label emr-6.2.0-latest \
    --job-driver '{
        "sparkSubmitJobDriver": {
            "entryPoint": "s3://'${S3_BUCKET}'/code/pyspark/windy_city.py",
            "entryPointArguments": ["-124.86,24.62,-66.96,49.16"],
            "sparkSubmitParameters": "--conf spark.executor.memory=2G --conf spark.executor.cores=1 --conf spark.driver.cores=1"
        }
    }' \
    --configuration-overrides '{
        "applicationConfiguration": [
            {
                "classification": "spark-defaults",
                "properties": {
                    "spark.dynamicAllocation.enabled": "true",
                    "spark.dynamicAllocation.shuffleTracking.enabled":"true",
                    "spark.dynamicAllocation.minExecutors":"2",
                    "spark.dynamicAllocation.maxExecutors":"100",
                    "spark.dynamicAllocation.initialExecutors":"5"
                }
            }
        ]
    }'
```

```
            "entryPointArguments": ["-124.86,24.62,-66.96,49.16"],
```

## Instance Placement

Finally, we can customize to some degree where the jobs run on the EKS cluster using standard Kubernetes labels. You might want to do this if you have a job with specific CPU or memory requirements and want to ensure it wants to run on a specific instance type. 

You could configure your jobs to run in a [single availability zone](https://aws.github.io/aws-emr-containers-best-practices/node-placement/docs/eks-node-placement/#single-az-placement) or you can schedule on specific instance types.

To do that, we'll add a filter condition to `spark.kubernetes.node.selector`. As an example, if we know we have a intensive application and only want to run it on  `c5.xlarge` instances, we can do the following:

```shell
aws emr-containers start-job-run \
    --virtual-cluster-id ${EMR_EKS_CLUSTER_ID} \
    --name windy-city-c5 \
    --execution-role-arn ${EMR_EKS_EXECUTION_ARN} \
    --release-label emr-6.2.0-latest \
    --job-driver '{
        "sparkSubmitJobDriver": {
            "entryPoint": "local:///usr/lib/spark/examples/src/main/python/pi.py",
            "sparkSubmitParameters": "--conf spark.executor.instances=4 --conf spark.executor.memory=1G --conf spark.executor.cores=1 --conf spark.driver.cores=1"
        }
    }' \
    --configuration-overrides '{
        "applicationConfiguration": [
            {
                "classification": "spark-defaults", 
                "properties": {
                    "spark.kubernetes.node.selector.node.kubernetes.io/instance-type":"c5.xlarge"
                }
            }
        ]
    }'
```

Just to see what happens, let's toggle `c5.xlarge` to `m5.xlarge`. Now the driver and executors spin up on the other nodes!

Finally, let's see if we can force a run on Fargate. Let's imagine we have a long-running job, don't want to worry about node groups and instance sizing, and just want some compute capacity. 

In order to do this, we'll create a second EMR virtual cluster that's dedicated to running executors on Fargate. Then, we need to create a Fargate profile with the relevant namespace and labels. If we have an EKS Cluster with both Fargate and Node Groups, the jobs will by default run on the Node Groups. We have two options here:

- `emr-containers.amazonaws.com/resource.type=job.run` - EMR adds a label to all jobs it runs. If you want any EMR job to run on Fargate, add this label to the Fargate profile.
- `emr-containers.amazonaws.com/component=job.submitter|driver|executor` - This allows for fine-grained access. For example, you can have the driver run on node groups and the executors run on Fargate. 

~~Let's try the scenario where we only want executors to run on Fargate.~~ Let's try creating a combination of labels that allows jobs to *only* run on Fargate.

1. Create the new EMR Virtual Cluster
_We'll skip over this, but documenting here for you_

```shell
# Create a new k8s namespace
kubectl create namespace dacort-fargate
# Create an identity mapping for the new namespace so EMR can submit jobs
eksctl create iamidentitymapping \
    --cluster dacort-emr  \
    --namespace dacort-fargate \
    --service-name "emr-containers"
# Update the trust policy for the new namespace
 aws emr-containers update-role-trust-policy \
       --cluster-name dacort-emr \
       --namespace dacort-fargate \
       --role-name emr_eks_execution_role
# Create our virtual cluster!
aws emr-containers create-virtual-cluster \
    --name dacort-fargate \
    --container-provider '{
        "id": "dacort-emr",
        "type": "EKS",
        "info": {
            "eksInfo": {
                "namespace": "dacort-fargate"
            }
        } 
    }'
```

2. Create a Fargate profile for the new namespace that only runs Spark executors

```shell
eksctl create fargateprofile \
    --cluster dacort-emr \
    --name spark-fargate-executors \
    --namespace dacort-fargate \
    --labels emr-containers.amazonaws.com/component=executor
```

_Note that all EMR executors in this namespace will now run on Fargate_

```shell
aws emr-containers start-job-run \
    --virtual-cluster-id ${EMR_EKS_FARGATE_EXEC_CLUSTER_ID} \
    --name pi-on-fargate \
    --execution-role-arn ${EMR_EKS_EXECUTION_ARN} \
    --release-label emr-6.2.0-latest \
    --job-driver '{
        "sparkSubmitJobDriver": {
            "entryPoint": "local:///usr/lib/spark/examples/src/main/python/pi.py",
            "sparkSubmitParameters": "--conf spark.executor.instances=4 --conf spark.executor.memory=1G --conf spark.executor.cores=1 --conf spark.driver.cores=1"
        }
    }'
```