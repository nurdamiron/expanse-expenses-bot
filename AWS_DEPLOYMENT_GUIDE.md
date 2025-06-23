# AWS Deployment Guide for Expanse Expenses Bot

## Prerequisites

1. AWS Account
2. AWS CLI installed and configured
3. Docker installed
4. Domain name (optional, for webhook)

## Architecture Overview

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│                 │     │              │     │                 │
│  Telegram API   │────▶│  AWS ECS/    │────▶│  RDS PostgreSQL │
│                 │     │  EC2         │     │                 │
└─────────────────┘     └──────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │              │
                        │  Redis       │
                        │  (ElastiCache)│
                        └──────────────┘
```

## Step 1: Prepare Application

### 1.1 Create Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

# Run the bot
CMD ["python", "main.py"]
```

### 1.2 Create docker-compose for local testing

```yaml
# docker-compose.yml
version: '3.8'

services:
  bot:
    build: .
    env_file:
      - .env
    depends_on:
      - postgres
      - redis
    volumes:
      - ./data:/app/data
    restart: unless-stopped

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: expenses_bot
      POSTGRES_USER: bot_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

## Step 2: Set up AWS Infrastructure

### 2.1 Create RDS PostgreSQL

```bash
# Create DB subnet group
aws rds create-db-subnet-group \
    --db-subnet-group-name expenses-bot-subnet \
    --db-subnet-group-description "Subnet group for expenses bot" \
    --subnet-ids subnet-xxx subnet-yyy

# Create RDS instance
aws rds create-db-instance \
    --db-instance-identifier expenses-bot-db \
    --db-instance-class db.t3.micro \
    --engine postgres \
    --engine-version 15 \
    --master-username botadmin \
    --master-user-password YOUR_SECURE_PASSWORD \
    --allocated-storage 20 \
    --db-subnet-group-name expenses-bot-subnet \
    --vpc-security-group-ids sg-xxx \
    --backup-retention-period 7 \
    --no-publicly-accessible
```

### 2.2 Create ElastiCache Redis

```bash
# Create Redis cluster
aws elasticache create-cache-cluster \
    --cache-cluster-id expenses-bot-redis \
    --cache-node-type cache.t3.micro \
    --engine redis \
    --num-cache-nodes 1 \
    --cache-subnet-group-name expenses-bot-subnet \
    --security-group-ids sg-xxx
```

### 2.3 Create S3 bucket for receipts (optional)

```bash
# Create S3 bucket
aws s3 mb s3://expenses-bot-receipts-YOUR_UNIQUE_ID

# Set bucket policy for private access
aws s3api put-bucket-policy --bucket expenses-bot-receipts-YOUR_UNIQUE_ID \
    --policy file://bucket-policy.json
```

## Step 3: Deploy with ECS (Recommended)

### 3.1 Create ECR repository

```bash
# Create ECR repository
aws ecr create-repository --repository-name expenses-bot

# Get login token
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com

# Build and push image
docker build -t expenses-bot .
docker tag expenses-bot:latest YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/expenses-bot:latest
docker push YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/expenses-bot:latest
```

### 3.2 Create ECS Task Definition

```json
{
  "family": "expenses-bot",
  "taskRoleArn": "arn:aws:iam::YOUR_ACCOUNT:role/ecsTaskRole",
  "executionRoleArn": "arn:aws:iam::YOUR_ACCOUNT:role/ecsTaskExecutionRole",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "containerDefinitions": [
    {
      "name": "expenses-bot",
      "image": "YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/expenses-bot:latest",
      "essential": true,
      "environment": [
        {
          "name": "APP_ENV",
          "value": "production"
        }
      ],
      "secrets": [
        {
          "name": "BOT_TOKEN",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT:secret:expenses-bot-secrets:BOT_TOKEN::"
        },
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT:secret:expenses-bot-secrets:DATABASE_URL::"
        },
        {
          "name": "REDIS_HOST",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT:secret:expenses-bot-secrets:REDIS_HOST::"
        },
        {
          "name": "OPENAI_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT:secret:expenses-bot-secrets:OPENAI_API_KEY::"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/expenses-bot",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

### 3.3 Create ECS Service

```bash
# Create ECS cluster
aws ecs create-cluster --cluster-name expenses-bot-cluster

# Create service
aws ecs create-service \
    --cluster expenses-bot-cluster \
    --service-name expenses-bot-service \
    --task-definition expenses-bot:1 \
    --desired-count 1 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx,subnet-yyy],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

## Step 4: Alternative - Deploy with EC2

### 4.1 Launch EC2 instance

```bash
# Launch EC2 instance
aws ec2 run-instances \
    --image-id ami-0c02fb55956c7d316 \
    --instance-type t3.micro \
    --key-name your-key-pair \
    --security-group-ids sg-xxx \
    --subnet-id subnet-xxx \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=expenses-bot}]'
```

### 4.2 Setup on EC2

```bash
# Connect to EC2
ssh -i your-key.pem ec2-user@YOUR_EC2_IP

# Install Docker
sudo yum update -y
sudo yum install -y docker git
sudo service docker start
sudo usermod -a -G docker ec2-user

# Install docker-compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Clone repository
git clone https://github.com/YOUR_USERNAME/expanse-expenses-bot.git
cd expanse-expenses-bot

# Create .env file
cat > .env << EOF
BOT_TOKEN=YOUR_BOT_TOKEN
DATABASE_URL=postgresql+asyncpg://botadmin:PASSWORD@YOUR_RDS_ENDPOINT:5432/expenses_bot
REDIS_HOST=YOUR_REDIS_ENDPOINT
REDIS_PORT=6379
OPENAI_API_KEY=YOUR_OPENAI_KEY
APP_ENV=production
EOF

# Run with docker-compose
docker-compose up -d
```

## Step 5: Environment Variables for AWS

Update your `.env` file for production:

```env
# Bot Configuration
BOT_TOKEN=YOUR_BOT_TOKEN
BOT_USERNAME=ExpenseTrackerBot

# Database Configuration - RDS PostgreSQL
DATABASE_URL=postgresql+asyncpg://botadmin:PASSWORD@expenses-bot-db.xxx.rds.amazonaws.com:5432/expenses_bot

# Redis Configuration - ElastiCache
REDIS_HOST=expenses-bot-redis.xxx.cache.amazonaws.com
REDIS_PORT=6379
REDIS_DB=0

# AWS Configuration (optional for S3)
AWS_ACCESS_KEY_ID=YOUR_ACCESS_KEY
AWS_SECRET_ACCESS_KEY=YOUR_SECRET_KEY
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET_NAME=expenses-bot-receipts-YOUR_UNIQUE_ID

# Application Settings
APP_ENV=production
LOG_LEVEL=INFO
TIMEZONE=Asia/Almaty
DEFAULT_LANGUAGE=ru
DEFAULT_CURRENCY=KZT

# Feature Flags
ENABLE_OCR=true
ENABLE_CURRENCY_CONVERSION=true
ENABLE_NOTIFICATIONS=true
ENABLE_EXPORT=true

# OpenAI Configuration
OPENAI_API_KEY=YOUR_OPENAI_KEY
USE_OPENAI_VISION=true

# Currency API Keys (optional)
FIXER_API_KEY=
EXCHANGERATE_API_KEY=

# Rate Limiting
MAX_TRANSACTIONS_PER_DAY=100
MAX_IMAGE_SIZE_MB=20
RATE_LIMIT_REQUESTS_PER_MINUTE=60
```

## Step 6: Monitoring and Logging

### 6.1 CloudWatch Logs

```bash
# Create log group
aws logs create-log-group --log-group-name /ecs/expenses-bot

# Set retention
aws logs put-retention-policy \
    --log-group-name /ecs/expenses-bot \
    --retention-in-days 30
```

### 6.2 CloudWatch Alarms

```bash
# Create CPU alarm
aws cloudwatch put-metric-alarm \
    --alarm-name expenses-bot-cpu-high \
    --alarm-description "Alarm when CPU exceeds 80%" \
    --metric-name CPUUtilization \
    --namespace AWS/ECS \
    --statistic Average \
    --period 300 \
    --threshold 80 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 2
```

## Step 7: Backup and Disaster Recovery

### 7.1 RDS Automated Backups
- Already enabled with 7-day retention
- Create manual snapshots before major updates

### 7.2 Database backup script

```bash
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="expenses_bot_backup_$DATE.sql"

# Create backup
pg_dump $DATABASE_URL > $BACKUP_FILE

# Upload to S3
aws s3 cp $BACKUP_FILE s3://expenses-bot-backups/$BACKUP_FILE

# Clean up local file
rm $BACKUP_FILE
```

## Step 8: CI/CD with GitHub Actions

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to AWS

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v2
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: us-east-1
    
    - name: Login to Amazon ECR
      id: login-ecr
      uses: aws-actions/amazon-ecr-login@v1
    
    - name: Build, tag, and push image to Amazon ECR
      env:
        ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
        ECR_REPOSITORY: expenses-bot
        IMAGE_TAG: ${{ github.sha }}
      run: |
        docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
        docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
        docker tag $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG $ECR_REGISTRY/$ECR_REPOSITORY:latest
        docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest
    
    - name: Update ECS service
      run: |
        aws ecs update-service \
          --cluster expenses-bot-cluster \
          --service expenses-bot-service \
          --force-new-deployment
```

## Estimated AWS Costs (Monthly)

- **ECS Fargate** (256 CPU, 512 Memory): ~$10
- **RDS PostgreSQL** (db.t3.micro): ~$15
- **ElastiCache Redis** (cache.t3.micro): ~$13
- **CloudWatch Logs**: ~$5
- **Total**: ~$43/month

Alternative with EC2:
- **EC2** (t3.micro): ~$8
- **RDS PostgreSQL** (db.t3.micro): ~$15
- **Total**: ~$23/month (without Redis)

## Security Best Practices

1. **Use AWS Secrets Manager** for sensitive data
2. **Enable VPC** for internal communication
3. **Use Security Groups** to restrict access
4. **Enable encryption** for RDS and S3
5. **Regular security updates** for Docker images
6. **Monitor with CloudWatch** for suspicious activity

## Troubleshooting

### Bot not starting
```bash
# Check ECS logs
aws logs tail /ecs/expenses-bot --follow

# Check task status
aws ecs describe-tasks --cluster expenses-bot-cluster --tasks TASK_ARN
```

### Database connection issues
- Check security group rules
- Verify RDS endpoint
- Test connection from EC2/ECS subnet

### Redis connection issues
- Check ElastiCache endpoint
- Verify security group allows Redis port 6379