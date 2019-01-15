#!/bin/bash

# Define some environment variables 
: ${TARGET_SUBNET:=subnet-XXXX}
: ${TARGET_GRANTEE:=role/Admin}
: ${CLUSTER_SSH_KEY:=sshkeyname}
: ${BUCKET_NAME:=damons-reinvent-demo}
: ${AWS_REGION:=us-east-1}
: ${AWS_PROFILE:=default}

# Used to retrieve output from AWS CLI commands
TMP_FILE=$(mktemp)

# Update settings specific to our desired region in the CloudFormation templates
find assets/cloudformation -type f -exec \
    sed -i '' "s/Ec2SubnetId:.*/Ec2SubnetId: \"${TARGET_SUBNET}\"/" {} +
find assets/cloudformation -type f -exec \
    sed -i '' "s/Ec2KeyName:.*/Ec2KeyName: \"${CLUSTER_SSH_KEY}\"/" {} +

# Deploy the updated templates
RELEASE_BUCKET=${BUCKET_NAME} AWS_PROFILE=${AWS_PROFILE} make

# Create a new portfolio
aws --region ${AWS_REGION} servicecatalog create-portfolio \
    --display-name "EMR re:Invent Demo" \
    --provider-name "@dacort" \
    --description "Pre-defined on-demand EMR clusters" \
    | tee ${TMP_FILE}
PORTFOLIO_ID=$(jq -r '.PortfolioDetail.Id' ${TMP_FILE})

# Create a product
aws --region ${AWS_REGION} servicecatalog create-product --name "Data Analyst EMR" \
    --owner "@dacort" \
    --description "Provides Hive, Spark, and Hue for interactive queries." \
    --product-type CLOUD_FORMATION_TEMPLATE \
    --provisioning-artifact-parameters '{"Name":"Initial revision", "Description": "", "Info":{"LoadTemplateFromURL":"https://s3.amazonaws.com/'${BUCKET_NAME}'/reinvent/cloudformation/Spark_Cluster_Versions/v0_Initial_Revision.cf.yml"},"Type":"CLOUD_FORMATION_TEMPLATE"}' \
    | tee ${TMP_FILE}
PRODUCT_ID=$(jq -r '.ProductViewDetail.ProductViewSummary.ProductId' ${TMP_FILE})

# Connect the product to our portfolio
aws --region ${AWS_REGION} servicecatalog associate-product-with-portfolio --product-id ${PRODUCT_ID} --portfolio-id ${PORTFOLIO_ID}

# Also create a Data Science product
aws --region ${AWS_REGION} servicecatalog create-product --name "Data Science EMR" \
    --owner "@dacort" \
    --description "Provides TensorFlow, JupyterHub, and MXNet for ML queries." \
    --product-type CLOUD_FORMATION_TEMPLATE \
    --provisioning-artifact-parameters '{"Name":"Initial revision", "Description": "", "Info":{"LoadTemplateFromURL":"https://s3.amazonaws.com/'${BUCKET_NAME}'/reinvent/cloudformation/Spark_Cluster_Versions/v0_Initial_Revision.cf.yml"},"Type":"CLOUD_FORMATION_TEMPLATE"}' \
    | tee ${TMP_FILE}
DS_PRODUCT_ID=$(jq -r '.ProductViewDetail.ProductViewSummary.ProductId' ${TMP_FILE})

# Connect the product to our portfolio
aws --region ${AWS_REGION} servicecatalog associate-product-with-portfolio --product-id ${DS_PRODUCT_ID} --portfolio-id ${PORTFOLIO_ID}

# Add different product revisions
VERSIONS=( "Updated security setting:v1_Security_Settings"
        "Updated parameter labels:v2_Updated_Parameters"
        "Choose your own cluster size!:v3_Cluster_Size"
        "Auto-terminate functionality:v4_Auto_Terminate"
        "Spark UI:v5_SparkUI" )

for version in "${VERSIONS[@]}" ; do
    NAME=${version%%:*}
    TEMPLATE=${version#*:}
    aws --region ${AWS_REGION} servicecatalog create-provisioning-artifact \
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
aws --region ${AWS_REGION} servicecatalog associate-principal-with-portfolio \
    --portfolio-id ${PORTFOLIO_ID} \
    --principal-type IAM \
    --principal-arn arn:aws:iam::$(aws --region ${AWS_REGION} sts get-caller-identity --query Account --output text):${TARGET_GRANTEE}