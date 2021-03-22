# EMR on EKS Demo

## Spin up an EMR on EC2 Cluster

Typically with EMR you figure out the following:

- The EMR version you want to run
- The VPC/Subnet to run your cluster in
- The SSH keypair to use
- The S3 bucket to send your cluster logs to
- The different applications to run on the cluster
- The instance types, count, and configuration

The command below spins up a cluster in `us-east-1` with Spark on EMR 5.32.0

```shell
VERSION=emr-5.32.0
KEYPAIR=<keypair_name>
SUBNET_ID=<subnet_id>
LOG_BUCKET=<logs_bucket>

aws emr create-cluster --applications Name=Spark Name=Zeppelin \
    --ec2-attributes '{"KeyName":"'${KEYPAIR}'","InstanceProfile":"EMR_EC2_DefaultRole","SubnetId":"'${SUBNET_ID}'"}' \
    --service-role EMR_DefaultRole \
    --enable-debugging \
    --release-label ${VERSION} \
    --log-uri "s3n://${LOG_BUCKET}/elasticmapreduce/" \
    --name 'dacort-spark' \
    --instance-groups '[{"InstanceCount":1,"EbsConfiguration":{"EbsBlockDeviceConfigs":[{"VolumeSpecification":{"SizeInGB":32,"VolumeType":"gp2"},"VolumesPerInstance":2}]},"InstanceGroupType":"MASTER","InstanceType":"m5.xlarge","Name":"Master Instance Group"},{"InstanceCount":2,"EbsConfiguration":{"EbsBlockDeviceConfigs":[{"VolumeSpecification":{"SizeInGB":32,"VolumeType":"gp2"},"VolumesPerInstance":2}]},"InstanceGroupType":"CORE","InstanceType":"m5.xlarge","Name":"Core Instance Group"}]' \
    --configurations '[{"Classification":"spark","Properties":{}}]' \
    --scale-down-behavior TERMINATE_AT_TASK_COMPLETION \
    --region us-east-1
```

So...let's take a quick look at some data and see what it takes to run analysis on EMR on EKS. 👇

## Explore a dataset

Idea: "What was the max wind speed in Seattle in 2021?" or "Average hourly rainfall when there was rain"

We can use the [NOAA Integrated Surface Database](https://registry.opendata.aws/noaa-isd/) hourly data in CSV format.

```shell
aws s3 ls s3://noaa-global-hourly-pds/2021/ --no-sign-request
```

See the code in [`windy_city.py`](./windy_city.py`) for a full example.

<details>
    <summary>Here is exploratory code we can use in a <code>pyspark</code> shell once we've SSH'ed into our EMR cluster.</summary>

```python
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType

# Reads the 2021 ISD data
df = spark.read.format("csv") \
        .option("header", "true")\
        .option("inferSchema", "true") \
        .load("s3://noaa-global-hourly-pds/2021/")

# Shows a sample row from Seattle
df \
    .withColumn('LATITUDE', df.LATITUDE.cast(DoubleType())) \
    .withColumn('LONGITUDE', df.LONGITUDE.cast(DoubleType())) \
    .filter(df.LATITUDE >= 47.41).filter(df.LATITUDE <= 47.49) \
    .filter(df.LONGITUDE >= -122.48).filter(df.LONGITUDE <= -122.16) \
    .take(1)


# See if we can split the wind speed properly
seadf = df \
    .withColumn('LATITUDE', df.LATITUDE.cast(DoubleType())) \
    .withColumn('LONGITUDE', df.LONGITUDE.cast(DoubleType())) \
    .filter(df.LATITUDE >= 47.41).filter(df.LATITUDE <= 47.49) \
    .filter(df.LONGITUDE >= -122.48).filter(df.LONGITUDE <= -122.16)

seadf.select("DATE", "NAME", "WND") \
    .withColumn("windSpeed", F.split(df.WND, ",")[3].cast(DoubleType())/10 ) \
    .take(10)
# [Row(DATE='2021-01-01T00:00:00', NAME='SEATTLE TACOMA AIRPORT, WA US', WND='200,1,N,0046,1', windSpeed=4.6), Row(DATE='2021-01-01T00:17:00', NAME='SEATTLE TACOMA AIRPORT, WA US', WND='200,5,N,0041,5', windSpeed=4.1), Row(DATE='2021-01-01T00:37:00', NAME='SEATTLE TACOMA AIRPORT, WA US', WND='170,5,N,0031,5', windSpeed=3.1), Row(DATE='2021-01-01T00:53:00', NAME='SEATTLE TACOMA AIRPORT, WA US', WND='190,5,N,0041,5', windSpeed=4.1), Row(DATE='2021-01-01T01:53:00', NAME='SEATTLE TACOMA AIRPORT, WA US', WND='190,5,N,0051,5', windSpeed=5.1), Row(DATE='2021-01-01T02:39:00', NAME='SEATTLE TACOMA AIRPORT, WA US', WND='180,5,N,0041,5', windSpeed=4.1), Row(DATE='2021-01-01T02:53:00', NAME='SEATTLE TACOMA AIRPORT, WA US', WND='180,5,N,0041,5', windSpeed=4.1), Row(DATE='2021-01-01T03:32:00', NAME='SEATTLE TACOMA AIRPORT, WA US', WND='190,5,N,0036,5', windSpeed=3.6), Row(DATE='2021-01-01T03:53:00', NAME='SEATTLE TACOMA AIRPORT, WA US', WND='190,5,N,0041,5', windSpeed=4.1), Row(DATE='2021-01-01T04:49:00', NAME='SEATTLE TACOMA AIRPORT, WA US', WND='180,5,N,0031,5', windSpeed=3.1)]

# OK, now create our slim dataframe and get top wind speed per day
wind_date_df = seadf.select("DATE", "NAME", "WND") \
    .withColumn("windSpeed", F.split(df.WND, ",")[3].cast(DoubleType())/10 ) \
    .withColumn("ymd", F.split(df.DATE, "T")[0]) \
    .filter(seadf.windSpeed != 999.9)

wind_date_df.groupBy("ymd") \
    .agg({'windSpeed':'max'}) \
    .orderBy("ymd") \
    .show()
```

</details>

And the output...

```
>>> wind_date_df.groupBy("ymd").agg({'windSpeed':'max'}).orderBy("ymd").show()
+----------+--------------+
|       ymd|max(windSpeed)|
+----------+--------------+
|2021-01-01|           9.3|
|2021-01-02|          10.3|
|2021-01-03|          10.3|
|2021-01-04|           8.2|
|2021-01-05|           9.8|
|2021-01-06|           8.2|
|2021-01-07|           4.6|
|2021-01-08|           8.8|
|2021-01-09|           6.2|
|2021-01-10|           7.2|
|2021-01-11|          10.3|
|2021-01-12|           6.7|
|2021-01-13|          13.9|
+----------+--------------+
```

👏

## EMR on EKS

### EKS Setup

First we need to have an EKS cluster already running with the EMR namespace configured. If you don't already have an EKS cluster running, you'll likely need Admin access to your account to get this all set up.

You can follow the [EMR on EKS Getting started guide](https://docs.aws.amazon.com/emr/latest/EMR-on-EKS-DevelopmentGuide/getting-started.html).

A couple notes:

- When creating the [job execution role](https://docs.aws.amazon.com/emr/latest/EMR-on-EKS-DevelopmentGuide/creating-job-execution-role.html), select `Another AWS account` as the trusted entity and use your Account ID.
- You will need to create a Node Group for Fargate profile for the namespace you created in EMR for the jobs to run.

As an example for #2 above, I created an EKS Fargate-only cluster and had to run the following command to create the desired profile:

```shell
eksctl create fargateprofile \
    --cluster <EKS_CLUSTER> \
    --name emr-profile \
    --namespace <EMR_VIRTUAL_CLUSTER_NAMESPACE>
```

## EMR Setup

Now that you've got a running EKS cluster(!), configured your execution roles and created an EMR Virtual Cluster that's mapped to EKS 😅  go ahead and upload your code to S3 and run a job!

```shell
S3_BUCKET=<YOUR_S3_BUCKET>
aws s3 cp windy_city.py s3://${S3_BUCKET}/code/pyspark/windy_city.py
```

Fill in your EMR on EKS Cluster ID and Execution role. I've configured this job to log to S3, but you can also use CloudFront as noted in [EMR EKS Job Parameters](https://docs.aws.amazon.com/emr/latest/EMR-on-EKS-DevelopmentGuide/emr-eks-jobs-CLI.html#emr-eks-jobs-parameters). Just make sure your execution role has the right permissions.

```shell
S3_BUCKET=<YOUR_S3_BUCKET>
EMR_EKS_CLUSTER_ID=<EMR_VIRTUAL_CLUSTER_ID>
EMR_EKS_EXECUTION_ROLE=arn:aws:iam::<ACCOUNT_ID>:role/<EMR_EKS_ROLE_NAME>

aws emr-containers start-job-run \
    --virtual-cluster-id ${EMR_EKS_CLUSTER_ID} \
    --name dacort-windycity \
    --execution-role-arn ${EMR_EKS_EXECUTION_ROLE} \
    --release-label emr-5.32.0-latest \
    --job-driver '{
        "sparkSubmitJobDriver": {
            "entryPoint": "s3://'${S3_BUCKET}'/code/pyspark/windy_city.py",
            "sparkSubmitParameters": "--conf spark.executor.instances=2 --conf spark.executor.memory=2G --conf spark.executor.cores=2 --conf spark.driver.cores=1"
        }
    }' \
    --configuration-overrides '{
        "monitoringConfiguration": {
            "s3MonitoringConfiguration": { "logUri": "s3://'${S3_BUCKET}'/emr-eks-logs/windy_city" }
        }
    }'
```

That command should spin up your Spark job on EKS and write the output to S3! 🙌

You should see the top wind speed per day in your Spark driver `stdout.gz` file on S3 after the job finishes.

- Want to run it on EMR 6.2.0? Change `--release-label` to `emr-6.2.0-latest`
- Want to run the windy city script for San Francisco? Add `"entryPointArguments": ["-123.18,37.64,-122.28,37.93"]` to the `sparkSubmitJobDriver` JSON

## Cleanup

1. Make sure you don't have any managed endpoints for EMR Studio

```shell
# List existing managed endpoints for your virtual cluster
aws emr-containers list-managed-endpoints \
    --virtual-cluster-id ${EMR_EKS_CLUSTER_ID} \
    --output text \
    --query 'endpoints[*].[id,state,name]'

# Delete them if you do
for endpoint_id in $(aws emr-containers list-managed-endpoints --virtual-cluster-id ${EMR_EKS_CLUSTER_ID} --output text --query 'endpoints[*].[id]'); do
    echo "Deleting ${endpoint_id}"
    aws emr-containers delete-managed-endpoint \
        --id ${endpoint_id} \
        --virtual-cluster-id ${EMR_EKS_CLUSTER_ID} 
done
```

2. Delete the virtual cluster

```shell
aws emr-containers delete-virtual-cluster --id ${EMR_EKS_CLUSTER_ID}
```