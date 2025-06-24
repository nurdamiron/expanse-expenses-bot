#!/bin/bash

# EC2 Deployment Script for Expanse Bot
set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}  Expanse Bot - EC2 Deployment${NC}"
echo -e "${BLUE}=====================================${NC}"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    exit 1
fi

# Configuration
EC2_HOST=""
EC2_USER="ubuntu"
KEY_PATH=""
PROJECT_DIR="/home/ubuntu/expanse-bot"

# Get EC2 details from user
read -p "Enter EC2 host/IP address: " EC2_HOST
read -p "Enter path to SSH key (.pem file): " KEY_PATH
read -p "EC2 user (default: ubuntu): " input_user
if [ ! -z "$input_user" ]; then
    EC2_USER=$input_user
fi

# Verify SSH key exists
if [ ! -f "$KEY_PATH" ]; then
    echo -e "${RED}Error: SSH key not found at $KEY_PATH${NC}"
    exit 1
fi

# Set proper permissions for SSH key
chmod 400 "$KEY_PATH"

echo -e "${GREEN}Deployment Configuration:${NC}"
echo "- EC2 Host: $EC2_HOST"
echo "- EC2 User: $EC2_USER"
echo "- Project Directory: $PROJECT_DIR"
echo ""

# Create deployment package
echo -e "${YELLOW}Creating deployment package...${NC}"
rm -rf deploy_package.tar.gz
tar -czf deploy_package.tar.gz \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='*.db' \
    --exclude='*.db-shm' \
    --exclude='*.db-wal' \
    --exclude='deploy_package.tar.gz' \
    --exclude='node_modules' \
    --exclude='.DS_Store' \
    .

echo -e "${GREEN}Package created!${NC}"

# Create setup script for EC2
cat > ec2_setup.sh <<'EOF'
#!/bin/bash
set -e

# Update system
echo "Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install Python 3.11
echo "Installing Python 3.11..."
sudo apt-get install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3.11-dev

# Install system dependencies
echo "Installing system dependencies..."
sudo apt-get install -y \
    nginx \
    supervisor \
    git \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-pip \
    mysql-client \
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-kaz

# Install Docker (optional, for future use)
echo "Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Clean up
rm get-docker.sh

echo "System setup complete!"
EOF

# Copy setup script to EC2
echo -e "${YELLOW}Copying setup script to EC2...${NC}"
scp -i "$KEY_PATH" ec2_setup.sh "$EC2_USER@$EC2_HOST:~/"

# Run setup script on EC2
echo -e "${YELLOW}Running system setup on EC2...${NC}"
ssh -i "$KEY_PATH" "$EC2_USER@$EC2_HOST" "chmod +x ~/ec2_setup.sh && ~/ec2_setup.sh"

# Create project directory on EC2
echo -e "${YELLOW}Creating project directory on EC2...${NC}"
ssh -i "$KEY_PATH" "$EC2_USER@$EC2_HOST" "mkdir -p $PROJECT_DIR"

# Copy deployment package to EC2
echo -e "${YELLOW}Copying deployment package to EC2...${NC}"
scp -i "$KEY_PATH" deploy_package.tar.gz "$EC2_USER@$EC2_HOST:$PROJECT_DIR/"

# Extract and setup on EC2
echo -e "${YELLOW}Setting up application on EC2...${NC}"
ssh -i "$KEY_PATH" "$EC2_USER@$EC2_HOST" << ENDSSH
cd $PROJECT_DIR
tar -xzf deploy_package.tar.gz
rm deploy_package.tar.gz

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create systemd service
sudo tee /etc/systemd/system/expanse-bot.service > /dev/null <<'EOL'
[Unit]
Description=Expanse Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin"
ExecStart=$PROJECT_DIR/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOL

# Create nginx configuration (optional, for webhook mode)
sudo tee /etc/nginx/sites-available/expanse-bot > /dev/null <<'EOL'
server {
    listen 80;
    server_name _;
    
    location /webhook {
        proxy_pass http://localhost:8443;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
    }
}
EOL

# Enable nginx site (optional)
# sudo ln -sf /etc/nginx/sites-available/expanse-bot /etc/nginx/sites-enabled/
# sudo nginx -t && sudo systemctl reload nginx

# Reload systemd and start service
sudo systemctl daemon-reload
sudo systemctl enable expanse-bot
sudo systemctl start expanse-bot

echo "Deployment complete!"
echo "Check status with: sudo systemctl status expanse-bot"
echo "View logs with: sudo journalctl -u expanse-bot -f"
ENDSSH

# Clean up local files
rm -f deploy_package.tar.gz ec2_setup.sh

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""
echo "Useful commands:"
echo "- Check status: ssh -i $KEY_PATH $EC2_USER@$EC2_HOST 'sudo systemctl status expanse-bot'"
echo "- View logs: ssh -i $KEY_PATH $EC2_USER@$EC2_HOST 'sudo journalctl -u expanse-bot -f'"
echo "- Restart bot: ssh -i $KEY_PATH $EC2_USER@$EC2_HOST 'sudo systemctl restart expanse-bot'"
echo "- Update bot: Run this script again"
echo ""
echo -e "${YELLOW}Note: Make sure your .env file has the correct MySQL connection string!${NC}"