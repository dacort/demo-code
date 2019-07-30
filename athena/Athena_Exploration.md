# Athena exploration

Walkthrough of different Athena functionality using the [Amazon Customer Reviews](https://registry.opendata.aws/amazon-reviews/) open dataset.

This dataset provides both TSV and Parquet versions of over 130 million customer reviews since 1995.

## Table Definitions

Create a table in Athena over the TSV dataset. 

```sql
CREATE EXTERNAL TABLE amazon_reviews_tsv(
  marketplace string, 
  customer_id string, 
  review_id string, 
  product_id string, 
  product_parent string, 
  product_title string, 
  product_category string, 
  star_rating int, 
  helpful_votes int, 
  total_votes int, 
  vine string, 
  verified_purchase string, 
  review_headline string, 
  review_body string, 
  review_date date)
ROW FORMAT DELIMITED
  FIELDS TERMINATED BY '\t'
  ESCAPED BY '\\'
  LINES TERMINATED BY '\n'
LOCATION
  's3://amazon-reviews-pds/tsv/'
TBLPROPERTIES ("skip.header.line.count"="1");
```

Run a simple query to preview the data.

```sql
SELECT * FROM "amazon_reviews_tsv"
WHERE marketplace = 'US'
limit 10;
```

Create a table over the Parquet dataset. It's partitioned by `product_category`.

Run a couple aggregation queries to see the amount of data scanned is minimal (kb-mb) compared to the full size of the data on S3 (~50 GiB).

```sql
CREATE EXTERNAL TABLE `amazon_reviews_parquet`(
  `marketplace` string, 
  `customer_id` string, 
  `review_id` string, 
  `product_id` string, 
  `product_parent` string, 
  `product_title` string, 
  `star_rating` int, 
  `helpful_votes` int, 
  `total_votes` int, 
  `vine` string, 
  `verified_purchase` string, 
  `review_headline` string, 
  `review_body` string, 
  `review_date` bigint, 
  `year` int)
PARTITIONED BY ( `product_category` string )
STORED AS PARQUET
LOCATION 's3://amazon-reviews-pds/parquet';
```

```sql
SELECT product_id, product_title, count(*) as num_reviews, avg(star_rating) as avg_stars
FROM amazon_reviews_parquet where product_category='Toys'
GROUP BY 1, 2
ORDER BY 3 DESC
limit 100;

SELECT COUNT(*) FROM amazon_reviews_parquet where product_category='Toys'AND year >= 2012

SELECT * FROM amazon_reviews_parquet 
WHERE product_category='Toys'
LIMIT 100;
```

## CTAS Example

Re-partition by marketplace and year to allow for efficient queries. (This takes ~5 minutes to run),.

By default, the results are stored in a bucket automatically created in your account for Athena output: `aws-athena-query-results-<account_id>-<region>`.

See [Athena CTAS examples](https://docs.aws.amazon.com/athena/latest/ug/ctas-examples.html) for how to specify a specific S3 location with the `external_location` parameter.

```sql
CREATE TABLE amazon_reviews_by_marketplace
WITH (
  format='PARQUET',
  partitioned_by = ARRAY['marketplace', 'year']
) AS
SELECT customer_id, review_id, product_id, product_parent, product_title, product_category, star_rating, helpful_votes, total_votes, verified_purchase, review_headline, review_body, review_date,
  marketplace,
  year(review_date) as year
FROM amazon_reviews_tsv
WHERE "$path" LIKE '%tsv.gz'
-- Run time: 4 minutes 43 seconds, Data scanned: 32.24 GB
```

Show different query times and data scanned

```sql
SELECT product_id, COUNT(*) FROM amazon_reviews_by_marketplace
GROUP BY 1 ORDER BY 2 DESC LIMIT 10
-- Run time: 6.7 seconds, Data scanned: 790.26 MB
```

vs.

```sql
SELECT product_id, COUNT(*) FROM amazon_reviews_by_marketplace
WHERE marketplace='US' AND year = 2013
GROUP BY 1 ORDER BY 2 DESC LIMIT 10
-- Run time: 3.87 seconds, Data scanned: 145 MB
```

## Optimization Techniques

### Sorting by a specific field

If you frequently query data based on an ID and expect a limited amount of data to be returned, you can sort the original dataset by that ID and write it out to a limited number of objects on S3. Athena will use the [parquet metadata](#parquet-metadata) to determine if it should read the underlying data.

One option is to use CTAS to create a derivative dataset and sort on the specific fields. This can take a while to run thanks to the sorting and the execution plan.

```sql
CREATE TABLE amazon_reviews_sorted
WITH (
  format='PARQUET'
) AS
SELECT product_id, customer_id, product_parent, star_rating, helpful_votes, total_votes, verified_purchase, marketplace, product_category, review_date
FROM amazon_reviews_by_marketplace
ORDER BY product_id ASC
-- Run time: 18 minutes 13 seconds, Data scanned: 2.44 GB
```

Note that this only outputs seven heavily-skewed files, but all rows for a specific `product_id` should be in one file.

```sql
SELECT "$path", product_id, COUNT(*) FROM amazon_reviews_sorted
WHERE product_id = 'B00E8KLWB4'
GROUP BY 1, 2 ORDER BY 1 ASC
-- Run time: 4.18 seconds, Data scanned: 81.9 MB)
```

vs.

```sql
CREATE TABLE amazon_reviews_unsorted
WITH (
  format='PARQUET',
  bucketed_by = ARRAY['review_id'], 
  bucket_count = 30
) AS
SELECT review_id, product_id, customer_id, product_parent, star_rating, helpful_votes, total_votes, verified_purchase, marketplace, product_category, review_date
FROM amazon_reviews_by_marketplace
-- Run time: 40.04 seconds, Data scanned: 2.44 GB
```

We used the bucketing functionality to distribute the data evenly across 30 buckets. We used `review_id` as it is high cardinality and will allow for an even distribution.

```sql
SELECT "$path", product_id, COUNT(*) FROM amazon_reviews_unsorted
WHERE product_id = 'B00E8KLWB4'
GROUP BY 1, 2 ORDER BY 1 ASC
-- Run time: 4.39 seconds, Data scanned: 834.36 MB
```

Initially I tried to bucket by `product_id`, but that still puts `product_id` in one file.
It's not sorted across all files, though, as the field is hashed and the hash is used.
Instead, we'll bucket on `review_id`, which will effectively randomize the `product_id`s.

It's tough to control sorting and # of output files using CTAS, but Spark can do this well. Using something like EMR Notebooks or AWS Glue, we read the original dataset and use `repartitionByRange` to sort `product_id` into 30 different output files.

```python
(spark.read.parquet("s3://amazon-reviews-pds/parquet/")
.select("marketplace", "customer_id", "review_id", "product_id", "product_parent", "star_rating")
.repartitionByRange(30, "product_id")
.write.mode("overwrite")
.parquet("s3://<bucket>/amazon-reviews-sorted-subset/", compression="gzip")
)
```

And then back in Athena...

```sql
CREATE EXTERNAL TABLE amazon_reviews_spark_sorted (
  marketplace string,
  customer_id string,
  review_id string,
  product_id string,
  product_parent string,
  star_rating int
)
STORED AS PARQUET
LOCATION 's3://<bucket>/amazon-reviews-sorted-subset/'
```

```sql
SELECT "$path", COUNT(*) FROM amazon_reviews_spark_sorted 
GROUP BY 1 ORDER BY 1 ASC
-- About 5-6M records per file
```

## Parquet metadata

[parquet-tools](https://github.com/apache/parquet-mr/tree/master/parquet-tools) is a fantastic utility for analyzing the content of Parquet files.

If you're on a mac, it's available via homebrew: `brew install parquet-tools`

Download a sample Parquet file and print out the metadata:

```shell
curl -O https://s3.amazonaws.com/amazon-reviews-pds/parquet/product_category=Watches/part-00009-495c48e6-96d6-4650-aa65-3c36a3516ddd.c000.snappy.parquet
parquet-tools meta part-00009-495c48e6-96d6-4650-aa65-3c36a3516ddd.c000.snappy.parquet
```

You'll see a bunch of detailed information about the file including number of rows, minimum and maximum values, and the schema.

_Some rows left out for brevity_

```
file:              file:/private/tmp/part-00009-495c48e6-96d6-4650-aa65-3c36a3516ddd.c000.snappy.parquet 
creator:           parquet-mr version 1.8.2 (build c6522788629e590a53eb79874b95f6c3ff11f16c) 

file schema:       spark_schema 
--------------------------------------------------------------------------------
product_title:     OPTIONAL BINARY O:UTF8 R:0 D:1
star_rating:       OPTIONAL INT32 R:0 D:1
helpful_votes:     OPTIONAL INT32 R:0 D:1
review_date:       OPTIONAL INT32 O:DATE R:0 D:1
year:              OPTIONAL INT32 R:0 D:1

row group 1:       RC:97608 TS:39755962 OFFSET:4 
--------------------------------------------------------------------------------
product_title:      BINARY SNAPPY DO:0 FPO:3243045 SZ:3170609/6450771/2.03 VC:97608 ENC:PLAIN,PLAIN_DICTIONARY,RLE,BIT_PACKED ST:[no stats for this column]
star_rating:        INT32 SNAPPY DO:0 FPO:6413654 SZ:36016/36709/1.02 VC:97608 ENC:PLAIN_DICTIONARY,RLE,BIT_PACKED ST:[min: 1, max: 5, num_nulls: 0]
helpful_votes:      INT32 SNAPPY DO:0 FPO:6449670 SZ:48348/93031/1.92 VC:97608 ENC:PLAIN_DICTIONARY,RLE,BIT_PACKED ST:[min: 0, max: 753, num_nulls: 0]
review_date:        INT32 SNAPPY DO:0 FPO:23689606 SZ:35674/146381/4.10 VC:97608 ENC:PLAIN_DICTIONARY,RLE,BIT_PACKED ST:[min: 2001-04-05, max: 2015-08-31, num_nulls: 0]
year:               INT32 SNAPPY DO:0 FPO:23725280 SZ:2004/37279/18.60 VC:97608 ENC:PLAIN_DICTIONARY,RLE,BIT_PACKED ST:[min: 2001, max: 2015, num_nulls: 0]
```


More detailed information on the different fields for each column is [here](https://github.com/apache/parquet-mr/tree/master/parquet-tools#meta-legend).

Note that current versions of the tool may not show string statistics by default as they could be incorrect: [PARQUET-686](https://issues.apache.org/jira/browse/PARQUET-686).