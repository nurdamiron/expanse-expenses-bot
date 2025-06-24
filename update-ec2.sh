#!/bin/bash

# Quick update script for EC2
set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}  Expanse Bot - EC2 Quick Update${NC}"
echo -e "${BLUE}=====================================${NC}"

# Configuration - update these with your EC2 details
EC2_HOST=""
EC2_USER="ubuntu"
KEY_PATH=""
PROJECT_DIR="/home/ubuntu/expanse-bot"

# Read saved config if exists
if [ -f ".ec2_config" ]; then
    source .ec2_config
else
    # Get EC2 details from user
    read -p "Enter EC2 host/IP address: " EC2_HOST
    read -p "Enter path to SSH key (.pem file): " KEY_PATH
    read -p "EC2 user (default: ubuntu): " input_user
    if [ ! -z "$input_user" ]; then
        EC2_USER=$input_user
    fi
    
    # Save config for future use
    cat > .ec2_config <<EOF
EC2_HOST="$EC2_HOST"
EC2_USER="$EC2_USER"
KEY_PATH="$KEY_PATH"
PROJECT_DIR="$PROJECT_DIR"
EOF
    echo -e "${GREEN}Configuration saved to .ec2_config${NC}"
fi

# Verify SSH key exists
if [ ! -f "$KEY_PATH" ]; then
    echo -e "${RED}Error: SSH key not found at $KEY_PATH${NC}"
    exit 1
fi

# Set proper permissions for SSH key
chmod 400 "$KEY_PATH"

echo -e "${GREEN}Update Configuration:${NC}"
echo "- EC2 Host: $EC2_HOST"
echo "- EC2 User: $EC2_USER"
echo "- Project Directory: $PROJECT_DIR"
echo ""

# Create update package (smaller, excludes more files)
echo -e "${YELLOW}Creating update package...${NC}"
rm -rf update_package.tar.gz

# Create a list of files to include
tar -czf update_package.tar.gz \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='*.db' \
    --exclude='*.db-shm' \
    --exclude='*.db-wal' \
    --exclude='*.tar.gz' \
    --exclude='node_modules' \
    --exclude='.DS_Store' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    --exclude='.coverage' \
    --exclude='htmlcov' \
    --exclude='*.log' \
    src/ main.py requirements.txt alembic/ alembic.ini .env

echo -e "${GREEN}Update package created!${NC}"

# Stop the bot service
echo -e "${YELLOW}Stopping bot service...${NC}"
ssh -i "$KEY_PATH" "$EC2_USER@$EC2_HOST" "sudo systemctl stop expanse-bot"

# Backup current version
echo -e "${YELLOW}Creating backup...${NC}"
ssh -i "$KEY_PATH" "$EC2_USER@$EC2_HOST" << ENDSSH
cd $PROJECT_DIR
timestamp=\$(date +%Y%m%d_%H%M%S)
mkdir -p backups
tar -czf backups/backup_\$timestamp.tar.gz src/ main.py requirements.txt alembic/ alembic.ini .env
echo "Backup created: backups/backup_\$timestamp.tar.gz"
ENDSSH

# Copy update package to EC2
echo -e "${YELLOW}Copying update package to EC2...${NC}"
scp -i "$KEY_PATH" update_package.tar.gz "$EC2_USER@$EC2_HOST:$PROJECT_DIR/"

# Apply update on EC2
echo -e "${YELLOW}Applying update on EC2...${NC}"
ssh -i "$KEY_PATH" "$EC2_USER@$EC2_HOST" << ENDSSH
cd $PROJECT_DIR

# Extract update
tar -xzf update_package.tar.gz
rm update_package.tar.gz

# Activate virtual environment and update dependencies
source venv/bin/activate
pip install -r requirements.txt

# Run database migrations if needed
if [ -f "alembic.ini" ]; then
    echo "Running database migrations..."
    alembic upgrade head || echo "No migrations to apply"
fi

# Start the bot service
sudo systemctl start expanse-bot

echo "Update complete!"
ENDSSH

# Clean up local files
rm -f update_package.tar.gz

# Check service status
echo -e "${YELLOW}Checking service status...${NC}"
ssh -i "$KEY_PATH" "$EC2_USER@$EC2_HOST" "sudo systemctl status expanse-bot --no-pager"

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}Update Complete!${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""
echo "Commands:"
echo "- View logs: ssh -i $KEY_PATH $EC2_USER@$EC2_HOST 'sudo journalctl -u expanse-bot -f'"
echo "- Restart: ssh -i $KEY_PATH $EC2_USER@$EC2_HOST 'sudo systemctl restart expanse-bot'"
echo "- Rollback: ssh -i $KEY_PATH $EC2_USER@$EC2_HOST 'cd $PROJECT_DIR && tar -xzf backups/backup_TIMESTAMP.tar.gz'"