#!/bin/bash
# Quick deployment script for Expanse Bot
# Usage: bash quick_deploy.sh

set -e  # Exit on error

echo "🚀 Starting Expanse Bot deployment..."

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo -e "${RED}This script should not be run as root!${NC}"
   exit 1
fi

# Configuration
BOT_DIR="$HOME/expanse-expenses-bot"
PYTHON_VERSION="python3.10"
SERVICE_NAME="expanse-bot"

echo "📦 Installing system dependencies..."
sudo apt update
sudo apt install -y $PYTHON_VERSION ${PYTHON_VERSION}-venv python3-pip
sudo apt install -y git redis-server mysql-server nginx
sudo apt install -y tesseract-ocr tesseract-ocr-rus tesseract-ocr-kaz
sudo apt install -y supervisor htop tmux

echo "📂 Setting up project directory..."
if [ ! -d "$BOT_DIR" ]; then
    git clone https://github.com/nurdamiron/expanse-expenses-bot.git "$BOT_DIR"
else
    cd "$BOT_DIR"
    git pull origin main
fi

cd "$BOT_DIR"

echo "🐍 Setting up Python environment..."
$PYTHON_VERSION -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "⚙️ Setting up configuration..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${RED}Please edit .env file with your configuration!${NC}"
    echo "Run: nano $BOT_DIR/.env"
    exit 1
fi

echo "🗄️ Setting up database..."
if ! sudo mysql -e "use expanse_bot" 2>/dev/null; then
    echo "Creating database..."
    sudo mysql <<EOF
CREATE DATABASE IF NOT EXISTS expanse_bot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'botuser'@'localhost' IDENTIFIED BY 'BotPassword123!';
GRANT ALL PRIVILEGES ON expanse_bot.* TO 'botuser'@'localhost';
FLUSH PRIVILEGES;
EOF
    
    # Import schema
    mysql -u botuser -p'BotPassword123!' expanse_bot < database/schema.sql
    echo -e "${GREEN}Database created successfully!${NC}"
else
    echo "Database already exists"
fi

echo "📝 Creating systemd service..."
sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null <<EOF
[Unit]
Description=Expanse Telegram Bot
After=network.target mysql.service redis.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$BOT_DIR
Environment="PATH=$BOT_DIR/venv/bin"
ExecStart=$BOT_DIR/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "🔧 Setting up log directory..."
sudo mkdir -p /var/log/$SERVICE_NAME
sudo chown $USER:$USER /var/log/$SERVICE_NAME

echo "🚦 Starting the bot..."
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME

echo "⏰ Setting up auto-updates..."
chmod +x $BOT_DIR/deploy/auto_update.sh

# Add to crontab if not already there
if ! crontab -l 2>/dev/null | grep -q "auto_update.sh"; then
    (crontab -l 2>/dev/null; echo "*/5 * * * * $BOT_DIR/deploy/auto_update.sh") | crontab -
    echo "Auto-update cron job added"
fi

echo "🔍 Checking bot status..."
sleep 3
if sudo systemctl is-active --quiet $SERVICE_NAME; then
    echo -e "${GREEN}✅ Bot is running successfully!${NC}"
    echo ""
    echo "📊 Bot Status:"
    sudo systemctl status $SERVICE_NAME --no-pager
    echo ""
    echo "📝 Useful commands:"
    echo "  - View logs: journalctl -u $SERVICE_NAME -f"
    echo "  - Restart bot: sudo systemctl restart $SERVICE_NAME"
    echo "  - Stop bot: sudo systemctl stop $SERVICE_NAME"
    echo "  - Edit config: nano $BOT_DIR/.env"
else
    echo -e "${RED}❌ Bot failed to start!${NC}"
    echo "Check logs: journalctl -u $SERVICE_NAME -n 50"
    exit 1
fi

echo ""
echo -e "${GREEN}🎉 Deployment completed!${NC}"
echo ""
echo "⚠️  IMPORTANT NEXT STEPS:"
echo "1. Edit database password in .env file"
echo "2. Add your bot token and API keys"
echo "3. Restart the bot: sudo systemctl restart $SERVICE_NAME"