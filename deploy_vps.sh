#!/bin/bash
# ============================================================
#  CryptoBhai — VPS One-Click Deploy (Ubuntu 22/24)
#  Ye script VPS pe SIRF EK BAAR chalao:
#    bash deploy_vps.sh
#  Uske baad bot 24/7 chalega — laptop band ho tab bhi!
# ============================================================
set -e
cd "$(dirname "$0")"

echo "=========================================="
echo "  CryptoBhai VPS Deploy shuru..."
echo "=========================================="

# 1. System packages
echo "[1/6] System packages install..."
apt update -y -qq
apt install -y -qq python3 python3-venv python3-pip > /dev/null

# 2. Files copy karo /opt/cryptobhai me
echo "[2/6] Files copy..."
mkdir -p /opt/cryptobhai
rsync -a --exclude data/cache --exclude __pycache__ ./ /opt/cryptobhai/
cd /opt/cryptobhai

# 3. Token check
echo "[3/6] Token check..."
if [ ! -f .env ]; then
  echo ""
  echo "  Telegram me @BotFather kholo -> /mybots -> apna bot"
  echo "  -> API Token -> copy karo aur neeche paste karo."
  echo ""
  read -p "Token: " TOKEN
  echo "TELEGRAM_TOKEN=$TOKEN" > .env
fi

# 4. Python dependencies
echo "[4/6] Python dependencies (1-2 min)..."
python3 -m venv venv
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q -r requirements.txt

# 5. Systemd service (ye hi asli jaadu hai — reboot/crash pe auto-start)
echo "[5/6] 24/7 service install..."
cp cryptobhai.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable cryptobhai > /dev/null 2>&1
systemctl restart cryptobhai

# 6. Status
echo "[6/6] Status check..."
sleep 3
if systemctl is-active --quiet cryptobhai; then
  echo ""
  echo "=========================================="
  echo "  🎉 DEPLOY SUCCESS! Bot ab 24/7 chal raha hai"
  echo ""
  echo "  • Laptop/PC band karo — bot VPS pe chalega"
  echo "  • Server reboot pe bhi khud start hoga"
  echo ""
  echo "  Useful commands:"
  echo "    systemctl status cryptobhai   # status dekho"
  echo "    journalctl -u cryptobhai -f   # live logs"
  echo "    systemctl restart cryptobhai  # restart"
  echo "=========================================="
else
  echo "❌ Service start nahi hui. Logs dekho:"
  journalctl -u cryptobhai -n 20 --no-pager
  echo ""
  echo "Zyada tar problem .env ka token galat hota hai."
  echo "Fix: nano /opt/cryptobhai/.env -> token sahi karo ->"
  echo "     systemctl restart cryptobhai"
fi
