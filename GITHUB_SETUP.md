# 🤖 GitHub Actions Setup — Bina Laptop, Bina Phone, Bina Card (FREE 24/7)

Ye sabse smart tarika hai: **GitHub** (duniya ka sabse bada coding website)
apne server pe **FREE me** tumhara bot har ghante chalayega. Tumhe bas ek
baar setup karna hai, phir:
- ⚡ Har ghante market scan → setup mile to **channel pe auto signal**
- ☀️ Roz subah **daily update** channel pe
- 📅 Har Somvaar **weekly report** + naye spot signals (charts ke saath)
- 🎯 Target hit / SL hit ki **auto updates**
- 💻 Tumhara laptop/phone **KABHI BHI ON zaroori nahi**

⚠️ **Ek hi cheez ka dhyan**: Is mode me `/weekly`, `/daily` jaise commands
kaam NAHI karte (ye sirf auto-posting wala mode hai). Sab kuch khud aata
rahega. Kabhi manual analysis chahiye to laptop pe `start_windows.bat` chala
ke kar lena — dono ek saath chal sakte hain, koi jhagda nahi.

---

## Step 1: GitHub Account Banao (3 min)

1. Browser me kholo: **https://github.com/signup**
2. Email daalo, password do, username do (koi bhi, jaise `rahul-trader`)
3. Email pe aayegi verification code daal do

## Step 2: Naya Repository Banao (2 min)

1. Login ke baad upar right side **+** icon → **New repository**
2. Repository name: `cryptobhai`
3. **Public** select karo (important — isse unlimited free minutes milte hain)
4. **Create repository** dabao

## Step 3: Bot Ki Files Upload Karo (5 min)

1. Khali repository page pe likha dikhega **"uploading an existing file"** —
   us link pe click karo
2. Apne laptop me **`crypto-agent` folder ke ANDAR** jao
   (folder khola — ab andar ki cheezein dikhein: agent.py, bot.py, data,
   .github, etc.)
3. **Sab kuch select karo** (Ctrl+A) aur **drag karke** browser ke upload
   box me chhod do
4. ⚠️ **SIRF `.env` FILE KO HATA DENA** (agar hai to) — usme tumhara secret
   token hai! Right-click → Delete kar do upload list me se.
5. Neeche **Commit changes** dabao → upload hone do (1-2 min)

Upload hone ke baad repository me saari files dikhni chahiye
(agent.py, bot.py, .github folder, data folder, etc.)

## Step 4: Secrets Daalo (3 min) — bot ka token aur channel

1. Repository page pe upar **Settings** tab
2. Left side me: **Secrets and variables** → **Actions**
3. **New repository secret** button:

   **Secret 1:**
   - Name: `TELEGRAM_TOKEN`
   - Secret: tumhara BotFather wala token paste karo → Add secret

   **Secret 2:**
   - Name: `CHANNEL_ID`
   - Secret: channel ka address:
     - Channel **public** hai (jaise @corporatetradervip) → bas
       `@corporatetradervip` likho
     - Channel **private** hai → laptop pe ek baar bot chala ke channel
       connect karo, fir `crypto-agent/data/state.json` file Notepad me
       kholo — usme `"channel_id": -100xxxxxxxxxx` likha hoga, wo number
       copy karo

   **Secret 3 (optional):**
   - Name: `CHAT_ID`
   - Secret: apni personal Telegram chat ka ID (daily update personally
     bhi chahiye to). Laptop bot ke `data/chats.json` me tumhara chat id
     milega. Nahi chahiye to skip karo.

## Step 5: Pehli Baar Chalao (1 min)

1. Repository me upar **Actions** tab kholo
2. (Agar bole "I understand my workflows, go ahead" → us button dabao)
3. Left side me **CryptoBhai Auto Scanner** pe click karo
4. Right side: **Run workflow** button → **Run workflow** dabao
5. 1-2 min me run complete hoga → tumhare **channel pe daily update aa
   jayega!** 🎉

## Step 6: Bas Ho Gaya! ✅

Ab GitHub **har ghante khud** run karega:
- Naya trade setup mila → channel pe signal + chart
- Target hit → "🎯 TARGET 1 HIT" update
- Roz 9 IST daily update, Somvaar ko weekly report

Laptop band karo, phone chhod do — sab chalta rahega. 🚀

---

## Aage Kabhi Check Karna Ho

- **Bot chal raha hai?** → Repository → Actions tab → hari tick ✅ dikhni chahiye
- **Kuch fail ho raha?** → Actions me red ❌ → click karke logs dekho
- **Haath se turant chalana ho?** → Actions → CryptoBhai Auto Scanner → Run workflow

## Free Limits Ka Sach (tension mat lo)

- **Public repo = UNLIMITED free minutes** (isliye Public banaya)
- Private repo hota to 2000 min/month — hourly run me ~1000 min lagta,
  wo bhi chal jata, par Public best hai
- GitHub scheduled runs kabhi-kabhi 5-15 min late ho sakte hain — normal hai

## Common Problems

| Problem | Fix |
|---|---|
| Actions tab me workflow nahi dikh raha | `.github/workflows/bot.yml` upload hui thi? Folder ke saath? |
| Run fail — TELEGRAM_TOKEN missing | Step 4 me secret naam bilkul same hona chahiye |
| Channel pe post nahi aa raha | CHANNEL_ID secret sahi? Bot channel me admin hai? |
| Commands (/weekly) reply nahi kar rahe | Ye normal hai — GitHub mode me commands off hote hain |
| WinINET/proxy error logs me | Ek baar fir "Run workflow" dabao, network hiccup hota hai |
