# 🐱 MeowBot — Pi 5 / Ubuntu Setup

A Discord bot that takes live screenshots from meow.camera and posts them, with both **slash commands** and legacy `s!` prefix commands.

---

## Quick Start on your Pi 5

### 1. Transfer files
Copy this folder to your Pi (via SCP, USB, or git):
```bash
scp -r meowbot/ ubuntu@<your-pi-ip>:~/meowbot
```

### 2. Run the setup script
```bash
cd ~/meowbot
bash setup.sh
```
This installs Chromium, chromedriver, Python deps, and registers a systemd service.

### 3. Add your bot token
```bash
nano ~/meowbot/.env
```
Paste your **new** bot token (invalidate the old one in the Discord Developer Portal first!).

Optionally add your server ID for instant slash command registration:
```
DISCORD_GUILD_ID=123456789012345678
```

### 4. Start the bot
```bash
sudo systemctl start meowbot
sudo systemctl status meowbot   # should show "active (running)"
journalctl -u meowbot -f        # live logs
```

---

## Commands

| Slash Command | Prefix | Description |
|---|---|---|
| `/photo cat:[name] view:[angle]` | `s!photo <name> [top\|back]` | Take a photo of a cat |
| `/cats` | `s!cats` | List all available cats |

Cat names with spaces: use underscores in the prefix version (`s!photo Mr.Fresh`). Slash commands show a dropdown so no typing needed.

---

## Managing the service

```bash
sudo systemctl stop meowbot       # stop
sudo systemctl restart meowbot    # restart after code changes
sudo systemctl disable meowbot    # don't start on boot
journalctl -u meowbot --since "1 hour ago"  # recent logs
```

---

## Troubleshooting

**`chromedriver` not found**
```bash
which chromedriver        # should print /usr/bin/chromedriver
sudo apt install chromium-chromedriver
```

**Slash commands not showing up**
- If `DISCORD_GUILD_ID` is set → they appear instantly in that server.
- If not set → global sync takes up to 1 hour.

**Bot crashes with "out of memory"**
- The Pi 5 has enough RAM, but Chromium is heavy. The semaphore in the code limits to 1 concurrent screenshot. If you still have issues, add swap:
```bash
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

**Bot token error**
- The old token in your code is now public and must be revoked. Go to [Discord Developer Portal](https://discord.com/developers/applications) → your app → Bot → Reset Token.
