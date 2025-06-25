#!/bin/bash

# Infrastructure Setup Script
set -e

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID}"
PROJECT_NAME="expanse-expenses-bot"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Setting up AWS infrastructure for ${PROJECT_NAME}...${NC}"

# Check if AWS credentials are configured
if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo -e "${RED}AWS credentials not found.${NC}"
    echo "Please set the following environment variables:"
    echo "  export AWS_ACCESS_KEY_ID=your_access_key"
    echo "  export AWS_SECRET_ACCESS_KEY=your_secret_key"
    echo "  export AWS_ACCOUNT_ID=your_account_id"
    exit 1
fi

if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo -e "${RED}AWS_ACCOUNT_ID not set. Please set it as an environment variable.${NC}"
    exit 1
fi

# Check dependencies
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is required but not installed.${NC}"
    exit 1
fi

if ! command -v aws &> /dev/null; then
    echo -e "${RED}AWS CLI is required but not installed.${NC}"
    exit 1
fi

# Install boto3 if not available
echo -e "${YELLOW}Checking Python dependencies...${NC}"
python3 -c "import boto3" 2>/dev/null || {
    echo -e "${YELLOW}Installing boto3...${NC}"
    pip3 install boto3
}

# Run the infrastructure setup
echo -e "${GREEN}Running infrastructure setup...${NC}"
python3 deploy-direct.py

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Infrastructure setup completed successfully!${NC}"
    echo -e "${YELLOW}Configuration saved to infrastructure-config.json${NC}"
else
    echo -e "${RED}Infrastructure setup failed!${NC}"
    exit 1
fi