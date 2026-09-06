# 🆓 FREE Setup Guide — Bot 24/7 Kaise Chalaye (Laptop Band Ho Tab Bhi)

Do FREE raste hain. Jo available hai wo chuno:

| | Tarika A: 📱 Purana Android Phone | Tarika B: ☁️ Oracle Cloud VPS |
|---|---|---|
| Cost | ₹0 (bilkul free) | ₹0 (free forever tier) |
| Kya chahiye | Koi bhi purana Android phone | Credit/Debit card (verification ke liye) |
| Mushkil | 🟢 Aasan | 🟡 Thodi technical |
| Reliability | Achhi (phone on rahe) | Best (real server) |

**Meri salah**: Spare phone ghar me pada hai → **Tarika A**. Nahi hai aur card
hai → **Tarika B**.

---

# ⚠️ SABSE PEHLE: Ye Zaroor Karo

Bot **ek time pe sirf EK jagah** chal sakta hai. Agar laptop pe already chal
raha hai to pehle usko band karo (black window me `Ctrl+C` dabao ya window
close kar do), **fir** naya setup karo. Warna "Conflict" error aayega.

Apna TOKEN wapas lene ke liye: Telegram → @BotFather → `/mybots` → apna bot
→ **API Token** → copy.

---

# 📱 TARIKA A: Purana Android Phone (Termux) — Full Steps

## A1. Termux Install Karo (5 min)

1. Phone me browser kholo → ye link kholo:
   **https://f-droid.org/en/packages/com.termux/**
2. **Download APK** button dabao → download hoke install karo
   (agar bole "unknown apps allow karo" → Settings me jaake allow kar do)
3. ⚠️ **Play Store wala Termux MAT lena** — wo purana/broken hai

## A2. Termux Me Python Setup (5 min)

Termux kholo aur ye commands ek-ek karke chalao:

```bash
pkg update -y && pkg upgrade -y
pkg install python -y
pip install requests matplotlib
```

(2-5 min lagega. Agar beech me koi [y/N] pooche to `y` Enter kar do)

## A3. Bot Ki Files Phone Me Lao (3 min)

1. Apne **laptop/browser me** `crypto-agent.zip` download karo (chat se)
2. Phone me us zip ko **Download folder** me rakho (USB/file manager se)
3. Termux me:

```bash
termux-setup-storage
```
(Popup aaye to **Allow** karo)

```bash
cd ~
unzip /sdcard/Download/crypto-agent.zip
cd crypto-agent
```

(agar unzip na mile: `pkg install unzip -y`)

## A4. Token Daalo (1 min)

```bash
echo "TELEGRAM_TOKEN=yahan_apna_token_paste_karo" > .env
```

Apna real token `yahan_apna_token_paste_karo` ki jagah likho
(bina space ke, = ke turant baad).

## A5. Pehla Test (2 min)

```bash
python agent.py
```

Dikhna chahiye:
```
🤖 CryptoBhai chal raha hai!
```

Ab dusre phone/Telegram web se apne bot ko `/start` bhejo — reply aayega! 🎉

## A6. 24/7 Mode Lock Karo (5 min) — SABSE IMPORTANT

Bot ko raat bhar jinda rakhne ke liye:

1. **Wake lock lagao** (screen off hone pe bhi chale):
   ```bash
   termux-wake-lock
   ```
   (Notification me "Acquire wakelock" aayega)

2. **Battery optimization band karo**:
   - Phone Settings → Apps → Termux → Battery → **Unrestricted** (ya "Don't optimize")

3. **Phone ko charger se laga do** 🔌 + WiFi pe chhod do

4. **Android 12+ ho to ye extra karo** (phantom process killer fix):
   - Laptop pe ADB se ek command chalani hoti hai — bina iske Termux
     kuch ghante baad mar jata hai Android 12/13 me:
   ```
   Laptop pe: adb shell "settings put global settings_enable_monitor_phantom_procs false"
   ```
   (ADB ke liye: phone me Developer Options → USB Debugging ON karo,
   laptop se USB lagao, ye command chalao — ek baar ka kaam hai)

5. **Auto-restart setup (optional but best)**:
   - F-Droid se **Termux:Boot** app install karo
   - Termux me: `pkg install termux-services -y`
   - Phone restart pe bot khud chalu ho jayega

## A7. Roz Ka Routine

- Bot band ho jaye to: Termux kholo → `cd ~/crypto-agent && python agent.py`
- Notifications na aaye to: wake-lock re-check karo, phone WiFi pe hai ya nahi

✅ **Bas! Ab laptop band karo — phone pe bot 24/7 signals bhejta rahega.**

---

# ☁️ TARIKA B: Oracle Cloud FREE VPS — Full Steps

Server aisa computer hai jo kabhi band nahi hota. Oracle ka Free Tier
**hamesha ke liye free** hai (trial nahi — expire nahi hota).

## B1. Account Banao (10 min)

1. Laptop browser me: **https://www.oracle.com/cloud/free/**
2. **Start for free** dabao
3. Form bharo: naam, email, phone
4. **Card verification**: card se ~₹100 hold hota hai jo **wapas mil jata hai**
   (ye sirf verify karne ke liye hai, koi charge nahi)
   - ⚠️ Sach batau: Indian **debit cards me se kai reject hote hain**.
     Credit card best chalta hai. Debit se fail ho jaye to Tarika A use karo.
5. Home region: **Mumbai (ap-mumbai-1)** chuno (ya South Korea/Bangalore)
   - ⚠️ Mumbai me free servers aksar "Out of capacity" hote hain — iska
     fix B3 me hai, ghabrana nahi

## B2. Free Server Banao (10 min)

1. Login ke baad search me likho: **Compute → Instances** → **Create Instance**
2. Name: `cryptobhai`
3. Image: **Ubuntu 24.04** (default "Canonical Ubuntu" select karo)
4. Shape: **VM.Standard.E2.1.Micro** chuno (ye Always Free hai, 1GB RAM)
   - A1.Flex (ARM, 4GB) bhi free hai par capacity nahi milti — Micro try karo
5. SSH keys: **"Generate a key pair"** → **"Save Private Key"** download karo
   (`.key` file — sambhal ke rakhna, ye server ki chabi hai)
6. **Create** dabao → 2 min me server ban jayega
7. Server ka **Public IP address** copy kar lo (details page pe dikhega)

## B3. "Out of Capacity" Aaye To (common problem)

- Alag Availability Domain try karo (instance page pe dropdown)
- Alag shape try karo (E2.1.Micro sabse aasan milta hai)
- Subah 6-8 baje (IST) try karo — tab capacity khuli milti hai
- Last option: Account ko **Pay As You Go me upgrade** karo (card lagta hai,
  par free tier limits me **bill ₹0 hi rehta hai**) — capacity turant mil jati hai

## B4. Server Se Connect Karo (2 min)

Windows me **PowerShell** kholo (Start me type karo) aur:

```powershell
cd $HOME\Downloads
ssh -i .\private.key ubuntu@SERVER_KA_IP
```
(`private.key` = jo key download ki thi, `SERVER_KA_IP` = tumhara IP)

Pehli baar pooche "continue connecting?" → `yes` likho.

Linux prompt khul gaya (`ubuntu@cryptobhai:~$`) = connected! 🎉

## B5. Files Upload Karo (3 min)

Apne laptop pe **NAYI PowerShell window** kholo (ye local me chalega,
dusri wali server me connected hai) aur:

```powershell
cd Downloads
scp -i .\private.key -r .\crypto-agent ubuntu@SERVER_KA_IP:~/
```

(crypto-agent folder jahan hai wahi se chalao — `cd` se pehle)

## B6. Deploy — Ek Command (5 min)

Wapas **server wali** PowerShell me:

```bash
cd ~/crypto-agent
bash deploy_vps.sh
```

Token poochhe to paste kar do. End me dikhega:

```
🎉 DEPLOY SUCCESS! Bot ab 24/7 chal raha hai
```

✅ **Bas! Ab laptop band karo, PowerShell close karo — server pe bot
24/7 chalega. Server restart pe bhi khud chalu hoga.**

## B7. Aage Kabhi Check Karna Ho To

Server me SSH karke (B4 wala command):

```bash
systemctl status cryptobhai    # "active (running)" dikhna chahiye
journalctl -u cryptobhai -f    # live logs (Ctrl+C se band)
```

Token galat daala ho to:
```bash
nano /opt/cryptobhai/.env      # token theek karo
systemctl restart cryptobhai
```

---

# 🆘 Common Problems

| Problem | Fix |
|---|---|
| Bot "Conflict" error de | Bot 2 jagah chal raha hai — ek band karo |
| Termux raat me band ho jata | wake-lock + battery Unrestricted + Android 12 ADB fix |
| Oracle card reject | Tarika A use karo (phone) |
| Oracle capacity nahi milti | B3 padho — time/shape change karo |
| Signals nahi aa rahe | `/autoscan` bhejo bot ko (ON karo), channel admin check karo |
| VPS pe bot silent | `systemctl status cryptobhai` — token .env me sahi hai? |

---

# ✅ Setup Ke Baad Checklist

1. Bot ko `/start` → menu aaye
2. `/weekly` → analysis + charts aaye
3. `/futures` → LONG/SHORT setups aaye
4. `/autoscan` → 24/7 scanner ON ho
5. Channel me bot **admin** ho (Post Messages + Invite Users)
6. `/testchannel` → channel pe test post aaye
7. `/invite 3` → paid members ke links banane layak

Sab tick? Tumhari signal service live hai — ab sirf promote karna baaki hai 😎
