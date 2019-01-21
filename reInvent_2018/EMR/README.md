# re:Invent 2018 EMR Demos

Preparation notes from my 2018 AWS re:Invent EMR Demo ([slides](https://slideshare.net/AmazonWebServices/a-deep-dive-into-whats-new-with-amazon-emr-ant340r1-aws-reinvent-2018) and [video](https://www.youtube.com/watch?v=ISl9sTzxoSo)).

- [Demo 1](https://youtu.be/ISl9sTzxoSo?t=2284): AWS Service Catalog for easy provisioning
- [Demo 2](https://www.youtube.com/watch?v=ISl9sTzxoSo&feature=youtu.be&t=3238): EMR Notebook creation and usage

## Requirements

- AWS CLI installed and configured
- System utilites: make, tempfile, sed, find
  - Tested on macOS Sierra (10.12.6) and Amazon Linux 2

## Usage

1. Gather some information you need for the demo:
   1. Subnet ID to launch the cluster in
   2. IAM user, group, or role to grant access to
   3. SSH key name for the EMR clusters
   4. Bucket name used above

2. Run `create_sc_entries.sh`, this will perform several steps:
   1. Upload required assets to the S3 bucket you specify
   2. Create Service Catalog Portfolio and 2 sample Products
   3. Create several revisions of the "Data Analyst" product
   4. Grant Service Catalog access to the specified role

    Feel free to change other settings in [create_sc_entries.sh](create_sc_entries.sh) like the portfolio `display-name` or `provider-name`.

    ```shell
    TARGET_SUBNET=subnet-abcd \
    TARGET_GRANTEE=role/roleName \
    CLUSTER_SSH_KEY=keyname \
    BUCKET_NAME=bucket_name \
    sh create_sc_entries.sh
    ```

3. See [Demo_Links.md](Demo_Links.md) for example Job Parameters you can provide to the Spark and Hive Job Types in the Data Analyst EMR.


## Pre-Talk Checklist

### Demo 1
- [ ] Verify Security Group Access for SSH
- [ ] Create Demo Hive Cluster (see [below](#prep-service-catalog-clusters))
- [ ] Create Demo Spark Cluster (see [below](#prep-service-catalog-clusters))
- [ ] [S3 Bucket](https://s3.console.aws.amazon.com/s3/buckets/damons-reinvent-demo/reinvent/?region=us-east-1&tab=overview) window
- [ ] Service Catalog window
- [ ] Pending CodePipeline Approval
- [ ] [Demo Links](Demo_Links.md) file
- [ ] Example [hive](assets/scripts/hive_converter.sql), [spark](assets/scripts/spark_converter.py) scripts and [Presto](assets/cloudformation/Presto_Cluster.cf.yml) template.

### Demo 2
- [ ] Window for demoing auto-cluster creation
- [ ] Spin up 1 Notebook cluster - https://console.aws.amazon.com/elasticmapreduce/home
- [ ] Attach Notebook to a cluster - https://console.aws.amazon.com/elasticmapreduce/home#notebooks-list:
- [ ] Have "Create notebook window" open and filled out
- [ ] Clear notebook pre-populated from [notebook_code](assets/notebook_code.md)
- [ ] Pre-compute other notebook (just in case)

## Prep Service Catalog Clusters

```shell
SC_PRODUCT_ID=prod-XXXX
SC_ARTIFACT_ID=pa-XXXX

aws --region us-east-1 servicecatalog provision-product --product-id ${SC_PRODUCT_ID} --provisioning-artifact-id ${SC_ARTIFACT_ID} --provisioned-product-name damons-spark-cluster --provisioning-parameters Key=ClusterName,Value=damons-spark-cluster Key=ComputeRequirements,Value=CPU "Key=JobArtifacts,Value=s3://damons-reinvent-demo/reinvent/scripts/spark_converter.py s3://amazon-reviews-pds/tsv/amazon_reviews_us_Toys_v1_00.tsv.gz s3://damons-reinvent-demo/reinvent/spark/amazon_reviews/" Key=JobType,Value=Spark

aws --region us-east-1 servicecatalog provision-product --product-id ${SC_PRODUCT_ID} --provisioning-artifact-id ${SC_ARTIFACT_ID} --provisioned-product-name damons-hive-cluster --provisioning-parameters Key=ClusterName,Value=damons-hive-cluster Key=ComputeRequirements,Value=Memory "Key=JobArtifacts,Value=s3://damons-reinvent-demo/reinvent/scripts/hive_converter.sql -d INPUT=s3://amazon-reviews-pds/tsv/ -d OUTPUT=s3://damons-reinvent-demo/reinvent/hive/query_output/" Key=JobType,Value=Hive
```

## Script

- Provide overview/user stories 
- As an administrator, I want to let users run Spark scripts on well-defined clusters.
- As a user, I want to be able to provision a cluster and run a simple script without having to worry about how to provision it.
- As an Admin, I can go in and configure EMR, vet the new release, etc
- As a user, I can request an EMR product, choose my memory/cpu profile, and run a script.
- As a user, I can also change my script, and service catalog will only update the Step.
- Hive script takes a couple minutes to run, Spark script too.
- Can also demo interactive use case - browsing with Hue.

So we should have:
1 Spark cluster already up and running
1 Hive cluster already up and running

Do we want to demo different "version" of the product?
- EMR 5.19 upgrade
- GPU upgrade

## TODO

- [ ] Lambda script to terminate service catalog when EMR cluster is done
- [x] Figure out how to choose between Hive/Spark
- [x] Add small/medium/large (or node count) to CF template
- [ ] Script to autoscale notebook cluster for demo?
- [x] Need to figure out console HTTP access

### Conditionals

```yaml
MyAndCondition: !And
  - !Equals ["sg-mysggroup", !Ref "ASecurityGroup"]
  - !Condition SomeOtherCondition
```

## Service catalog

What do we want to provide the user with?

- Select workload profile: Generic | Memory | CPU
    - Have a mapping to M5/R5/C5
- Which application?
    - Hive, Presto, Spark, Zeppelin
- Provide Spark or SQL script
- ~~SSH key~~

## Research

Good conditional Applications mode: 
https://github.com/awslabs/aws-cloudformation-templates/blob/master/aws/services/EMR/EMRClusterWithAdditioanalSecurityGroups.json

Terminating the cluster when done (nevermind, that was data pipeline): 
https://github.com/aws-samples/data-pipeline-samples/blob/master/samples/SparkPiMaximizeResourceAllocation/SparkPi-maximizeResource.json

Existing Service Catalog reference arch: 
https://github.com/aws-samples/aws-service-catalog-reference-architectures/blob/master/emr/sc-emr-ra.yml

Cool demo: 
https://aws.amazon.com/blogs/big-data/implement-continuous-integration-and-delivery-of-apache-spark-applications-using-aws/

^^ Awesome codepipeline demo

```shell
aws --region us-east-1 cloudformation create-stack \
  --template-url https://damons-reinvent-demo.s3.amazonaws.com/reinvent/EMR_Spark_Pipeline.cf.yml \
  --stack-name emr-spark-pipeline \
  --capabilities CAPABILITY_NAMED_IAM
```

## EMR Notebooks

Create test cluster

```shell
aws emr create-cluster --applications Name=Ganglia Name=Spark Name=Zeppelin --ec2-attributes '{"KeyName":"SSH_KEY_NAME","InstanceProfile":"EMR_EC2_DefaultRole","SubnetId":"subnet-XXXX"}' --service-role EMR_DefaultRole --enable-debugging --release-label emr-5.19.0 --log-uri 's3n://aws-logs-AWS_ACCOUNT_ID-us-east-1/elasticmapreduce/' --name 'damons-notebook' --instance-groups '[{"InstanceCount":1,"EbsConfiguration":{"EbsBlockDeviceConfigs":[{"VolumeSpecification":{"SizeInGB":32,"VolumeType":"gp2"},"VolumesPerInstance":1}]},"InstanceGroupType":"MASTER","InstanceType":"c5.2xlarge","Name":"Master Instance Group"},{"InstanceCount":2,"EbsConfiguration":{"EbsBlockDeviceConfigs":[{"VolumeSpecification":{"SizeInGB":32,"VolumeType":"gp2"},"VolumesPerInstance":1}]},"InstanceGroupType":"CORE","InstanceType":"c5.2xlarge","Name":"Core Instance Group"}]' --configurations '[{"Classification":"spark","Properties":{},"Configurations":[]},{"Classification":"spark-hive-site","Properties":{"hive.metastore.client.factory.class":"com.amazonaws.glue.catalog.metastore.AWSGlueDataCatalogHiveClientFactory"},"Configurations":[]}]' --scale-down-behavior TERMINATE_AT_TASK_COMPLETION --region us-east-1
```

Test cluster with Glue data catalog

```shell
aws emr create-cluster --applications Name=Ganglia Name=Spark Name=Hive Name=Hue --ec2-attributes '{"KeyName":"SSH_KEY_NAME","InstanceProfile":"EMR_EC2_DefaultRole","SubnetId":"subnet-XXXX","EmrManagedSlaveSecurityGroup":"sg-XXXX","EmrManagedMasterSecurityGroup":"sg-YYYY"}' --release-label emr-5.19.0 --log-uri 's3n://aws-logs-AWS_ACCOUNT_ID-us-west-2/elasticmapreduce/' --steps '[{"Args":["hive-script","--run-hive-script","--args","-f","s3://damons-reinvent-demo/reinvent/scripts/hive_converter.q","-d","INPUT=s3://amazon-reviews-pds/tsv/","-d","OUTPUT=s3://damons-reinvent-demo/reinvent/hive/query_output/"],"Type":"CUSTOM_JAR","ActionOnFailure":"CONTINUE","Jar":"command-runner.jar","Properties":"","Name":"Hive program"}]' --instance-groups '[{"InstanceCount":4,"EbsConfiguration":{"EbsBlockDeviceConfigs":[{"VolumeSpecification":{"SizeInGB":32,"VolumeType":"gp2"},"VolumesPerInstance":1}]},"InstanceGroupType":"CORE","InstanceType":"r4.2xlarge","Name":"Core Instance Group"},{"InstanceCount":4,"EbsConfiguration":{"EbsBlockDeviceConfigs":[{"VolumeSpecification":{"SizeInGB":32,"VolumeType":"gp2"},"VolumesPerInstance":1}]},"InstanceGroupType":"TASK","InstanceType":"c5.4xlarge","Name":"Task"},{"InstanceCount":1,"EbsConfiguration":{"EbsBlockDeviceConfigs":[{"VolumeSpecification":{"SizeInGB":32,"VolumeType":"gp2"},"VolumesPerInstance":1}]},"InstanceGroupType":"MASTER","InstanceType":"r4.2xlarge","Name":"Master Instance Group"}]' --configurations '[{"Classification":"hive-site","Properties":{"hive.metastore.client.factory.class":"com.amazonaws.glue.catalog.metastore.AWSGlueDataCatalogHiveClientFactory"},"Configurations":[]},{"Classification":"spark-hive-site","Properties":{"hive.metastore.client.factory.class":"com.amazonaws.glue.catalog.metastore.AWSGlueDataCatalogHiveClientFactory"},"Configurations":[]}]' --auto-scaling-role EMR_AutoScaling_DefaultRole --ebs-root-volume-size 10 --service-role EMR_DefaultRole --enable-debugging --name 'damons-spark-redemo' --scale-down-behavior TERMINATE_AT_TASK_COMPLETION --region us-west-2
```

### Test cluster demo account

Cluster with autoscaling Spot

```shell
aws emr create-cluster --termination-protected --applications Name=Hadoop Name=Spark Name=Livy --ec2-attributes '{"KeyName":"SSH_KEY_NAME","InstanceProfile":"EMR_EC2_DefaultRole","SubnetId":"subnet-XXXX","EmrManagedSlaveSecurityGroup":"sg-YYYY","EmrManagedMasterSecurityGroup":"sg-XXXX"}' --release-label emr-5.18.0 --log-uri 's3n://aws-logs-AWS_ACCOUNT_ID-us-west-2/elasticmapreduce/' --instance-groups '[{"InstanceCount":2,"EbsConfiguration":{"EbsBlockDeviceConfigs":[{"VolumeSpecification":{"SizeInGB":32,"VolumeType":"gp2"},"VolumesPerInstance":1}]},"InstanceGroupType":"CORE","InstanceType":"m5.xlarge","Name":"Core - 2"},{"InstanceCount":2,"BidPrice":"OnDemandPrice","AutoScalingPolicy":{"Constraints":{"MinCapacity":0,"MaxCapacity":10},"Rules":[{"Action":{"SimpleScalingPolicyConfiguration":{"ScalingAdjustment":1,"CoolDown":300,"AdjustmentType":"CHANGE_IN_CAPACITY"}},"Description":"","Trigger":{"CloudWatchAlarmDefinition":{"MetricName":"YARNMemoryAvailablePercentage","ComparisonOperator":"LESS_THAN","Statistic":"AVERAGE","Period":300,"Dimensions":[{"Value":"${emr.clusterId}","Key":"JobFlowId"}],"EvaluationPeriods":1,"Unit":"PERCENT","Namespace":"AWS/ElasticMapReduce","Threshold":15}},"Name":"Default-scale-out-1"},{"Action":{"SimpleScalingPolicyConfiguration":{"ScalingAdjustment":1,"CoolDown":300,"AdjustmentType":"CHANGE_IN_CAPACITY"}},"Description":"","Trigger":{"CloudWatchAlarmDefinition":{"MetricName":"ContainerPendingRatio","ComparisonOperator":"GREATER_THAN","Statistic":"AVERAGE","Period":300,"Dimensions":[{"Value":"${emr.clusterId}","Key":"JobFlowId"}],"EvaluationPeriods":1,"Unit":"COUNT","Namespace":"AWS/ElasticMapReduce","Threshold":0.75}},"Name":"Default-scale-out-2"},{"Action":{"SimpleScalingPolicyConfiguration":{"ScalingAdjustment":-1,"CoolDown":300,"AdjustmentType":"CHANGE_IN_CAPACITY"}},"Description":"","Trigger":{"CloudWatchAlarmDefinition":{"MetricName":"YARNMemoryAvailablePercentage","ComparisonOperator":"GREATER_THAN","Statistic":"AVERAGE","Period":300,"Dimensions":[{"Value":"${emr.clusterId}","Key":"JobFlowId"}],"EvaluationPeriods":1,"Unit":"PERCENT","Namespace":"AWS/ElasticMapReduce","Threshold":75}},"Name":"Default-scale-in"}]},"EbsConfiguration":{"EbsBlockDeviceConfigs":[{"VolumeSpecification":{"SizeInGB":32,"VolumeType":"gp2"},"VolumesPerInstance":1}]},"InstanceGroupType":"TASK","InstanceType":"r5.2xlarge","Name":"Task - 3"},{"InstanceCount":1,"EbsConfiguration":{"EbsBlockDeviceConfigs":[{"VolumeSpecification":{"SizeInGB":32,"VolumeType":"gp2"},"VolumesPerInstance":1}]},"InstanceGroupType":"MASTER","InstanceType":"m5.xlarge","Name":"Master - 1"}]' --configurations '[{"Classification":"spark-hive-site","Properties":{"hive.metastore.client.factory.class":"com.amazonaws.glue.catalog.metastore.AWSGlueDataCatalogHiveClientFactory"},"Configurations":[]}]' --auto-scaling-role EMR_AutoScaling_DefaultRole --ebs-root-volume-size 10 --service-role EMR_DefaultRole --enable-debugging --name 'damons-notebook' --scale-down-behavior TERMINATE_AT_TASK_COMPLETION --region us-west-2
```

## Recommender

Various useful links for building a product recommendation engine.

- https://hub.packtpub.com/building-recommendation-engine-spark/
- https://mapr.com/ebooks/spark/08-recommendation-engine-spark.html
- https://jaceklaskowski.gitbooks.io/mastering-apache-spark/spark-mllib/spark-mllib-ALSModel.html
- https://spark.apache.org/docs/2.2.0/ml-collaborative-filtering.html
- https://spark.apache.org/docs/2.3.2/ml-collaborative-filtering.html
- https://aws.amazon.com/blogs/big-data/building-a-recommendation-engine-with-spark-ml-on-amazon-emr-using-zeppelin/
- https://databricks.com/blog/2014/07/23/scalable-collaborative-filtering-with-spark-mllib.html
- https://spark.apache.org/docs/latest/ml-collaborative-filtering.html

## Transient clusters

Quick-create link

https://us-west-2.console.aws.amazon.com/cloudformation/home?region=us-west-2#/stacks/quickcreate?templateUrl=https%3A%2F%2Fdamons-reinvent-demo.s3.amazonaws.com%2Freinvent%2Fcloudformation%2FSpark_cluster.cf.yml&stackName=damon-convert&param_ClusterName=damon-converter&param_ComputeRequirements=Memory&param_JobArtifacts=s3%3A%2F%2Fdamons-reinvent-demo%2Freinvent%2Fscripts%2Fspark_converter.py%20s3%3A%2F%2Famazon-reviews-pds%2Ftsv%2Famazon_reviews_us_Toys_v1_00.tsv.gz%20s3%3A%2F%2Fdamons-reinvent-demo%2Freinvent%2Famazon_reviews%2F&param_JobType=Spark

Can do local testing in `~/src/random/spark-scratch`

## Provision Service Catalog via API

### Initial Research

```
❯ aws servicecatalog describe-product --id prod-XXXX
{
    "ProductViewSummary": {
        "Name": "EMR",
        "HasDefaultPath": false,
        "ShortDescription": "EMR Clusters",
        "Owner": "damon",
        "SupportEmail": "damon@",
        "Type": "CLOUD_FORMATION_TEMPLATE",
        "Id": "prodview-XXXX",
        "ProductId": "prod-XXXX"
    },
    "ProvisioningArtifacts": [
        {
            "CreatedTime": 1539887461.0,
            "Description": "",
            "Id": "pa-XXXX",
            "Name": "Initial revision"
        },
        {
            "CreatedTime": 1542411605.0,
            "Description": "Added Spark support on EMR 5.19",
            "Id": "pa-YYYY",
            "Name": "EMR 5.19 Release"
        }
    ]
}
```


```
❯ aws servicecatalog describe-provisioning-artifact --provisioning-artifact-id pa-XXXX --product-id prod-XXXX
{
    "ProvisioningArtifactDetail": {
        "Description": "",
        "Active": true,
        "CreatedTime": 1539887461.0,
        "Type": "CLOUD_FORMATION_TEMPLATE",
        "Id": "pa-XXXX",
        "Name": "Initial revision"
    },
    "Info": {
        "TemplateUrl": "https://s3.amazonaws.com/cf-templates-HASH-us-west-2/servicecatalog-product-HASH-emr_streaming.cf.yaml"
    },
    "Status": "AVAILABLE"
}

❯ aws servicecatalog describe-provisioning-artifact --provisioning-artifact-id pa-YYYY --product-id prod-XXXX
{
    "ProvisioningArtifactDetail": {
        "Description": "Added Spark support on EMR 5.19",
        "Active": true,
        "CreatedTime": 1542411605.0,
        "Type": "CLOUD_FORMATION_TEMPLATE",
        "Id": "pa-YYYY",
        "Name": "EMR 5.19 Release"
    },
    "Info": {
        "TemplateUrl": "https://damons-reinvent-demo.s3.amazonaws.com/reinvent/cloudformation/Spark_cluster.cf.yml"
    },
    "Status": "AVAILABLE"
}
```

```
❯ aws servicecatalog list-principals-for-portfolio --portfolio-id port-XXXX
{
    "Principals": [
        {
            "PrincipalType": "IAM",
            "PrincipalARN": "arn:aws:iam::AWS_ACCOUNT_ID:group/Administrators"
        },
        {
            "PrincipalType": "IAM",
            "PrincipalARN": "arn:aws:iam::AWS_ACCOUNT_ID:role/admin"
        }
    ]
}
```

```
❯ aws servicecatalog describe-product --id prod-YYYY --region us-west-2
{
    "ProductViewSummary": {
        "Name": "Data Analyst EMR",
        "HasDefaultPath": false,
        "ShortDescription": "Provides Hive, Spark, and Hue for interactive queries.",
        "Owner": "@dacort",
        "Type": "CLOUD_FORMATION_TEMPLATE",
        "Id": "prodview-YYYY",
        "ProductId": "prod-YYYY"
    },
    "ProvisioningArtifacts": [
        {
            "CreatedTime": 1542648509.0,
            "Description": "",
            "Id": "pa-1111",
            "Name": "Initial revision"
        },
        {
            "CreatedTime": 1542650131.0,
            "Id": "pa-2222",
            "Name": "Updated security settings"
        },
        {
            "CreatedTime": 1542667146.0,
            "Id": "pa-3333",
            "Name": "Updated parameters"
        },
        {
            "CreatedTime": 1542745216.0,
            "Id": "pa-4444",
            "Name": "Choose your own cluster size!"
        },
        {
            "CreatedTime": 1543170484.0,
            "Id": "pa-5555",
            "Name": "Auto-terminate functionality"
        }
    ]
}
```

### Creation

- Update settings specific to region

```shell
TARGET_SUBNET=subnet-XXXX
TARGET_GRANTEE=role/Admin
TARGET_SSH_KEY=keyname

sed -i '' "s/Ec2SubnetId:.*/Ec2SubnetId: \"${TARGET_SUBNET}\"/" assets/cloudformation/Spark_Cluster_Versions/*
make
```

- Create Portfolio

```shell
aws --region us-east-1 servicecatalog create-portfolio --display-name "EMR re:Invent Demo" --provider-name "@dacort" --description "Pre-defined on-demand EMR clusters" | tee /tmp/out
PORTFOLIO_ID=$(jq -r '.PortfolioDetail.Id' /tmp/out)
```

```json
{
    "PortfolioDetail": {
        "DisplayName": "EMR re:Invent Demo",
        "Description": "Pre-defined on-demand EMR clusters",
        "ProviderName": "@dacort",
        "CreatedTime": 1543197065.083,
        "Id": "port-XXXX",
        "ARN": "arn:aws:catalog:us-east-1:AWS_ACCOUNT_ID:portfolio/port-XXXX"
    }
}
```

- Create Product

```shell
aws --region us-east-1 servicecatalog create-product --name "Data Analyst EMR" \
    --owner "@dacort" \
    --description "Provides Hive, Spark, and Hue for interactive queries." \
    --product-type CLOUD_FORMATION_TEMPLATE \
    --provisioning-artifact-parameters '{"Name":"Initial revision", "Description": "", "Info":{"LoadTemplateFromURL":"https://s3.amazonaws.com/damons-reinvent-demo/reinvent/cloudformation/Spark_Cluster_Versions/v0_Initial_Revision.cf.yml"},"Type":"CLOUD_FORMATION_TEMPLATE"}' | tee /tmp/out
PRODUCT_ID=$(jq -r '.ProductViewDetail.ProductViewSummary.ProductId' /tmp/out)
```

```json
{
    "ProductViewDetail": {
        "ProductViewSummary": {
            "Name": "Data Analyst EMR",
            "HasDefaultPath": false,
            "ShortDescription": "Provides Hive, Spark, and Hue for interactive queries.",
            "Owner": "@dacort",
            "Type": "CLOUD_FORMATION_TEMPLATE",
            "Id": "prodview-XXXX",
            "ProductId": "prod-XXXX"
        },
        "Status": "CREATED",
        "ProductARN": "arn:aws:catalog:us-east-1:AWS_ACCOUNT_ID:product/prod-XXXX",
        "CreatedTime": 1543200874.0
    },
    "ProvisioningArtifactDetail": {
        "Description": "",
        "Active": true,
        "CreatedTime": 1543200874.0,
        "Type": "CLOUD_FORMATION_TEMPLATE",
        "Id": "pa-XXXX",
        "Name": "Initial revision"
    }
}
```

- Connect product to portfolio

```shell
aws --region us-east-1 servicecatalog associate-product-with-portfolio --product-id ${PRODUCT_ID} --portfolio-id ${PORTFOLIO_ID}
```

- Add different product revisions

```shell
VERSIONS=( "Updated security setting:v1_Security_Settings"
        "Updated parameter labels:v2_Updated_Parameters"
        "Choose your own cluster size\!:v3_Cluster_Size"
        "Auto-terminate functionality:v4_Auto_Terminate" )

for version in "${VERSIONS[@]}" ; do
    NAME=${version%%:*}
    TEMPLATE=${version#*:}
    aws --region us-east-1 servicecatalog create-provisioning-artifact --product-id ${PRODUCT_ID} --parameters '{"Name":"'${NAME}'", "Description": "", "Info":{"LoadTemplateFromURL":"https://s3.amazonaws.com/damons-reinvent-demo/reinvent/cloudformation/Spark_Cluster_Versions/'${TEMPLATE}'.cf.yml"},"Type":"CLOUD_FORMATION_TEMPLATE"}'
done
```

- Grant access to the portfolio

```shell
aws --region us-east-1 servicecatalog associate-principal-with-portfolio --portfolio-id ${PORTFOLIO_ID} --principal-type IAM --principal-arn arn:aws:iam::$(aws --region us-east-1 sts get-caller-identity --query Account --output text):${TARGET_GRANTEE}
```

## Codepipeline

```shell
aws cloudformation create-stack \
  --template-url https://s3.amazonaws.com/damons-reinvent-demo/reinvent/EMR_Spark_Pipeline.cf.yml \
  --stack-name emr-spark-pipeline \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-west-2
```

## Other Products

## Apache Flink

- https://stackoverflow.com/questions/52638193/streaming-to-parquet-files-not-happy-with-flink-1-6-1
- https://github.com/jose1003/flinkparquet
- https://ci.apache.org/projects/flink/flink-docs-release-1.2/dev/batch/index.html
```java
// read a CSV file with three fields
DataSet<Tuple3<String, String, String>> csvInput = env.readCsvFile("s3://amazon-reviews-pds/tsv/amazon_reviews_us_Toys_v1_00.tsv.gz")
	                       .types(String.class, String.class, String.class);

// read a CSV file with three fields into a POJO (Person.class) with corresponding fields
DataSet<Person>> csvInput = env.readCsvFile("hdfs:///the/CSV/file")
                         .pojoType(Person.class, "name", "age", "zipcode");
// fieldDelimiter
```
