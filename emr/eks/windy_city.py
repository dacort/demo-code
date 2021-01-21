import sys

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType

NOAA_ISD = "s3://noaa-global-hourly-pds/2021/"

def topDays(spark, longLeft, latBottom, longRight, latTop):
    # Load data for 2021
    df = spark.read.format("csv").option("header", "true").option("inferSchema", "true").load(NOAA_ISD)

    # Convert lat/long columns to doubles
    df = df \
        .withColumn('LATITUDE', df.LATITUDE.cast(DoubleType())) \
        .withColumn('LONGITUDE', df.LONGITUDE.cast(DoubleType()))
    
    # Exclude missing values and filter on our bounding box
    seadf = df \
        .filter(df.WND != '999,9,9,9999,9') \
        .filter(df.LATITUDE >= latBottom) \
        .filter(df.LATITUDE <= latTop) \
        .filter(df.LONGITUDE >= longLeft) \
        .filter(df.LONGITUDE <= longRight)

    # Pull out day and windspeed
    wind_date_df = seadf \
        .select("DATE", "NAME", "WND") \
        .withColumn("windSpeed", F.split(seadf.WND, ",")[3].cast(DoubleType())/10 ) \
        .withColumn("ymd", F.split(df.DATE, "T")[0])

    # Find top speed for reach day!
    wind_date_df.groupBy("ymd").agg({'windSpeed':'max'}).orderBy("ymd").show(50)

if __name__ == "__main__":
    """
        Usage: windy_city [bbox]
                e.g. -122.46,47.48,-122.22,47.73 for Seattle
    """
    spark = SparkSession\
        .builder\
        .appName("WindyCity")\
        .getOrCreate()
    
    # Use http://tools.geofabrik.de/calc/#type=geofabrik_standard&bbox=-122.459696,47.481002,-122.224433,47.734136&tab=1&proj=EPSG:4326&places=2 to 
    # test out or find bounding boxes
    bbox = [float(val) for val in sys.argv[1].split(',')] if len(sys.argv) > 1 else [-122.459696,47.481002,-122.224433,47.734136]

    topDays(spark, *bbox)

    spark.stop()

    # -122.459696,47.481002,-122.224433,47.734136
    # -122.48,47.41,-122.16,47.49
    # left_long, bottom_lat, right_long, top_lat