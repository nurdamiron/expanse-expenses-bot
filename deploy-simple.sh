#!/bin/bash

# Simple deployment script
set -e

# Configuration from environment variables
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID}"
PROJECT_NAME="expanse-expenses-bot"

# Check if AWS credentials are configured
if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo "Error: AWS credentials not found."
    echo "Please set the following environment variables:"
    echo "  export AWS_ACCESS_KEY_ID=your_access_key"
    echo "  export AWS_SECRET_ACCESS_KEY=your_secret_key"
    echo "  export AWS_ACCOUNT_ID=your_account_id"
    exit 1
fi

if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo "Error: AWS_ACCOUNT_ID not set. Please set it as an environment variable."
    exit 1
fi

echo "Starting deployment for ${PROJECT_NAME}..."

# Step 1: Build Docker image
echo "Building Docker image..."
docker build -t ${PROJECT_NAME} .

# Step 2: Run setup script
echo "Setting up AWS infrastructure..."
python3 deploy-direct.py

# Step 3: Deploy to ECS
echo "Deploying to ECS..."
./deploy-ecs.sh

echo "Deployment complete!"