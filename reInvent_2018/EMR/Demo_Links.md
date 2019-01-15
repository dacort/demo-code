# Demo Links

Replace `damons-reinvent-demo` with your own S3 bucket. 😃

## Presto Cluster

This is an example template that can be used to create a new Presto Product in the Service Catalog.

https://damons-reinvent-demo.s3.amazonaws.com/reinvent/cloudformation/Presto_Cluster.cf.yml

## Spark Converter

Copy and paste the below into Job Parameters

s3://damons-reinvent-demo/reinvent/scripts/spark_converter.py
s3://amazon-reviews-pds/tsv/amazon_reviews_us_Toys_v1_00.tsv.gz
s3://damons-reinvent-demo/reinvent/spark/amazon_reviews/

## Hive Converter

Copy and paste the below into Job Parameters

s3://damons-reinvent-demo/reinvent/scripts/hive_converter.sql
-d INPUT=s3://amazon-reviews-pds/tsv/
-d OUTPUT=s3://damons-reinvent-demo/reinvent/hive/query_output/