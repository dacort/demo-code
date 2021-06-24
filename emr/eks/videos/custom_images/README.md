# EMR on EKS Custom Images

Use Bokeh with EMR on EKS to draw daily images of Air Quality data in the continental US.

Demo video: [https://youtu.be/0x4DRKmNPfQ](https://youtu.be/0x4DRKmNPfQ)

## Overview

- First, we need to login to the relevant ECR and pull the latest EMR image we want.

```shell
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin 711395599931.dkr.ecr.us-east-2.amazonaws.com
docker pull 711395599931.dkr.ecr.us-east-2.amazonaws.com/notebook-spark/emr-6.3.0:latest
```

- Next, we want to build a Dockerfile that installs the `bokeh` library.

We also want to populate the bokeh sample dataset directly on the image itself because we use that for our map.

```dockerfile
FROM 711395599931.dkr.ecr.us-east-2.amazonaws.com/notebook-spark/emr-6.3.0:latest

USER root

# Install Chrome
RUN curl https://intoli.com/install-google-chrome.sh | bash && \
    mv /usr/bin/google-chrome-stable /usr/bin/chrome

RUN pip3 install \
    bokeh>=2.3.2 \
    chromedriver-py>=91.0.4472.19.0 \
    selenium>=3.141.0
RUN bokeh sampledata

RUN ln -s /usr/local/lib/python3.7/site-packages/chromedriver_py/chromedriver_linux64 /usr/local/bin/chromedriver

USER hadoop:hadoop
```

- Now build your image

```shell
docker build -t emr-6.3.0-bokeh:latest .
```

- Validate

I added a simple test script that generates a plot and validates it against a known hash.

```shell
docker run --rm -it emr-6.3.0-bokeh python3 /test/gen_plot.py
```

If you see "All good! 🙌" we're good to go!

- Push it to a (private) GH repo

```shell
export GH_USERNAME=dacort
echo $CR_PAT| docker login ghcr.io -u ${GH_USERNAME} --password-stdin
docker tag emr-6.3.0-bokeh:latest ghcr.io/${GH_USERNAME}/emr-6.3.0-bokeh:latest
docker push ghcr.io/${GH_USERNAME}/emr-6.3.0-bokeh:latest
```

- Set up a secret to allow for the git pull

```shell
DOCKER_AUTH=$(echo -n "${GH_USERNAME}:${CR_PAT}" | base64)

DOCKER_DATA=$(echo '{ "auths": { "ghcr.io": { "auth":"'${DOCKER_AUTH}'" } } }' | base64)

cat <<EOF > dockerconfigjson-github-com.yaml
kind: Secret
type: kubernetes.io/dockerconfigjson
apiVersion: v1
metadata:
  name: dockerconfigjson-github-com
  namespace: emr-jobs
  labels:
    app: app-name
data:
  .dockerconfigjson: ${DOCKER_DATA}
EOF

kubectl create -f dockerconfigjson-github-com.yaml -n emr-jobs
```

- Now let's run run it!

```shell
aws emr-containers start-job-run \
    --virtual-cluster-id ${EMR_EKS_CLUSTER_ID} \
    --name dacort-aqi \
    --execution-role-arn ${EMR_EKS_EXECUTION_ARN} \
    --release-label emr-6.3.0-latest \
    --job-driver '{
        "sparkSubmitJobDriver": {
            "entryPoint": "s3://'${S3_BUCKET}'/code/generate_aqi_map.py",
            "entryPointArguments": ["'${S3_BUCKET}'", "output/airq/"],
            "sparkSubmitParameters": "--conf spark.kubernetes.container.image=ghcr.io/dacort/emr-6.3.0-bokeh:latest --conf spark.kubernetes.container.image.pullSecrets=dockerconfigjson-github-com"
        }
    }' \
    --configuration-overrides '{
        "monitoringConfiguration": {
            "s3MonitoringConfiguration": { "logUri": "s3://'${S3_BUCKET}'/logs/" }
        }
    }'
```

- We should see some air quality data!

```shell
aws s3 ls s3://${S3_BUCKET}/output/airq/
# 2021-06-15 15:44:49     277735 2021-06-15-latest.png
```

```shell
aws s3 cp s3://${S3_BUCKET}/output/airq/2021-06-15-latest.png .
open 2021-06-15-latest.png
```

## Testing your code locally

If you want, you can start up `pyspark` on your image locally to interactively test your code.

```shell
docker run --rm -it emr-6.3.0-bokeh pyspark --deploy-mode client --master 'local[1]'
```

Note that if you access AWS resources from within your environment, you'll either need to change your `spark.hadoop.fs.s3.customAWSCredentialsProvider` in your Spark job or set AWS crednetials in your environment. If you have an access key or secret, you can pass those into the `docker run` command like so:

```shell
docker run --rm -it \
    -e AWS_ACCESS_KEY_ID \
    -e AWS_SECRET_ACCESS_KEY \
    emr-6.3.0-bokeh \
    pyspark --deploy-mode client --master 'local[1]'
```

## References

- https://stackoverflow.com/questions/47087506/flatten-a-fiona-structure-to-dictionary-for-bokeh/47135604#47135604
- https://discourse.bokeh.org/t/questions-re-choropleth/2589/3
- https://towardsdatascience.com/walkthrough-mapping-basics-with-bokeh-and-geopandas-in-python-43f40aa5b7e9
