-- Summary: This sample shows you how to convert Amazon review stored in S3 using Hive

-- Create table using sample data in S3.  Note: you can replace this S3 path with your own.
CREATE EXTERNAL TABLE IF NOT EXISTS `amazon_reviews_tsv`(
  `marketplace` string, 
  `customer_id` string, 
  `review_id` string, 
  `product_id` string, 
  `product_parent` string, 
  `product_title` string, 
  `product_category` string,
  `star_rating` int, 
  `helpful_votes` int, 
  `total_votes` int, 
  `vine` string, 
  `verified_purchase` string, 
  `review_headline` string, 
  `review_body` string, 
  `review_date` string
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY '\t'
LOCATION 's3://amazon-reviews-pds/tsv/';

-- ${INPUT}

-- Total requests per operating system for a given time frame
SET hive.groupby.position.alias=true;

INSERT OVERWRITE DIRECTORY '${OUTPUT}/top_toys/'
ROW FORMAT DELIMITED FIELDS TERMINATED BY '\t'
SELECT product_id, product_title, count(*) AS num_reviews, avg(star_rating) AS avg_stars
FROM amazon_reviews_tsv where product_category='Toys'
GROUP BY 1, 2
ORDER BY num_reviews DESC
limit 100;

-- s3://damons-reinvent-demo/reinvent/scripts/hive_converter.sql -d INPUT=s3://amazon-reviews-pds/tsv/ -d OUTPUT=s3://damons-reinvent-demo/reinvent/hive/query_output/
-- hive-script --run-hive-script --args -f s3://damons-reinvent-demo/reinvent/scripts/hive_converter.sql -d INPUT=s3://amazon-reviews-pds/tsv/ -d OUTPUT=s3://damons-reinvent-demo/reinvent/hive/query_output/