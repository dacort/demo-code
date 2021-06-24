import argparse
import datetime
import io

import boto3
import geopandas as gpd
from bokeh.io.export import get_screenshot_as_png
from bokeh.io.webdriver import create_chromium_webdriver
from bokeh.models import ColorBar, GeoJSONDataSource, LinearColorMapper
from bokeh.palettes import Reds9 as palette
from bokeh.plotting import figure
from PIL.Image import Image
from pyspark.broadcast import Broadcast
from pyspark.context import SparkContext
from pyspark.sql import SparkSession, dataframe
from pyspark.sql.dataframe import DataFrame
from pyspark.sql.functions import last, udf
from pyspark.sql.types import StringType
from pyspark.sql.window import Window
from shapely.geometry import Point

STATE_FILE = "file:///usr/local/share/bokeh/cb_2020_us_state_500k.zip"
COUNTY_FILE = "file:///usr/local/share/bokeh/cb_2020_us_county_500k.zip"
EXCLUDED_STATES = ["AK", "HI", "PR", "GU", "VI", "MP", "AS"]


def find_first_county_id(longitude: float, latitude: float):
    p = Point(longitude, latitude)
    for index, geo in bc_county.value.items():
        if geo.intersects(p):
            return index
    return None


find_first_county_id_udf_v2 = udf(find_first_county_id, StringType())


def load_county_data(sc: SparkContext) -> Broadcast:
    """
    Loads census.gov polygon data for US counties and broadcasts
    a hash of county GEOID to geometry.
    """
    countydf = gpd.read_file(COUNTY_FILE)
    return sc.broadcast(dict(zip(countydf["GEOID"], countydf["geometry"])))


def get_latest_aqi_avg_by_county(date) -> DataFrame:
    """
    Fetches `date` data from the OpenAQ dataset and performs the following:
        - Filters down to US only
        - Filters to pm2.5 readings
        - Retrieves the most recent reading
        - Enriches the dataframe with Census data county GEOID
        - Calculates the average reading per county
    """
    df = spark.read.json(f"s3://openaq-fetches/realtime-gzipped/{date}/")

    # Filter down to US locations only
    usdf = (
        df.where(df.country == "US")
        .where(df.parameter == "pm25")
        .select("coordinates", "date", "parameter", "unit", "value", "location")
    )

    # Retrieve the most recent pm2.5 reading per county
    windowSpec = (
        Window.partitionBy("location")
        .orderBy("date.utc")
        .rangeBetween(Window.unboundedPreceding, Window.unboundedFollowing)
    )
    last_reading_df = (
        usdf.withColumn("last_value", last("value").over(windowSpec))
        .select("coordinates", "last_value")
        .distinct()
    )

    # Find the county that this reading is from
    countydf = last_reading_df.withColumn(
        "GEOID",
        find_first_county_id_udf_v2(
            last_reading_df.coordinates.longitude, last_reading_df.coordinates.latitude
        ),
    ).select("GEOID", "last_value")

    # Calculate the average reading per county
    pm_avg_by_county = (
        countydf.groupBy("GEOID")
        .agg({"last_value": "avg"})
        .withColumnRenamed("avg(last_value)", "avg_value")
    )

    return pm_avg_by_county


def generate_map(df: dataframe, title: str) -> Image:
    """
    Generate an air quality map for the continental US.
    """
    palette_r = tuple(reversed(palette))

    # Read in county and state geo data from census.gov
    county_df = gpd.read_file(COUNTY_FILE).query(f"STUSPS not in {EXCLUDED_STATES}")
    state_df = gpd.read_file(STATE_FILE).query(f"STUSPS not in {EXCLUDED_STATES}")

    # Merge in our air quality data
    county_aqi_df = county_df.merge(df.toPandas(), on="GEOID")
    color_column = "avg_value"

    # Convert to a "proper" Albers projection :)
    state_json = state_df.to_crs("ESRI:102003").to_json()
    county_json = county_aqi_df.to_crs("ESRI:102003").to_json()

    # Now build the plot!
    p = figure(
        title=title,
        plot_width=1100,
        plot_height=700,
        toolbar_location=None,
        x_axis_location=None,
        y_axis_location=None,
        tooltips=[
            ("County", "@NAME"),
            ("Air Quality Index", "@avg_value"),
        ],
    )
    color_mapper = LinearColorMapper(palette=palette_r)
    p.grid.grid_line_color = None
    p.hover.point_policy = "follow_mouse"
    p.patches(
        "xs",
        "ys",
        fill_alpha=0.0,
        line_color="black",
        line_width=0.5,
        source=GeoJSONDataSource(geojson=state_json),
    )
    p.patches(
        "xs",
        "ys",
        fill_alpha=0.7,
        fill_color={"field": color_column, "transform": color_mapper},
        line_color="black",
        line_width=0.5,
        source=GeoJSONDataSource(geojson=county_json),
    )

    color_bar = ColorBar(color_mapper=color_mapper, label_standoff=12, width=10)
    p.add_layout(color_bar, "right")

    driver = create_chromium_webdriver(["--no-sandbox"])
    return get_screenshot_as_png(p, height=700, width=1100, driver=driver)


def upload_image(image: Image, bucket_name, key):
    print(f"Uploading image data to s3://{bucket_name}/{key}")
    client = boto3.client("s3")
    in_mem_file = io.BytesIO()
    image.save(in_mem_file, format="png")
    in_mem_file.seek(0)
    client.put_object(Bucket=bucket_name, Key=key, Body=in_mem_file)


def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("bucket", help="The name of the S3 bucket to upload to.")
    parser.add_argument(
        "prefix",
        help="The prefix where the image file (date-latest.png) will be uploaded.",
    )
    parser.add_argument(
        "--date",
        help="The date to create the AQI map for.",
        default=f"{datetime.datetime.utcnow().date()}",
    )
    return parser.parse_args()


if __name__ == "__main__":
    """
    Generates an Air Quality Index (AQI) map for the continential US.
    By default, it generates the latest AQI readings for the current date.

    Usage: generate_aqi_map
    """
    spark = SparkSession.builder.appName("AirQualityMapper").getOrCreate()
    bc_county = load_county_data(spark.sparkContext)

    args = parse_args()
    date = args.date
    bucket = args.bucket
    key = f"{args.prefix}{date}-latest.png"

    pm_reading_by_county = get_latest_aqi_avg_by_county(date)
    image = generate_map(pm_reading_by_county, f"US PM2.5 by county for {date}")
    upload_image(image, bucket, key)
