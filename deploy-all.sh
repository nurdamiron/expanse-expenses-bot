#!/bin/bash

# Complete AWS Deployment Script
set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}  Expanse Expenses Bot AWS Deployment${NC}"
echo -e "${BLUE}=====================================${NC}"

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"


# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo -e "${RED}AWS CLI is not installed. Installing...${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
        sudo installer -pkg AWSCLIV2.pkg -target /
        rm AWSCLIV2.pkg
    else
        echo "Please install AWS CLI manually: https://aws.amazon.com/cli/"
        exit 1
    fi
fi

# Check .env file
if [ ! -f ".env" ]; then
    echo -e "${RED}.env file not found!${NC}"
    echo "Please create .env file with at least:"
    echo "BOT_TOKEN=your-telegram-bot-token"
    echo "OPENAI_API_KEY=your-openai-api-key"
    exit 1
fi

# Load environment variables
source .env

# Export for scripts
export BOT_TOKEN
export OPENAI_API_KEY

echo -e "${GREEN}Prerequisites checked!${NC}"

# Step 1: Build and push Docker image
echo -e "${BLUE}Step 1: Building and pushing Docker image...${NC}"
./deploy-aws.sh

# Step 2: Setup infrastructure
echo -e "${BLUE}Step 2: Setting up AWS infrastructure...${NC}"
./setup-infrastructure.sh

# Step 3: Deploy to ECS
echo -e "${BLUE}Step 3: Deploying to ECS...${NC}"
./deploy-ecs.sh

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}  Deployment Complete!${NC}"
echo -e "${GREEN}=====================================${NC}"

echo -e "${YELLOW}Your bot is now running on AWS!${NC}"
echo -e "${YELLOW}Monitor logs with:${NC}"
echo "aws logs tail /ecs/expanse-expenses-bot --follow"

echo -e "${YELLOW}AWS Console:${NC}"
echo "https://console.aws.amazon.com/ecs/home?region=us-east-1#/clusters/expanse-expenses-bot-cluster/services"