# EMR on EKS Pod Templates

## Demos
- Running Spark jobs with Dynamic Resource Allocation (DRA)
- Using pod templates to optimize job cost (Spot and Fargate)
- Using pod templates to run sidecar containers

## Step 1 - Running a simple Spark job

- Using a local Spark example, submit a job with static executor config

```shell
aws emr-containers start-job-run \
    --virtual-cluster-id ${EMR_EKS_CLUSTER_ID} \
    --name dacort-pi-static \
    --execution-role-arn ${EMR_EKS_EXECUTION_ARN} \
    --release-label emr-5.33.0-latest \
    --job-driver '{
        "sparkSubmitJobDriver": {
            "entryPoint": "local:///usr/lib/spark/examples/src/main/python/pi.py",
            "sparkSubmitParameters": "--conf spark.executor.instances=20 --conf spark.executor.memory=2G --conf spark.executor.cores=2 --conf spark.driver.cores=1"
        }
    }' \
    --configuration-overrides '{
        "monitoringConfiguration": {
            "s3MonitoringConfiguration": { 
                "logUri": "s3://'${S3_BUCKET}'/emr-eks-logs/pi/"
            }
        }
    }'
```

## Step 2 - Dynamic Resource Allocation

_Notes_
- Only works with Spark 3.x / EMR 6

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

```shell
aws emr-containers start-job-run \
    --virtual-cluster-id ${EMR_EKS_CLUSTER_ID} \
    --name dacort-windycity-dra \
    --execution-role-arn ${EMR_EKS_EXECUTION_ARN} \
    --release-label emr-6.2.0-latest \
    --job-driver '{
        "sparkSubmitJobDriver": {
            "entryPoint": "s3://'${S3_BUCKET}'/code/pyspark/windy_city.py",
            "sparkSubmitParameters": "--conf spark.executor.memory=2G --conf spark.executor.cores=2 --conf spark.driver.cores=1"
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

## Step 3 - Limit executors to Spot

For this step, we make use of [pod templates](https://docs.aws.amazon.com/emr/latest/EMR-on-EKS-DevelopmentGuide/pod-templates.html).  Pod templates allow you to specify how or where the containers will run in your cluster.


1. Create pod templates for Spot and On-Demand

- `spot_pod_template.yaml`
```yaml
apiVersion: v1
kind: Pod
spec:
  nodeSelector:
    eks.amazonaws.com/capacityType: SPOT
```

- `ondemand_pod_template.yaml`
```yaml
apiVersion: v1
kind: Pod
spec:
  nodeSelector:
    eks.amazonaws.com/capacityType: ON_DEMAND
```

2. Upload those templates to S3

```shell
aws s3 cp spot_pod_template.yaml s3://<BUCKET>/artifacts/pod_templates/
aws s3 cp ondemand_pod_template.yaml s3://<BUCKET>/artifacts/pod_templates/
```

3. Run your Spark job with the pod template specified for the executor!

We also specify on-demand for the driver because we want to ensure the driver persists for the entire length of the job.

```shell
aws emr-containers start-job-run \
    --virtual-cluster-id ${EMR_EKS_CLUSTER_ID} \
    --name dacort-windycity-spot \
    --execution-role-arn ${EMR_EKS_EXECUTION_ARN} \
    --release-label emr-5.33.0-latest \
    --job-driver '{
        "sparkSubmitJobDriver": {
            "entryPoint": "s3://'${S3_BUCKET}'/code/pyspark/windy_city.py",
            "sparkSubmitParameters": "--conf spark.executor.instances=5 --conf spark.executor.memory=2G --conf spark.executor.cores=2 --conf spark.driver.cores=1 --conf spark.kubernetes.driver.podTemplateFile=s3://'${S3_BUCKET}'/artifacts/pod_templates/ondemand_pod_template.yaml --conf spark.kubernetes.executor.podTemplateFile=s3://'${S3_BUCKET}'/artifacts/pod_templates/spot_pod_template.yaml"
        }
    }'
```

And now verify the driver and executors are running where we expect!

```shell
kubectl describe node \
  $(kubectl get pods -n emr-jobs --selector=spark-role=driver -o jsonpath='{.items[*].spec.nodeName}' ) \
  | grep -i capacityType
#                     eks.amazonaws.com/capacityType=ON_DEMAND
```


```shell
kubectl describe node \
  $(kubectl get pods -n emr-jobs --selector=spark-role=executor -o jsonpath='{.items[*].spec.nodeName}' ) \
  | grep -i capacityType
                    # eks.amazonaws.com/capacityType=SPOT
                    # eks.amazonaws.com/capacityType=SPOT
                    # eks.amazonaws.com/capacityType=SPOT
                    # eks.amazonaws.com/capacityType=SPOT
                    # eks.amazonaws.com/capacityType=SPOT
```

## Step 3.5 - Pod Templates: Limit executors to Fargate

- Ensure you have the Fargate role

```shell
aws iam create-role --role-name AmazonEKSFargatePodExecutionRole --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"eks-fargate-pods.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
aws iam attach-role-policy --role-name AmazonEKSFargatePodExecutionRole --policy-arn arn:aws:iam::aws:policy/AmazonEKSFargatePodExecutionRolePolicy
```

- Create a new Fargate profile in the appropriate namespace

We need to add a specific selector, otherwise *all* jobs in the `emr-jobs` namespace will run on Fargate.

```shell
aws eks create-fargate-profile \
    --cluster-name data-team \
    --fargate-profile-name spark-fargate-executors \
    --selectors 'namespace=emr-jobs,labels={eks.amazonaws.com/capacityType=FARGATE}' \
    --pod-execution-role-arn ${FARGATE_EXECUTION_ARN}
```

- Assign Spark executor label

In order to properly run our executors _only_ on Fargate, we'll add a label to the spark-submit parameters:

```
--conf spark.kubernetes.executor.label.eks.amazonaws.com/capacityType=FARGATE
```

- Run our job!

```shell
aws emr-containers start-job-run \
    --virtual-cluster-id ${EMR_EKS_CLUSTER_ID} \
    --name dacort-windycity-fargate \
    --execution-role-arn ${EMR_EKS_EXECUTION_ARN} \
    --release-label emr-5.33.0-latest \
    --job-driver '{
        "sparkSubmitJobDriver": {
            "entryPoint": "s3://'${S3_BUCKET}'/code/pyspark/windy_city.py",
            "sparkSubmitParameters": "--conf spark.executor.instances=5 --conf spark.executor.memory=2G --conf spark.executor.cores=2 --conf spark.driver.cores=1 --conf spark.kubernetes.driver.podTemplateFile=s3://'${S3_BUCKET}'/artifacts/pod_templates/ondemand_pod_template.yaml --conf spark.kubernetes.executor.label.eks.amazonaws.com/capacityType=FARGATE"
        }
    }'
```

## Step 4 - Running a sidecar container

Sidecar containers can be used to add additional functionality alongside your Spark drivers and/or executors. A common use-case is to forward logs to a centralized logging provider.

For this example, we'll use a custom [Spark Tweeter](https://github.com/dacort/spark-tweeter) container that tweets out when a job starts and stops.

- First, we need to add our Twitter credentials as a Kubernetes secret

```shell
kubectl create secret generic -n emr-jobs twitter-creds \
  --from-literal=consumer_key=${CONSUMER_KEY} \
  --from-literal=consumer_secret=${CONSUMER_SECRET} \
  --from-literal=access_token=${ACCESS_TOKEN} \
  --from-literal=access_token_secret=${ACCESS_TOKEN_SECRET}

```

- Then we create a sidecar yaml file and upload that to S3

```yaml
# tweetcar.yaml
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: side-car-tweeter
    image: ghcr.io/dacort/spark-tweeter:latest
    env:
      - name: CONSUMER_KEY
        valueFrom:
          secretKeyRef:
            name: twitter-creds
            key: consumer_key
      - name: CONSUMER_SECRET
        valueFrom:
          secretKeyRef:
            name: twitter-creds
            key: consumer_secret
      - name: ACCESS_TOKEN
        valueFrom:
          secretKeyRef:
            name: twitter-creds
            key: access_token
      - name: ACCESS_TOKEN_SECRET
        valueFrom:
          secretKeyRef:
            name: twitter-creds
            key: access_token_secret
      - name: EMR_COMMS_MOUNT
        value: /var/log/fluentd
    resources: {}
    volumeMounts:
      - name: emr-container-application-log-dir
        mountPath: /var/log/spark/user
      - name: emr-container-communicate
        mountPath: /var/log/fluentd
```

```shell
aws s3 cp tweetcar.yaml s3://<BUCKET>/artifacts/pod_templates/tweetcar.yaml
```

- Now run your Spark job with the sidecar mounted on the Driver

```shell
aws emr-containers start-job-run \
    --virtual-cluster-id ${EMR_EKS_CLUSTER_ID} \
    --name dacort-tweeter \
    --execution-role-arn ${EMR_EKS_EXECUTION_ARN} \
    --release-label emr-5.33.0-latest \
    --job-driver '{
        "sparkSubmitJobDriver": {
            "entryPoint": "s3://'${S3_BUCKET}'/code/pyspark/windy_city.py",
            "sparkSubmitParameters": "--conf spark.executor.instances=20 --conf spark.executor.memory=2G --conf spark.executor.cores=2 --conf spark.driver.cores=1 --conf spark.kubernetes.driver.podTemplateFile=s3://'${S3_BUCKET}'/artifacts/pod_templates/tweetcar.yaml"
        }
    }'
```