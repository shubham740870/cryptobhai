#!/data/data/com.termux/files/usr/bin/bash
# ============================================
#  CryptoBhai Bot - Termux (Android) starter
#  Chalane ke liye: bash start_termux.sh
# ============================================
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo ""
  echo "  Pehli baar setup chal raha hai..."
  echo "  Telegram me @BotFather kholo, /newbot bhejo,"
  echo "  aur jo TOKEN mile wo yahan paste karo."
  echo ""
  read -p "Token yahan paste karo: " TOKEN
  echo "TELEGRAM_TOKEN=$TOKEN" > .env
  echo ""
fi

echo "Dependencies check ho rahi hai (pehli baar me 2-3 min)..."
pip install -q requests matplotlib 2>/dev/null || pkg install python -y

echo ""
echo "============================================"
echo "  Bot chalu! Terminal BAND MAT karna."
echo "  (Screen off hone pe band na ho isliye:"
echo "   alag se 'termux-wake-lock' chala sakte ho)"
echo "============================================"
echo ""
python agent.py
