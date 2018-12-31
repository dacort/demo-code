# Demo Links

## Presto Cluster

https://damons-reinvent-demo.s3.amazonaws.com/reinvent/cloudformation/Presto_Cluster.cf.yml

## Spark Converter

s3://damons-reinvent-demo/reinvent/scripts/spark_converter.py
s3://amazon-reviews-pds/tsv/amazon_reviews_us_Toys_v1_00.tsv.gz
s3://damons-reinvent-demo/reinvent/spark/amazon_reviews/

## Hive Converter

s3://damons-reinvent-demo/reinvent/scripts/hive_converter.sql
-d INPUT=s3://amazon-reviews-pds/tsv/
-d OUTPUT=s3://damons-reinvent-demo/reinvent/hive/query_output/