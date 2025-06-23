# Deployment Checklist for Expanse Expenses Bot

## Prerequisites
- [ ] Docker Desktop installed
- [ ] AWS CLI v2 installed
- [ ] AWS credentials configured

## AWS Resources to Create
- [ ] VPC (use default)
- [ ] Security Groups:
  - [ ] expanse-expenses-bot-ecs-sg (for ECS tasks)
  - [ ] expanse-expenses-bot-rds-sg (for RDS)
  - [ ] expanse-expenses-bot-redis-sg (for Redis)
- [ ] RDS PostgreSQL:
  - Instance: expanse-expenses-bot-db
  - Type: db.t3.micro
  - Engine: PostgreSQL 15
  - Username: botadmin
  - Password: (secure password)
- [ ] ElastiCache Redis:
  - Cluster: expanse-expenses-bot-redis
  - Type: cache.t3.micro
- [ ] ECR Repository: expanse-expenses-bot
- [ ] ECS Cluster: expanse-expenses-bot-cluster
- [ ] ECS Service: expanse-expenses-bot-service
- [ ] CloudWatch Log Group: /ecs/expanse-expenses-bot

## Environment Variables (store in AWS Secrets Manager)
- BOT_TOKEN=YOUR_BOT_TOKEN_HERE
- OPENAI_API_KEY=YOUR_OPENAI_API_KEY_HERE
- DATABASE_URL=postgresql+asyncpg://botadmin:PASSWORD@RDS_ENDPOINT:5432/expenses_bot
- REDIS_HOST=REDIS_ENDPOINT
- REDIS_PORT=6379
- DEFAULT_LANGUAGE=ru
- DEFAULT_CURRENCY=KZT
- TIMEZONE=Asia/Almaty

## Deployment Steps
1. Build Docker image
2. Push to ECR
3. Create ECS task definition
4. Deploy ECS service

## Post-Deployment
- [ ] Check ECS service is running
- [ ] Monitor CloudWatch logs
- [ ] Test bot functionality
