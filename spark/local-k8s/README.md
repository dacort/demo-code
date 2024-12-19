# Spark on Local Kubernetes

This is a demo of how to get Spark up and running with a local (KIND) Kubernetes environment.


## Pre-requisites

- [KIND](https://kind.sigs.k8s.io/)
- Docker, `kubectl`, `helm`

## Install and start KIND

```bash
kind create cluster --config kind-config.yaml
kubectl cluster-info --context kind-kind
```

```
❯ kubectl cluster-info --context kind-kind
Kubernetes control plane is running at https://127.0.0.1:61563
CoreDNS is running at https://127.0.0.1:61563/api/v1/namespaces/kube-system/services/kube-dns:dns/proxy

To further debug and diagnose cluster problems, use 'kubectl cluster-info dump'.
```

By default, `kind` adds the cluster info to your `~/.kube/config` file. If you need to get it later (maybe your config got updated), you can always use something like this:

```bash
kind get kubeconfig > ~/.kube/kind-config
KUBECONFIG=~/.kube/kind-config kubectl get pods
```

### (Optional) Install Official Apache Spark K8s Operator

```bash
helm install spark-kubernetes-operator \
https://nightlies.apache.org/spark/charts/spark-kubernetes-operator-0.1.0-SNAPSHOT.tgz
```

#### uninstall process

```bash
helm uninstall spark-kubernetes-operator
kubectl delete crd sparkapplications.spark.apache.org
kubectl delete crd sparkclusters.spark.apache.org
```

## Verify Installs

```bash
kubectl --context=kind-kind get pods --all-namespaces
```

_remaining commands assume your `kubectl` context is set to `kind-kind`_

```
❯ kubectl --context=kind-kind get pods --all-namespaces
NAMESPACE            NAME                                             READY   STATUS              RESTARTS   AGE
kube-system          coredns-7db6d8ff4d-7x252                         1/1     Running             0          2m36s
kube-system          coredns-7db6d8ff4d-kjk6v                         1/1     Running             0          2m36s
kube-system          etcd-kind-control-plane                          1/1     Running             0          2m52s
kube-system          kindnet-62kqj                                    1/1     Running             0          2m36s
kube-system          kube-apiserver-kind-control-plane                1/1     Running             0          2m51s
kube-system          kube-controller-manager-kind-control-plane       1/1     Running             0          2m51s
kube-system          kube-proxy-ggk2n                                 1/1     Running             0          2m36s
kube-system          kube-scheduler-kind-control-plane                1/1     Running             0          2m51s
local-path-storage   local-path-provisioner-988d74bc-dkc6k            1/1     Running             0          2m36s
spark-operator       spark-operator-7b7b54cf75-8p9jb                  1/1     Running             0          25s
```


## Run a Spark job

```bash
kubectl --context=kind-kind create -f - <<-EOF
apiVersion: spark.apache.org/v1alpha1
kind: SparkApplication
metadata:
  name: pi-python
spec:
  pyFiles: "local:///opt/spark/examples/src/main/python/pi.py"
  sparkConf:
    spark.dynamicAllocation.enabled: "true"
    spark.dynamicAllocation.shuffleTracking.enabled: "true"
    spark.dynamicAllocation.maxExecutors: "3"
    spark.log.structuredLogging.enabled: "false"
    spark.kubernetes.authenticate.driver.serviceAccountName: "spark"
    spark.kubernetes.container.image: "apache/spark:4.0.0-preview2"
  applicationTolerations:
    resourceRetainPolicy: OnFailure
  runtimeVersions:
    sparkVersion: "4.0.0-preview2"
EOF
```

Once the container image downloads and the container starts, you can watch the logs with:

```bash
kubectl logs -f pi-python-0-driver
```

To delete the app, use:

```bash
kubectl delete sparkapp/pi-python
```

## Let's try S3 tables

Per the docs on [S3 tables with Apache Spark](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-tables-integrating-open-source-spark.html).

- Create a table bucket in a region near me

```bash
aws s3tables create-table-bucket \
    --region us-west-2 \
    --name dacort-berg
```

```json
{
    "arn": "arn:aws:s3tables:us-west-2:<YOUR_AWS_ACCOUNT_ID>:bucket/dacort-berg"
}
```

- Spin up a Spark SQL shell

First, we create a persistent pod we can exec into.

```bash
kubectl apply -f spark-shell-pod.yaml
```

Then start up Spark SQL

_note that we assume you already have your AWS CLI setup and can export credentials_

```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export TABLE_BUCKET_NAME=dacort-berg

kubectl exec -it spark-shell-pod -- /bin/bash -c "export AWS_REGION=us-west-2;$(aws configure export-credentials --format env | tr '\n' ';') \
    /opt/spark/bin/spark-sql \
    --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.6.1,software.amazon.awssdk:s3tables:2.29.26,software.amazon.awssdk:s3:2.29.26,software.amazon.awssdk:sts:2.29.26,software.amazon.awssdk:kms:2.29.26,software.amazon.awssdk:glue:2.29.26,software.amazon.awssdk:dynamodb:2.29.26,software.amazon.s3tables:s3-tables-catalog-for-iceberg-runtime:0.1.3 \
    --conf spark.jars.ivy=/opt/spark/work-dir/.ivy2 \
    --conf spark.sql.catalog.s3tablesbucket=org.apache.iceberg.spark.SparkCatalog \
    --conf spark.sql.catalog.s3tablesbucket.catalog-impl=software.amazon.s3tables.iceberg.S3TablesCatalog \
    --conf spark.sql.catalog.s3tablesbucket.warehouse=arn:aws:s3tables:us-west-2:${AWS_ACCOUNT_ID}:bucket/${TABLE_BUCKET_NAME} \
    --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions"
```

- Create a new S3 Table

```sql
CREATE NAMESPACE IF NOT EXISTS s3tablesbucket.default;

CREATE TABLE IF NOT EXISTS s3tablesbucket.default.`demo` 
    ( id INT, name STRING, value INT )
USING iceberg;

INSERT INTO s3tablesbucket.default.demo VALUES (1, 'damon', 33), (2, 'dad', 34);

SELECT * FROM s3tablesbucket.default.demo;
```

```
spark-sql (default)> SELECT * FROM s3tablesbucket.default.demo;
1       damon   33
2       dad     34
Time taken: 3.455 seconds, Fetched 2 row(s)
```

## Reading S3 Tables with other query engines (DuckDB)

The neat(?) thing about S3 Tables is that it's just Iceberg behind the scenes.

So if you use `aws s3tables get-table`, you can find the metadata location:

```bash
 aws s3tables get-table --table-bucket-arn arn:aws:s3tables:us-west-2:${AWS_ACCOUNT_ID}:bucket/${TABLE_BUCKET_NAME} --namespace default --name demo
 ```

 ```json
 {
    "name": "demo",
    "type": "customer",
    "tableARN": "arn:aws:s3tables:us-west-2:<YOUR_AWS_ACCOUNT_ID>:bucket/dacort-berg/table/e0b502d9-5de1-46a4-8633-412b78401be3",
    "namespace": [
        "default"
    ],
    "versionToken": "<SOME_ID>",
    "metadataLocation": "s3://502d9-5de1-46a4-<SOME_OTHER_ID>--table-s3/metadata/00001-e76a727d-8a4d-4883-95c7-dea809f2a4cb.metadata.json",
    "warehouseLocation": "s3://502d9-5de1-46a4-<SOME_OTHER_ID>--table-s3",
    "createdAt": "2024-12-18T21:20:39.347151+00:00",
    "createdBy": "<YOUR_AWS_ACCOUNT_ID>",
    "modifiedAt": "2024-12-18T21:25:22.327612+00:00",
    "ownerAccountId": "<YOUR_AWS_ACCOUNT_ID>",
    "format": "ICEBERG"
}
```

If you take the `metadataLocation` from the response and use that in DuckDB (with the `iceberg`, `httpfs` extensions installed and an [S3 secret created](https://duckdb.org/docs/configuration/secrets_manager.html#temporary-secrets))...it seems to work!

_using duckdb v1.1.3 19864453f7_

```sql
-- Install/load Iceberg and https extensions
-- Set up S3 access to my specific region
INSTALL iceberg;
LOAD iceberg;
INSTALL https;
LOAD https;
CREATE SECRET secret1 (
    TYPE S3,
    PROVIDER CREDENTIAL_CHAIN,
    ENDPOINT 's3.us-west-2.amazonaws.com'
);

-- Query using the metadat file from above!
SELECT count(*)
FROM iceberg_scan('s3://502d9-5de1-46a4-<SOME_OTHER_ID>--table-s3/metadata/00001-e76a727d-8a4d-4883-95c7-dea809f2a4cb.metadata.json');
```

```
┌──────────────┐
│ count_star() │
│    int64     │
├──────────────┤
│            2 │
└──────────────┘
```

```sql
SELECT * FROM iceberg_scan('s3://502d9-5de1-46a4-<SOME_OTHER_ID>--table-s3/metadata/00001-e76a727d-8a4d-4883-95c7-dea809f2a4cb.metadata.json');
```

```
┌───────┬─────────┬───────┐
│  id   │  name   │ value │
│ int32 │ varchar │ int32 │
├───────┼─────────┼───────┤
│     1 │ damon   │    33 │
│     2 │ dad     │    34 │
└───────┴─────────┴───────┘
```

🤯

- What happens if I insert more data?

The `metadataLocation` gets updated and we can, of course, query each different version of the table. 🎉
