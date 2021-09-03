package aws.example.emrcontainers;

import software.amazon.awssdk.services.emrcontainers.EmrContainersClient;
import software.amazon.awssdk.services.emrcontainers.model.*;

public class StartJobRunExample {

    public static StartJobRunResponse submitEMRContainersJob(EmrContainersClient emrContainersClient, String virtualClusterId, String jobRoleArn) {
        SparkSubmitJobDriver sparkSubmit = SparkSubmitJobDriver.builder()
                .entryPoint("local:///usr/lib/spark/examples/src/main/python/pi.py")
                .entryPointArguments()
                .sparkSubmitParameters("--conf spark.executor.instances=1 --conf spark.executor.memory=2G --conf spark.executor.cores=1 --conf spark.driver.cores=1")
                .build();

        JobDriver jobDriver = JobDriver.builder()
                .sparkSubmitJobDriver(sparkSubmit)
                .build();

        StartJobRunRequest jobRunRequest = StartJobRunRequest.builder()
                .name("pi.py")
                .jobDriver(jobDriver)
                .executionRoleArn(jobRoleArn)
                .virtualClusterId(virtualClusterId)
                .releaseLabel(ExampleConstants.EMR_RELEASE_LABEL)
                .build();

        return emrContainersClient.startJobRun(jobRunRequest);
    }

    // Wait for an EMR Containers query to complete, fail or to be cancelled
    public static void waitForQueryToComplete(EmrContainersClient emrContainersClient, String virtualClusterId, String jobId) throws InterruptedException {
        DescribeJobRunResponse jobRunResponse;
        DescribeJobRunRequest jobRunRequest = DescribeJobRunRequest.builder()
                .virtualClusterId(virtualClusterId)
                .id(jobId)
                .build();

        boolean isQueryStillRunning = true;
        while (isQueryStillRunning) {
            jobRunResponse = emrContainersClient.describeJobRun(jobRunRequest);
            JobRunState jobState = jobRunResponse.jobRun().state();
            if (jobState == JobRunState.FAILED) {
                throw new RuntimeException("The EMR Containers job failed to run with error message: " +
                        jobRunResponse.jobRun().failureReasonAsString());
            } else if (jobState == JobRunState.CANCELLED) {
                throw new RuntimeException("The EMR Containers job was cancelled.");
            } else if (jobState == JobRunState.COMPLETED) {
                isQueryStillRunning = false;
            } else {
                // Sleep an amount of time before retrying again
                Thread.sleep(ExampleConstants.SLEEP_AMOUNT_IN_MS);
            }
            System.out.println("The current status is: " + jobState.toString());
        }
    }

    public static void main(String[] args) throws InterruptedException {
        final String USAGE = "\n" +
                "StartJobRunExample - Run an EMR on EKS job\n\n" +
                "Usage: StartJobRunExample <virtual_cluster_id> <job_role_arn>\n\n" +
                "Where:\n" +
                "  virtual_cluster_id - The virtual cluster ID of your EMR on EKS cluster.\n\n" +
                "  job_role_arn       - The execution role ARN for the job run.\n";

        if (args.length < 2) {
            System.out.println(USAGE);
            System.exit(1);
        }

        String virtual_cluster_id = args[0];
        String job_role_arn = args[1];

        System.out.println("Creating a new job on cluster: " + virtual_cluster_id);

        EmrContainersClient emrContainersClient = EmrContainersClient.builder()
                .build();

        // Create a default job on the provided EMR on EKS cluster
        StartJobRunResponse jobRun = submitEMRContainersJob(emrContainersClient, virtual_cluster_id, job_role_arn);
        System.out.println("Started job: " + jobRun.id());

        // Now wait for the job to run to completion
        waitForQueryToComplete(emrContainersClient, virtual_cluster_id, jobRun.id());
        emrContainersClient.close();

        System.out.println("Done!");
    }

}
