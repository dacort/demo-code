#!/bin/bash

# Define some environment variables 
TARGET_SUBNET=subnet-XXXX
TARGET_GRANTEE=role/Admin
CLUSTER_SSH_KEY=sshkeyname
BUCKET_NAME=damons-reinvent-demo

# Update settings specific to our desired region and update the CloudFormation templates
sed -i '' "s/Ec2SubnetId:.*/Ec2SubnetId: \"${TARGET_SUBNET}\"/" assets/cloudformation/Spark_Cluster_Versions/*
make

# Create a new portfolio
aws --region us-east-1 servicecatalog create-portfolio \
    --display-name "EMR re:Invent Demo" \
    --provider-name "@dacort" \
    --description "Pre-defined on-demand EMR clusters" \
    | tee /tmp/out
PORTFOLIO_ID=$(jq -r '.PortfolioDetail.Id' /tmp/out)

# Create a product
aws --region us-east-1 servicecatalog create-product --name "Data Analyst EMR" \
    --owner "@dacort" \
    --description "Provides Hive, Spark, and Hue for interactive queries." \
    --product-type CLOUD_FORMATION_TEMPLATE \
    --provisioning-artifact-parameters '{"Name":"Initial revision", "Description": "", "Info":{"LoadTemplateFromURL":"https://s3.amazonaws.com/'${BUCKET_NAME}'/reinvent/cloudformation/Spark_Cluster_Versions/v0_Initial_Revision.cf.yml"},"Type":"CLOUD_FORMATION_TEMPLATE"}' \
    | tee /tmp/out
PRODUCT_ID=$(jq -r '.ProductViewDetail.ProductViewSummary.ProductId' /tmp/out)

# Connect the product to our portfolio
aws --region us-east-1 servicecatalog associate-product-with-portfolio --product-id ${PRODUCT_ID} --portfolio-id ${PORTFOLIO_ID}

# Also create a Data Science product
aws --region us-east-1 servicecatalog create-product --name "Data Science EMR" \
    --owner "@dacort" \
    --description "Provides TensorFlow, JupyterHub, and MXNet for ML queries." \
    --product-type CLOUD_FORMATION_TEMPLATE \
    --provisioning-artifact-parameters '{"Name":"Initial revision", "Description": "", "Info":{"LoadTemplateFromURL":"https://s3.amazonaws.com/'${BUCKET_NAME}'/reinvent/cloudformation/Spark_Cluster_Versions/v0_Initial_Revision.cf.yml"},"Type":"CLOUD_FORMATION_TEMPLATE"}' \
    | tee /tmp/out
DS_PRODUCT_ID=$(jq -r '.ProductViewDetail.ProductViewSummary.ProductId' /tmp/out)

# Connect the product to our portfolio
aws --region us-east-1 servicecatalog associate-product-with-portfolio --product-id ${DS_PRODUCT_ID} --portfolio-id ${PORTFOLIO_ID}

# Add different product revisions
VERSIONS=( "Updated security setting:v1_Security_Settings"
        "Updated parameter labels:v2_Updated_Parameters"
        "Choose your own cluster size!:v3_Cluster_Size"
        "Auto-terminate functionality:v4_Auto_Terminate"
        "Spark UI:v5_SparkUI" )

for version in "${VERSIONS[@]}" ; do
    NAME=${version%%:*}
    TEMPLATE=${version#*:}
    aws --region us-east-1 servicecatalog create-provisioning-artifact \
        --product-id ${PRODUCT_ID} \
        --parameters '{
            "Name": "'"${NAME}"'",
            "Description": "",
            "Info": {
                "LoadTemplateFromURL": "https://s3.amazonaws.com/'${BUCKET_NAME}'/reinvent/cloudformation/Spark_Cluster_Versions/'${TEMPLATE}'.cf.yml"
            },
            "Type": "CLOUD_FORMATION_TEMPLATE"
        }'
done

# Grant access to the portfolio
aws --region us-east-1 servicecatalog associate-principal-with-portfolio \
    --portfolio-id ${PORTFOLIO_ID} \
    --principal-type IAM \
    --principal-arn arn:aws:iam::$(aws --region us-east-1 sts get-caller-identity --query Account --output text):${TARGET_GRANTEE}