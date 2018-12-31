```python
print("Hello, world!")
```

```python
from pyspark.ml.recommendation import ALS
from pyspark.ml.evaluation import RegressionEvaluator

from pyspark.sql.functions import *
import sys
```


```python
toys = spark.read.parquet("s3://amazon-reviews-pds/parquet/product_category=Toys/")
toys.printSchema()
```

```python
toys.count()
```

```python
ratings = (
    toys.select("customer_id", "product_id", "star_rating", "product_title")
    .withColumn("customer_id_int", abs(hash(col("customer_id")) % sys.maxint))
    .withColumn("product_id_int", abs(hash(col("product_id")) % sys.maxint))
).repartition(200)
```

```python
top_toys = ratings\
            .groupby("product_id_int", "product_title")\
            .agg(
                avg(col("star_rating")).alias("avg_rating"),
                count("star_rating").alias("count")
            )\
            .sort(desc("count"))\
            .limit(25)\
            .withColumn("avg_rating", round(col('avg_rating'), 3))\
            .withColumn("product_title", col("product_title").substr(1, 45))
top_toys.show(truncate=False)
```

```python
kids_ratings = (
    toys
    .where("lower(review_body) LIKE '%baby%' OR lower(review_body) LIKE '%infant%'")
    .select("customer_id", "product_id", "star_rating", "product_title")
    .withColumn("customer_id_int", abs(hash(col("customer_id")) % sys.maxint))
    .withColumn("product_id_int", abs(hash(col("product_id")) % sys.maxint))
).repartition(200)
```

```python
top_toys = kids_ratings\
            .groupby("product_id_int", "product_title")\
            .agg(
                avg(col("star_rating")).alias("avg_rating"),
                count("star_rating").alias("count")
            )\
            .sort(desc("count"))\
            .limit(25)\
            .withColumn("avg_rating", round(col('avg_rating'), 3))\
            .withColumn("product_title", col("product_title").substr(1, 45))
top_toys.show(truncate=False)
```

```python
(training, test) = ratings.randomSplit([0.8, 0.2])

# Build the recommendation model using ALS on the training data
als = ALS(maxIter=5, regParam=0.01, userCol="customer_id_int", itemCol="product_id_int", ratingCol="star_rating", coldStartStrategy="drop")
model = als.fit(training)
```