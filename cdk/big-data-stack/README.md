
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

## Useful commands

 * `cdk ls`          list all stacks in the app
 * `cdk synth`       emits the synthesized CloudFormation template
 * `cdk deploy`      deploy this stack to your default AWS account/region
 * `cdk diff`        compare deployed stack with current state
 * `cdk docs`        open CDK documentation

