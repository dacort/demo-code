from os.path import expanduser, join, abspath
from pyspark.sql import SparkSession
from pyspark.sql import Row

# warehouse_location points to the default location for managed databases and tables
warehouse_location = abspath("spark-warehouse")
spark = (
    SparkSession.builder.appName("glue-demo")
    .config("spark.sql.warehouse.dir", warehouse_location)
    .enableHiveSupport()
    .getOrCreate()
)

spark.sql("SHOW DATABASES").show()
spark.sql("""
SELECT id, snippet.title,
  MAX(CAST(statistics.viewcount AS integer)) AS max_views,
  MAX(CAST(statistics.likecount AS integer)) AS max_likes
FROM damons_datalake.youtube
GROUP BY 1, 2
ORDER BY 3 DESC
""").show(truncate=False)
spark.stop()