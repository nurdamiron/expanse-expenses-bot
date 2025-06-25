#!/bin/bash

# ECS Deployment Script
set -e

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID}"
PROJECT_NAME="expanse-expenses-bot"
ECR_REPOSITORY="${PROJECT_NAME}"
ECS_CLUSTER="${PROJECT_NAME}-cluster"
ECS_SERVICE="${PROJECT_NAME}-service"
TASK_FAMILY="${PROJECT_NAME}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if AWS credentials are configured
if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo -e "${RED}AWS credentials not found. Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables.${NC}"
    exit 1
fi

if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo -e "${RED}AWS_ACCOUNT_ID not set. Please set it as an environment variable.${NC}"
    exit 1
fi

# Load infrastructure config
if [ -f "infrastructure-config.sh" ]; then
    source infrastructure-config.sh
elif [ -f "infrastructure-config.json" ]; then
    # Parse JSON config if Python is available
    if command -v python3 &> /dev/null; then
        export VPC_ID=$(python3 -c "import json; print(json.load(open('infrastructure-config.json'))['vpc_id'])")
        export SUBNET_ID=$(python3 -c "import json; print(json.load(open('infrastructure-config.json'))['subnet_ids'][0])")
        export SECURITY_GROUP_ID=$(python3 -c "import json; print(json.load(open('infrastructure-config.json'))['security_group_id'])")
        export TASK_EXECUTION_ROLE_ARN=$(python3 -c "import json; print(json.load(open('infrastructure-config.json'))['task_execution_role_arn'])")
    else
        echo -e "${RED}Python3 required to parse infrastructure-config.json${NC}"
        exit 1
    fi
else
    echo -e "${RED}Infrastructure config not found. Run deploy-direct.py first!${NC}"
    exit 1
fi

# Build and push Docker image
echo -e "${GREEN}Building Docker image...${NC}"
docker build -t ${PROJECT_NAME} .

# Tag for ECR
echo -e "${GREEN}Tagging image for ECR...${NC}"
docker tag ${PROJECT_NAME}:latest ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}:latest

# Login to ECR
echo -e "${GREEN}Logging in to ECR...${NC}"
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Push to ECR
echo -e "${GREEN}Pushing image to ECR...${NC}"
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}:latest

# Create task definition
echo -e "${GREEN}Creating task definition...${NC}"
cat > task-definition.json <<EOF
{
  "family": "${TASK_FAMILY}",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "${TASK_EXECUTION_ROLE_ARN}",
  "containerDefinitions": [
    {
      "name": "${PROJECT_NAME}",
      "image": "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}:latest",
      "essential": true,
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/${PROJECT_NAME}",
          "awslogs-region": "${AWS_REGION}",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "environment": [
        {"name": "NODE_ENV", "value": "production"}
      ]
    }
  ]
}
EOF

# Register task definition
TASK_DEF_ARN=$(aws ecs register-task-definition --cli-input-json file://task-definition.json --query 'taskDefinition.taskDefinitionArn' --output text)
echo -e "${GREEN}Registered task definition: ${TASK_DEF_ARN}${NC}"

# Check if service exists
SERVICE_EXISTS=$(aws ecs describe-services --cluster ${ECS_CLUSTER} --services ${ECS_SERVICE} --query 'services[0].serviceName' --output text 2>/dev/null || echo "")

if [ "$SERVICE_EXISTS" == "${ECS_SERVICE}" ]; then
    # Update existing service
    echo -e "${GREEN}Updating existing ECS service...${NC}"
    aws ecs update-service \
        --cluster ${ECS_CLUSTER} \
        --service ${ECS_SERVICE} \
        --task-definition ${TASK_DEF_ARN} \
        --force-new-deployment
else
    # Create new service
    echo -e "${GREEN}Creating new ECS service...${NC}"
    aws ecs create-service \
        --cluster ${ECS_CLUSTER} \
        --service-name ${ECS_SERVICE} \
        --task-definition ${TASK_DEF_ARN} \
        --desired-count 1 \
        --launch-type FARGATE \
        --network-configuration "awsvpcConfiguration={subnets=[${SUBNET_ID}],securityGroups=[${SECURITY_GROUP_ID}],assignPublicIp=ENABLED}"
fi

# Clean up
rm -f task-definition.json

echo -e "${GREEN}Deployment complete!${NC}"
echo -e "${YELLOW}Check the service status:${NC}"
echo "aws ecs describe-services --cluster ${ECS_CLUSTER} --services ${ECS_SERVICE}"