from datetime import timedelta

from airflow import DAG
from airflow.providers.amazon.aws.operators.emr_create_job_flow import (
    EmrCreateJobFlowOperator,
)
from airflow.providers.amazon.aws.sensors.emr_job_flow import EmrJobFlowSensor
from airflow.utils.dates import days_ago

DEFAULT_ARGS = {
    "owner": "airflow",
    "depends_on_past": False,
    "email": ["airflow@example.com"],
    "email_on_failure": False,
    "email_on_retry": False,
}

# [START howto_operator_emr_automatic_steps_config]
SPARK_STEPS = [
    {
        "Name": "calculate_pi",
        "ActionOnFailure": "CONTINUE",
        "HadoopJarStep": {
            "Jar": "command-runner.jar",
            "Args": ["/usr/lib/spark/bin/run-example", "SparkPi", "10"],
        },
    }
]


# "LogUri": "s3://my-emr-log-bucket/default_job_flow_location",
JOB_FLOW_OVERRIDES = {
    "Name": "PiCalc",
    "ReleaseLabel": "emr-6.3.0",
    "Instances": {
        "InstanceGroups": [
            {
                "Name": "Primary node",
                "Market": "SPOT",
                "InstanceRole": "MASTER",
                "InstanceType": "m5.xlarge",
                "InstanceCount": 1,
            },
            {
                "Name": "Core nodes",
                "Market": "SPOT",
                "InstanceRole": "CORE",
                "InstanceType": "m5.xlarge",
                "InstanceCount": 1,
            },
        ],
        "KeepJobFlowAliveWhenNoSteps": False,
        "TerminationProtected": False,
    },
    "Steps": SPARK_STEPS,
    "JobFlowRole": "EMR_EC2_DefaultRole",
    "ServiceRole": "EMR_DefaultRole",
}
# [END howto_operator_emr_automatic_steps_config]

with DAG(
    dag_id="emr_job_flow_automatic_steps_dag",
    default_args=DEFAULT_ARGS,
    dagrun_timeout=timedelta(hours=2),
    start_date=days_ago(2),
    schedule_interval="0 3 * * *",
    tags=["example"],
) as dag:

    # [START howto_operator_emr_automatic_steps_tasks]
    job_flow_creator = EmrCreateJobFlowOperator(
        task_id="create_job_flow",
        job_flow_overrides=JOB_FLOW_OVERRIDES,
        aws_conn_id="aws_default",
        emr_conn_id="emr_default",
    )

    job_sensor = EmrJobFlowSensor(
        task_id="check_job_flow",
        job_flow_id="{{ task_instance.xcom_pull(task_ids='create_job_flow', key='return_value') }}",
        aws_conn_id="aws_default",
    )

    job_flow_creator >> job_sensor
    # [END howto_operator_emr_automatic_steps_tasks]
