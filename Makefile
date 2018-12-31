RELEASE_BUCKET?=damons-reinvent-demo
AWS_PROFILE?=default

deploy:
	@aws --profile $(AWS_PROFILE) s3 sync assets/ "s3://$(RELEASE_BUCKET)/reinvent/"
	@echo "https://$(RELEASE_BUCKET).s3.amazonaws.com/reinvent/cloudformation/Spark_Cluster.cf.yml"
	@echo "https://$(RELEASE_BUCKET).s3.amazonaws.com/reinvent/EMR_Spark_Pipeline.cf.yml"
	@echo "https://$(RELEASE_BUCKET).s3.amazonaws.com/reinvent/cloudformation/Presto_Cluster.cf.yml"

