import sys

from pyspark.sql import SparkSession

if len(sys.argv) > 1:
    INPUT_LOCATION = sys.argv[1]
    OUTPUT_LOCATION = sys.argv[2]
else:
    INPUT_LOCATION = 's3://amazon-reviews-pds/tsv/amazon_reviews_us_Toys_v1_00.tsv.gz'
    OUTPUT_LOCATION = 's3://damons-reinvent-demo/reinvent/spark/amazon_reviews/'

# Utility to just take an input file and split it
# df = spark.read.option("sep", "\t").option("header","true").csv(INPUT_LOCATION)
# df.repartition(10).write.csv("s3://damons-reinvent-demo/reinvent/source_toys/")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: spark_converter <input> <output>")
        sys.exit(-1)
    
    # Initialize the spark context.
    spark = SparkSession\
        .builder\
        .appName("SparkConverter")\
        .config("spark.sql.parquet.fs.optimized.committer.optimization-enabled", "true")\
        .getOrCreate()
    
    # Read in the desired TSV
    df = spark.read.option('sep', '\t').option('header', 'true').csv(INPUT_LOCATION)

    # Repartition for multiple output files and write out to parquet
    df.repartition(10).write.mode('overwrite').parquet(OUTPUT_LOCATION)

# To run: s3://damons-reinvent-demo/reinvent/scripts/spark_converter.py s3://amazon-reviews-pds/tsv/amazon_reviews_us_Toys_v1_00.tsv.gz s3://damons-reinvent-demo/reinvent/amazon_reviews/