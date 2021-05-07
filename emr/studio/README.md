# EMR Studio Demo Code

This is the associated code for the [Intro to Amazon EMR Studio](https://youtu.be/oVgyL5W9FPU) video.

- [WeatherDay.ipynb](WeatherDay.ipynb) - Notebook that uses [@zflamig](https://github.com/zflamig)'s original [birthday-weather](https://github.com/zflamig/birthday-weather) example that uses [ERA5 Zaar data](https://registry.opendata.aws/ecmwf-era5/) to draw a map of US weather for a given day.

## CloudFormation Templates

There are two templates in this repository for use with EMR Studio. Please note that you can find more examples in the [EMR Studio Samples](https://github.com/aws-samples/emr-studio-samples) repository.

1. [`full_studio_dependencies`](./cloudformation/full_studio_dependencies.cfn.yaml) - Creates everything you need in order to use EMR Studio including a new VPC with security groups and subnets tagged appropriately for use with [EMR Managed Policies](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-managed-iam-policies.html).
2. [`matplotlib_studio`](./cloudformation/matplotlib_studio.cfn.yaml) - Incorporates the above template and also creates a new Studio associated with the AWS SSO username you provide. Also includes a Service Catalog cluster template that installs `basemap` for usage with matplotlib and the `WeatherDay` notebook above.

## Scheduling Notebooks

In order to schedule, you need three pieces of information:
- Editor ID
- Cluster ID
- Service role name

```shell
export EDITOR_ID=e-AAABBB
export CLUSTER_ID=j-CCCDDD
```


```shell
aws emr start-notebook-execution \
  --editor-id ${EDITOR_ID} \
  --notebook-params '{"weather_date": "2019-09-01"}' \
  --relative-path demo-code/emr/studio/WeatherDay.ipynb \
  --notebook-execution-name Summer \
  --execution-engine '{"Id" : "'${CLUSTER_ID}'"}' \
  --service-role EMR_Notebooks_DefaultRole
```

```shell
aws emr describe-notebook-execution --notebook-execution-id ex-FFFFGGGG
```

```shell
aws s3 cp s3://<EMR_STUDIO_BUCKET>/e-AAABBB/executions/ex-FFFFGGGG/WeatherDay.ipynb .
```