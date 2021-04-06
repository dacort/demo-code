
# CDK Big Data Stack

This is Big Data Stack built with Python CDK.

It installs the following:
- VPC
- RDS MySQL Instance
- EMR Cluster
- EKS Cluster
    - With k8s Cluster Autoscaler
- EMR Virtual Cluster (for EKS)

You can use the following step to activate your virtualenv.

```
$ source .venv/bin/activate
```

Once the virtualenv is activated, you can install the required dependencies.

```
$ pip install -r requirements.txt
```

At this point you can now synthesize the CloudFormation template for this code.

```
$ cdk synth
```

To add additional dependencies, for example other CDK libraries, just add
them to your `setup.py` file and rerun the `pip install -r requirements.txt`
command.

To deploy:

```shell
cdk deploy --all -c eks_admin_role_name=Admin   
```

Where `eks_admin_role_name` is an IAM role that you want to grant admin access to your EKS cluster.

## Stack Overview

### VPC

Deploys a simple VPC across 3 availability zones.

### RDS

Creates a MySQL RDS instance to be used as a Hive metastore for EMR.

### EMR

Creates an EMR 5.32 that is configured to connect to the RDS database above. 

A job execution role is created that, currently, has extremely permissive permissions.

The cluster is creating using the new EMR roles and is configured to use Spark and the Jupyter Enteprise Gateway so you can use it with EMR Notebooks or EMR Studio.

### EKS

Creates an EKS cluster with a single managed Node Group of `m5.xlarge` instances. In addition, it installs the Cluster Autoscaler, Kubernetes Dashboard, and Apache Airflow from the [community-provided Helm Chart](https://github.com/airflow-helm/charts/tree/main/charts/airflow).

An IAM service role is also created specifically for EMR.

### EMRContainers

Creates an EMR Virtual Cluster for running EMR jobs on EKS.

## Useful commands

 * `cdk ls`          list all stacks in the app
 * `cdk synth`       emits the synthesized CloudFormation template
 * `cdk deploy`      deploy this stack to your default AWS account/region
 * `cdk diff`        compare deployed stack with current state
 * `cdk docs`        open CDK documentation

