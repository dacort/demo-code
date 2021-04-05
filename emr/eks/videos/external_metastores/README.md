# EMR on EKS Metastores

## Getting the database connection string

```shell
RDS_SECRETS=$(aws secretsmanager get-secret-value --secret-id 'arn:aws:secretsmanager:us-east-1:123456789012:secret:RDSStackSecret12345' | jq -r '.SecretString' )
RDS_USERNAME=$(echo $RDS_SECRETS | jq -r '.username')
RDS_PASSWORD=$(echo $RDS_SECRETS | jq -r '.password')
RDS_DATABASE=$(echo $RDS_SECRETS | jq -r '.dbname')
RDS_HOSTNAME=$(echo $RDS_SECRETS | jq -r '.host')
RDS_STRING="jdbc:mysql://${RDS_HOSTNAME}:3306/${RDS_DATABASE}"
```

## Get the connector jar

```shell
curl -O https://downloads.mariadb.com/Connectors/java/latest/mariadb-java-client-2.3.0.jar
aws s3 cp mariadb-java-client-2.3.0.jar s3://${S3_BUCKET}/artifacts/jars/       
```


## Try to run the code

```shell
aws emr-containers start-job-run \
    --virtual-cluster-id ${EMR_EKS_CLUSTER_ID} \
    --name dacort-hive \
    --execution-role-arn ${EMR_EKS_EXECUTION_ARN} \
    --release-label emr-6.2.0-latest \
    --job-driver '{
        "sparkSubmitJobDriver": {
            "entryPoint": "s3://'${S3_BUCKET}'/code/pyspark/hivejdbc.py",
            "sparkSubmitParameters": "--jars s3://'${S3_BUCKET}'/artifacts/jars/mariadb-java-client-2.3.0.jar --conf spark.hadoop.javax.jdo.option.ConnectionDriverName=org.mariadb.jdbc.Driver --conf spark.hadoop.javax.jdo.option.ConnectionUserName='${RDS_USERNAME}' --conf spark.hadoop.javax.jdo.option.ConnectionPassword='${RDS_PASSWORD}' --conf spark.hadoop.javax.jdo.option.ConnectionURL='${RDS_STRING}' --conf spark.driver.cores=1 --conf spark.executor.memory=2G --conf spark.driver.memory=2G --conf spark.executor.cores=2 --conf spark.executor.instances=5"
        }
    }' \
    --configuration-overrides '{
        "monitoringConfiguration": {
            "cloudWatchMonitoringConfiguration": { "logGroupName": "/aws/eks/dacort-emr/eks-spark", "logStreamNamePrefix": "hive" }
        }
    }'
```

https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/$252Faws$252Feks$252Fdacort-emr$252Feks-spark$3FlogStreamNameFilter$3Dhive

## Glue


```shell
aws emr-containers start-job-run \
    --virtual-cluster-id ${EMR_EKS_CLUSTER_ID} \
    --name dacort-glue \
    --execution-role-arn ${EMR_EKS_EXECUTION_ARN} \
    --release-label emr-6.2.0-latest \
    --job-driver '{
        "sparkSubmitJobDriver": {
            "entryPoint": "s3://'${S3_BUCKET}'/code/pyspark/gluespark.py",
            "sparkSubmitParameters": "--conf spark.driver.cores=1 --conf spark.executor.memory=1G --conf spark.driver.memory=1G --conf spark.executor.cores=1 --conf spark.executor.instances=1"

        }
    }' \
    --configuration-overrides '{
        "applicationConfiguration": [
            {
                "classification": "spark-defaults",
                "properties": {
                    "spark.hadoop.hive.metastore.client.factory.class": "com.amazonaws.glue.catalog.metastore.AWSGlueDataCatalogHiveClientFactory"
                }
            }
        ],
        "monitoringConfiguration": {
            "cloudWatchMonitoringConfiguration": {
                "logGroupName": "/aws/eks/dacort-emr/eks-spark",
                "logStreamNamePrefix": "glue-cat"
            }
        }
    }'
```