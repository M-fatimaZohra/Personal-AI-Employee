#!/bin/bash
# setup_vm.sh — Platinum Tier Azure VM provisioning script
# Run this script on the Azure VM after first SSH connection
# Usage: bash setup_vm.sh

set -e  # Exit on any error

echo "=========================================="
echo "Platinum Tier VM Setup"
echo "=========================================="
echo ""

# Update system
echo "[1/10] Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Python 3.13
echo "[2/10] Installing Python 3.13..."
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt install python3.13 python3.13-venv python3.13-dev python3-pip -y

# Install uv (Python package manager)
echo "[3/10] Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc

# Install Node.js 24
echo "[4/10] Installing Node.js 24..."
curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
sudo apt install -y nodejs

# Install PM2 (process manager)
echo "[5/10] Installing PM2..."
sudo npm install -g pm2

# Install Docker
echo "[6/10] Installing Docker..."
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker ubuntu
echo "Note: You'll need to log out and back in for Docker group to take effect"

# Install nginx (for Odoo HTTPS reverse proxy)
echo "[7/10] Installing nginx..."
sudo apt install nginx -y

# Install fail2ban (SSH brute force protection)
echo "[8/10] Installing fail2ban..."
sudo apt install fail2ban -y
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Harden SSH
echo "[9/10] Hardening SSH configuration..."
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sudo sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart sshd

# Install git (for vault sync)
echo "[10/10] Installing git..."
sudo apt install git -y

# Create Claude Code junctions (skills and hooks from shared/)
echo "[11/11] Creating Claude Code junctions..."
mkdir -p ~/cloud/.claude
cd ~/cloud

# Create junctions using ln -s (Linux symlinks, not Windows junctions)
ln -sf ../shared/.claude/skills .claude/skills
ln -sf ../shared/.claude/hooks .claude/hooks

# Copy settings files
cp ../shared/.claude/settings.json .claude/
cp ../shared/.claude/settings.local.json .claude/

echo "Claude Code junctions created:"
echo "  .claude/skills -> shared/.claude/skills"
echo "  .claude/hooks -> shared/.claude/hooks"

echo ""
echo "=========================================="
echo "VM Setup Complete!"
echo "=========================================="
echo ""
echo "Installed:"
echo "  - Python 3.13 + uv"
echo "  - Node.js 24 + PM2"
echo "  - Docker + docker-compose"
echo "  - nginx"
echo "  - fail2ban"
echo "  - git"
echo ""
echo "Security:"
echo "  - SSH password authentication disabled"
echo "  - Root login disabled"
echo "  - fail2ban active"
echo ""
echo "Architecture:"
echo "  - Claude Code skills/hooks via symlinks to shared/"
echo "  - Single source of truth for agent intelligence"
echo ""
echo "Next steps:"
echo "  1. Log out and back in (for Docker group)"
echo "  2. Run transfer_secrets.sh from local machine"
echo "  3. Set up vault-sync Git repo"
echo "  4. Deploy cloud agent code"
echo ""
