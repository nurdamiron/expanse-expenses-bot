# EC2 Deployment Guide for Expanse Bot

## Prerequisites

1. **EC2 Instance**
   - Ubuntu 22.04 LTS (recommended)
   - Instance type: t2.micro or t3.micro (for free tier)
   - Security group with ports:
     - 22 (SSH)
     - 80 (HTTP) - optional for webhook
     - 443 (HTTPS) - optional for webhook

2. **AWS RDS MySQL** (already configured)
   - Endpoint: expanse.cde42ec8m1u7.eu-north-1.rds.amazonaws.com
   - Port: 3306
   - Database: expanse_bot

3. **Local Requirements**
   - SSH key (.pem file) for EC2 access
   - Git installed locally

## Initial Deployment

1. **Prepare for deployment**
   ```bash
   # Make sure .env file is configured with MySQL connection
   # DATABASE_URL should point to your RDS instance
   ```

2. **Run the deployment script**
   ```bash
   ./deploy-ec2.sh
   ```
   
   The script will:
   - Ask for your EC2 host/IP
   - Ask for SSH key path
   - Install all system dependencies on EC2
   - Deploy the bot code
   - Set up systemd service for auto-restart
   - Start the bot

3. **Verify deployment**
   ```bash
   # Check service status
   ssh -i your-key.pem ubuntu@your-ec2-ip 'sudo systemctl status expanse-bot'
   
   # View logs
   ssh -i your-key.pem ubuntu@your-ec2-ip 'sudo journalctl -u expanse-bot -f'
   ```

## Updating the Bot

For quick updates after initial deployment:

```bash
./update-ec2.sh
```

This script will:
- Stop the bot
- Create a backup
- Deploy new code
- Update dependencies
- Run database migrations
- Restart the bot

## Manual Commands

### SSH to EC2
```bash
ssh -i your-key.pem ubuntu@your-ec2-ip
```

### Service Management
```bash
# Start bot
sudo systemctl start expanse-bot

# Stop bot
sudo systemctl stop expanse-bot

# Restart bot
sudo systemctl restart expanse-bot

# View status
sudo systemctl status expanse-bot

# View logs
sudo journalctl -u expanse-bot -f

# View last 100 lines of logs
sudo journalctl -u expanse-bot -n 100
```

### Manual Update Steps
```bash
# Connect to EC2
ssh -i your-key.pem ubuntu@your-ec2-ip

# Navigate to project
cd /home/ubuntu/expanse-bot

# Pull latest changes (if using git)
git pull

# Or copy files manually and then:
source venv/bin/activate
pip install -r requirements.txt

# Run migrations if needed
alembic upgrade head

# Restart service
sudo systemctl restart expanse-bot
```

## Troubleshooting

### Bot not starting
1. Check logs: `sudo journalctl -u expanse-bot -n 100`
2. Check .env file exists and has correct values
3. Verify MySQL connection from EC2 to RDS
4. Check Python dependencies installed correctly

### Database connection issues
1. Verify RDS security group allows connection from EC2
2. Check DATABASE_URL in .env is correct
3. Test connection: `mysql -h your-rds-endpoint -u admin -p`

### Permission issues
```bash
# Fix ownership
sudo chown -R ubuntu:ubuntu /home/ubuntu/expanse-bot

# Fix permissions
chmod -R 755 /home/ubuntu/expanse-bot
```

## Monitoring

### Set up CloudWatch (optional)
1. Install CloudWatch agent on EC2
2. Configure to send systemd logs
3. Create alarms for service failures

### Basic monitoring
```bash
# Check disk space
df -h

# Check memory
free -m

# Check CPU
top

# Check bot process
ps aux | grep python
```

## Backup

### Manual backup
```bash
cd /home/ubuntu/expanse-bot
tar -czf backup_$(date +%Y%m%d_%H%M%S).tar.gz src/ main.py .env alembic/
```

### Automated backup (cron)
```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * cd /home/ubuntu/expanse-bot && tar -czf backups/backup_$(date +\%Y\%m\%d).tar.gz src/ main.py .env alembic/
```

## Security Best Practices

1. **Keep EC2 updated**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. **Use SSH key only** (disable password auth)

3. **Restrict security groups** to minimum required ports

4. **Store sensitive data** in environment variables, not in code

5. **Regular backups** of both code and database

6. **Monitor logs** for suspicious activity

## Cost Optimization

1. Use t2.micro or t3.micro for free tier eligibility
2. Stop instance when not needed for testing
3. Use RDS free tier (db.t3.micro)
4. Set up billing alerts in AWS

## Additional Features

### Enable Webhook Mode (optional)
1. Get a domain and SSL certificate
2. Configure nginx as reverse proxy
3. Update bot to use webhook instead of polling
4. Open port 443 in security group

### Add Redis Cache (optional)
1. Install Redis on EC2 or use ElastiCache
2. Update .env with Redis connection
3. Restart bot

### Enable Hot Reload (development)
1. Set ENABLE_HOT_RELOAD=true in .env
2. Bot will auto-reload on code changes
3. Useful for development, not recommended for production