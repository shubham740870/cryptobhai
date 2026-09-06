# 🤖 CryptoBhai — Tumhara Personal Crypto Analysis Agent + Signal Channel

Ye agent **pure crypto market ko khud analyze karta hai** aur Telegram pe deta hai:

- 📅 **Weekly report** — kis coin ko kharidna hai, kis price pe kharido (entry zone),
  kaha profit book karo (Target 1/2), kaha exit karo (stop-loss)
- 🖼 **Har recommendation ka CHART IMAGE** — entry/target/SL price chart pe visualized
- 📊 **Signal Performance Tracker** — har purane call ka live P&L, "T1 HIT ✅",
  "TARGET 2 HIT 🎯 +27%" type result updates + win rate
- ☀️ **Daily update** — kaun sa coin achha chal raha hai, kahan profit book karna hai
- ⚡ **FUTURES signals** — LONG/SHORT setups + leverage + liquidation price + funding rate
- 🤖 **24/7 Auto-Scanner** — har ghante market scan; setup milte hi khud channel pe signal
- 📺 **Telegram Channel auto-posting** — saare trades apne channel pe automatically
- 🔗 **Paid community tools** — one-time invite links (leak-proof member access)
- 🔬 **Kisi bhi coin ka deep analysis** + 📦 **Portfolio P&L chart**

Data source: **CoinGecko free API** (real-time, 250+ coins) + Fear & Greed Index.
Sab analysis tumhare computer/phone pe hota hai — koi paid service nahi.

---

## 🚀 Setup (sirf 5 minute)

### Step 1: Telegram bot banao (2 min)

1. Telegram me jao → **@BotFather** search karo → `/start`
2. `/newbot` type karo
3. Bot ka naam do (jaise: `CryptoBhai Market Bot`)
4. Username do (jaise: `crypto_bhai_analysis_bot` — `bot` se end hona chahiye)
5. BotFather ek **token** dega, aisa dikhega:
   ```
   7284915620:AAHf3kQ8xNv2mP9zX4bY7wL1cE5rT6uU8iO
   ```
6. **Is token ko kisi se share mat karo!**

### Step 2: Token set karo

```bash
# crypto-agent folder me .env file banao:
cp .env.example .env

# .env kholo aur apna token daalo:
TELEGRAM_TOKEN=7284915620:AAHf3kQ8xNv2mP9zX4bY7wL1cE5rT6uU8iO
```

### Step 3: Install + Run

```bash
pip install -r requirements.txt   # requests + matplotlib
python agent.py
```

Bas! 🎉 Ab Telegram me apne bot ko jao → `/start` bhejo → phir `/weekly` bhejo.
**~1-2 minute me pura market analysis + charts aa jayega.**

---

## 💬 Bot Commands

| Command | Kya karta hai |
|---|---|
| `/weekly` | 📅 Top BUY picks + **chart images** + SELL alerts |
| `/daily` | ☀️ Movers, alerts, market mood + **open signals ka live P&L** |
| `/analyze sol` | 🔬 Deep analysis + trade plan chart |
| `/futures` | ⚡ LONG/SHORT futures setups (leverage, liq price, funding) |
| `/autoscan` | 🤖 24/7 auto-scanner on/off |
| `/performance` | 📊 Saare signals ka track record: win rate + open P&L |
| `/trending` | 🔥 Abhi kya trend me hai |
| `/portfolio` | 📦 Holdings ka **P&L bar chart** + advice |
| `/add BTC 0.05 65000` | ➕ Holding add karo (coin, qty, buy price) |
| `/remove BTC` | ➖ Holding hatao |
| `/watch SOL` / `/unwatch SOL` | 👁🙈 Tracking on/off |
| `/risk aggressive` | 🎚 Mode: `safe` / `balanced` / `aggressive` |
| `/time 9` | ⏰ Daily update ka time badlo (IST) |
| `/help` | 📖 Sab commands |

### 📺 Channel commands (paid community ke liye)

| Command | Kya karta hai |
|---|---|
| `/setchannel` | 📺 Channel connect karo (bot ko admin banao — auto-detect) |
| `/testchannel` | 🧪 Channel pe test post |
| `/invite 5` | 🔗 5 one-time join links (har link ek baar use ho sakta hai) |

**Paid community kaise chalao (step-by-step):**

1. Telegram channel banao (jaise "CryptoBhai VIP Signals")
2. Channel settings → Administrators → **Add Admin** → apna bot select karo
   → permissions: **Post Messages** + **Invite Users via Link**
3. Bot khud detect kar lega: "✅ Channel connect ho gaya!" 🎉
4. Ab automatically channel pe jayega:
   - Har naya signal (chart + entry/target/SL ke saath)
   - 🎯 Target Hit updates + 🛑 Stop-loss alerts (live P&L ke saath)
   - Daily market update + weekly overview
5. Members se charge karo — UPI / Razorpay / Gumroad / jo bhi chale
6. Payment milne pe: bot chat me `/invite 1` → jo link aaye wo member ko bhejo.
   **Link one-time hai** — join karte hi dead, koi forward leak nahi hoga 🔒

### Signal lifecycle (fully automatic)

```
🚀 NEW SIGNAL (chart ke saath)
   → 🎯 TARGET 1 HIT!  "SL entry pe shift karo — risk-free trade"
   → 🚀 TARGET 2 HIT (+27%)  YA  🛑 STOP-LOSS (-8%)
```

Har signal `signals.json` me track hota hai → `/performance` me sab ka record:
win rate, open positions ka live P&L, closed results.
**Ye transparency paid community ka sabse bada trust factor hai.** 💪

---

## ⏰ Automatic Updates

Bot chalte rahe to khud bhejta hai (tumhari personal chat + channel dono pe):

- ☀️ **Daily update**: roz subah **9:00 IST** (`/time 9` se badal sakte ho)
  + open signals ka P&L check → target/SL hit notifications
- 📅 **Weekly report**: har **Somvaar 9:00 IST** + naye signal charts

---

## 🖥 24/7 Chalane Ke Options (LAPTOP BAND HO TAB BHI)

### Option 0: GitHub Actions (FREE + BINA CARD + BINA PHONE — sabse aasan)

GitHub ke free server pe bot har ghante chalega. Na laptop chahiye,
na phone, na credit card — sirf email se account. Setup sirf 15 min,
pura step-by-step: **GITHUB_SETUP.md** padho.

- ✅ Auto signals har ghante channel pe (24/7)
- ✅ Daily + weekly posts automatic
- ⚠️ Commands (/weekly etc.) is mode me off — sab khud aata hai

### Option 1: VPS (RECOMMENDED — paid community ke liye)

Cloud server pe bot daal do — wahan ye Windows **service** ban jata hai.
Tumhara laptop BAND, bot phir bhi 24/7 chalta rahega.

**Kaise (10 min):**
1. VPS lo: Hostinger/DigitalOcean/AWS Lightsail (~₹150-300/mahina)
   ya **Oracle Cloud Free Tier** (hamesha ke liye FREE VPS — 2 chhoti servers)
2. SSH se login karo (Termius app / Windows PowerShell: `ssh root@IP`)
3. crypto-agent folder ko upload karo (`scp -r crypto-agent root@IP:/root/`)
4. VPS pe: `cd /root/crypto-agent && bash deploy_vps.sh`
5. Token paste karo — DONE! 🎉

Bot ab systemd service hai: crash ho to khud restart, server reboot pe
bhi khud start. Koi window nahi, kuch nahi dekhna padta.

```bash
systemctl status cryptobhai    # bot chal raha hai?
journalctl -u cryptobhai -f    # live logs dekho
```

### Option 2: Purana Android phone (FREE)

**Termux** (F-Droid wala) me:
```bash
pkg install python
cd crypto-agent && bash start_termux.sh
termux-wake-lock   # screen off hone pe bhi chale
```
Phone charger se laga do, WiFi pe — 24/7 free bot!

### Option 3: Apna laptop (sirf testing ke liye)
`start_windows.bat` double-click — par window band = bot band.

---

## 🧪 Bina Telegram ke test karo

```bash
python agent.py --selftest          # quick check
python agent.py --demo weekly       # weekly report + charts + signal recording
python agent.py --demo daily        # daily update + signal P&L check
python agent.py --demo analyze sol  # ek coin ka analysis + chart
```

Reports `data/reports/` me, charts `data/reports/charts/` me save hoti hain.

---

## 🧠 Engine Kaise Kaam Karta Hai

**Stage 1 — Market scan (1 API call):** Top 250 coins filter hote hain
(stablecoins, wrapped tokens, low-liquidity coins hata diye jaate hain),
fir har coin ka momentum/7d-trend/volume score banta hai.

**Stage 2 — Deep analysis (top candidates):** Har shortlisted coin ke liye
90 din ka price data → daily candles banake compute hota hai:

- **RSI (14)** — overbought/oversold momentum
- **MACD (12,26,9)** — trend direction
- **SMA 20/50** — trend support
- **ATR (14)** — volatility (stop-loss isi se set hota hai)
- **Bollinger Bands** — entry quality
- Volume trend + CoinGecko trending bonus

**Score (0-100) = Trend(28) + Momentum(22) + Entry quality(20) + Risk(18) + Volume(12)**

- 🚀 Score 68+ → STRONG BUY (aggressive mode me)
- ✅ 55+ → BUY
- ⏳ 45+ → HOLD/WATCH
- 💰 Overbought (RSI>78) ya parabolic pump → **PROFIT BOOKING ZONE**
- 📉 Weak → SELL/AVOID

**Levels:**
- Entry zone = current price / SMA20 pullback area
- Target 1 = 1.5R, Target 2 = 2.5R (ATR-based, realistic moves)
- Stop-loss = 1.8×ATR neeche (min 5%, max 13%)

**Safety guards:**
- Parabolic pump (>90% weekly) wale coins BUY me nahi aate — FOMO protection
- RSI 78+ coins BUY list me nahi aate
- Low liquidity (<$1.5M volume) coins filter out

---

## ⚡ Futures Signals (LONG/SHORT)

Futures engine sirf **LIQUID coins** (mcap $50M+, volume $5M+) pe signal deta hai
— manipulation-safe:

- 🟢 **LONG setup**: uptrend + MACD bullish + RSI < 74 (overbought nahi)
- 🔴 **SHORT setup**: price < SMA50, SMA20 < SMA50, MACD bearish, 7d -6% ya zyada girawat
- ⚡ **Leverage**: volatility se calculate hota hai (max 5x cap, isolated margin)
- 💥 **Liquidation price** har signal me dikhata hai
- 💵 **Funding rate** (OKX se) — crowded side ki warning
- 🎖 **Confidence**: HIGH/MEDIUM

**Auto-Scanner (24/7):** har ghante market scan hota hai. Koi coin 1h me ±2.5%
ya 24h me ±8% move kare → turant deep analysis → setup valid ho to channel pe
signal + chart + funding — sab automatic, bina kisi command ke!

⚠️ **Futures discipline (members ko bhi sikhao):**
- Max 5x leverage, isolated margin, hamesha SL ke saath
- Ek trade me capital ka 2-5% se zyada risk mat lo
- Liquidation price ka dhyan rakho — leverage = double-edged sword

---

## ⚠️ Disclaimer

Ye tool **sirf educational analysis** ke liye hai — **financial advice nahi**.
Crypto market bahut volatile hai. Apna research karo (DYOR), sirf utna invest
karo jitna afford kar sakte ho. Bot ke suggestions guarantee nahi hain.

Paid community chalate waqt members ko clearly batao ki ye algorithmic
educational signals hain, guaranteed returns nahi. India me crypto pe 30% tax
+ 1% TDS lagta hai — apne members ko bhi ye remind karte raho.
