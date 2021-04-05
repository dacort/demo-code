from os.path import abspath
from pyspark.sql import SparkSession
from pyspark.sql import Row

# warehouse_location points to the default location for managed databases and tables
warehouse_location = abspath("spark-warehouse")
spark = (
    SparkSession.builder.appName("hive-demo")
    .config("spark.sql.warehouse.dir", warehouse_location)
    .enableHiveSupport()
    .getOrCreate()
)
spark.sql("SHOW DATABASES").show()
spark.sql("SELECT count(*) FROM rapid7_fdns_any").show()
spark.sql("SELECT * FROM rapid7_fdns_any WHERE name LIKE '%.starlink.com' AND date = (SELECT MAX(date) from rapid7_fdns_any)").show()
spark.stop()