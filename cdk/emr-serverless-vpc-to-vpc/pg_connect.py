from pyspark.sql import SparkSession

PG_HOSTNAME = "ip-10-0-XXX-XXX.us-west-2.compute.internal"

spark = SparkSession.builder.getOrCreate()

df = (
    spark.read.format("jdbc")
    .option(
        "url", f"jdbc:postgresql://{PG_HOSTNAME}:5432/postgres"
    )
    .option("driver", "org.postgresql.Driver")
    .option("dbtable", "users")
    .option("user", "remote")
    .option("password", "remote")
    .load()
)

df.show()
print(df.count())

