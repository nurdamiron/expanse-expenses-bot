#!/bin/bash
# One-line VPS deployment script
# Usage: curl -sSL https://raw.githubusercontent.com/nurdamiron/expanse-expenses-bot/main/deploy/install_on_vps.sh | bash

set -e

echo "
███████╗██╗  ██╗██████╗  █████╗ ███╗   ██╗███████╗███████╗    ██████╗  ██████╗ ████████╗
██╔════╝╚██╗██╔╝██╔══██╗██╔══██╗████╗  ██║██╔════╝██╔════╝    ██╔══██╗██╔═══██╗╚══██╔══╝
█████╗   ╚███╔╝ ██████╔╝███████║██╔██╗ ██║███████╗█████╗      ██████╔╝██║   ██║   ██║   
██╔══╝   ██╔██╗ ██╔═══╝ ██╔══██║██║╚██╗██║╚════██║██╔══╝      ██╔══██╗██║   ██║   ██║   
███████╗██╔╝ ██╗██║     ██║  ██║██║ ╚████║███████║███████╗    ██████╔╝╚██████╔╝   ██║   
╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝╚══════╝    ╚═════╝  ╚═════╝    ╚═╝   
"

# Check OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
    VER=$VERSION_ID
else
    echo "Cannot determine OS version"
    exit 1
fi

# Install dependencies based on OS
case $OS in
    "Ubuntu"|"Debian GNU/Linux")
        echo "📦 Installing dependencies for $OS $VER..."
        sudo apt update
        sudo apt install -y curl git python3.10 python3.10-venv python3-pip
        ;;
    "CentOS Linux"|"Red Hat Enterprise Linux")
        echo "📦 Installing dependencies for $OS $VER..."
        sudo yum install -y curl git python310 python310-devel
        ;;
    *)
        echo "Unsupported OS: $OS"
        exit 1
        ;;
esac

# Create bot user if doesn't exist
if ! id "botuser" &>/dev/null; then
    echo "👤 Creating bot user..."
    sudo useradd -m -s /bin/bash botuser
fi

# Switch to bot user and continue installation
echo "🚀 Continuing installation as botuser..."
sudo -u botuser bash << 'EOF'
cd ~

# Clone repository
if [ ! -d "expanse-expenses-bot" ]; then
    echo "📂 Cloning repository..."
    git clone https://github.com/nurdamiron/expanse-expenses-bot.git
fi

cd expanse-expenses-bot

# Run quick deploy script
chmod +x deploy/quick_deploy.sh
bash deploy/quick_deploy.sh
EOF

echo ""
echo "✅ Installation completed!"
echo ""
echo "Next steps:"
echo "1. Edit configuration: sudo -u botuser nano /home/botuser/expanse-expenses-bot/.env"
echo "2. Add your bot token and API keys"
echo "3. Restart bot: sudo systemctl restart expanse-bot"
echo ""
echo "View logs: sudo journalctl -u expanse-bot -f"