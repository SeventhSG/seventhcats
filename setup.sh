#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# MeowBot setup script for Ubuntu on Raspberry Pi 5 (ARM64)
# Run as your normal user (not root). sudo will be invoked where needed.
# Usage: bash setup.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BOT_USER="$(whoami)"
SERVICE_FILE="meowbot.service"

echo "=== [1/6] Updating apt packages ==="
sudo apt update && sudo apt upgrade -y

echo "=== [2/6] Installing system dependencies ==="
sudo apt install -y \
    python3 python3-pip python3-venv \
    chromium-browser chromium-chromedriver \
    fonts-liberation \
    libatk-bridge2.0-0 libgtk-3-0 \
    --no-install-recommends

# Confirm chromedriver location
CHROMEDRIVER_PATH="$(which chromedriver 2>/dev/null || echo '/usr/bin/chromedriver')"
echo "    chromedriver found at: $CHROMEDRIVER_PATH"

echo "=== [3/6] Creating Python virtual environment ==="
cd "$SCRIPT_DIR"
python3 -m venv venv
source venv/bin/activate

echo "=== [4/6] Installing Python packages ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== [5/6] Setting up .env ==="
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "  ⚠️  Please edit .env and add your DISCORD_TOKEN before continuing."
    echo "  Run:  nano $SCRIPT_DIR/.env"
    echo ""
else
    echo "  .env already exists, skipping."
fi

echo "=== [6/6] Installing systemd service ==="
# Patch the service file with the real user and path
sed \
    -e "s|/home/ubuntu/meowbot|$SCRIPT_DIR|g" \
    -e "s|User=ubuntu|User=$BOT_USER|g" \
    "$SERVICE_FILE" | sudo tee /etc/systemd/system/meowbot.service > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable meowbot.service

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit your token:   nano $SCRIPT_DIR/.env"
echo "  2. Start the bot:     sudo systemctl start meowbot"
echo "  3. Check status:      sudo systemctl status meowbot"
echo "  4. Watch live logs:   journalctl -u meowbot -f"
echo ""
