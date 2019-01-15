RELEASE_BUCKET?=damons-reinvent-demo
PREFIX?=reinvent/
AWS_PROFILE?=default

deploy:
	@aws --profile $(AWS_PROFILE) s3 sync assets/ "s3://$(RELEASE_BUCKET)/$(PREFIX)"
	@echo "https://$(RELEASE_BUCKET).s3.amazonaws.com/$(PREFIX)cloudformation/Spark_Cluster.cf.yml"
	@echo "https://$(RELEASE_BUCKET).s3.amazonaws.com/$(PREFIX)EMR_Spark_Pipeline.cf.yml"
	@echo "https://$(RELEASE_BUCKET).s3.amazonaws.com/$(PREFIX)cloudformation/Presto_Cluster.cf.yml"

