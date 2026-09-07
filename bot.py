"""Telegram bot — commands, chart images, channel auto-posting, signal tracking."""
import html
import logging
import threading
import time

import requests

import analyzer
import charts
import config
import reports
import signals as signals_mod
import storage

log = logging.getLogger("bot")

API = "https://api.telegram.org/bot{token}/{method}"

HELP_TEXT = (
    "🤖 <b>CryptoBhai — tumhara personal market analyst</b>\n\n"
    "<b>MAIN COMMANDS</b>\n"
    "📅 /weekly — Top buy/sell picks + chart images (entry, target, SL)\n"
    "☀️ /daily — Aaj ka update: movers, alerts, market mood\n"
    "🔬 /analyze sol — Kisi bhi coin ka deep analysis + chart\n"
    "⚡ /futures — LONG/SHORT futures setups (leverage + liquidation)\n"
    "👑 /majors — BTC/ETH/SOL ka futures scan\n"
    "🎓 /pro btc — Professional desk analysis (structure/MTF/S-R/position size)\n"
    "🥇🥈 /gold — GOLD + SILVER (XAU/XAG) live signals 🔥\n"
    "🎬 /content — last winning trade ka video + caption (IG/YT)\n"
    "📒 /journal — Google Sheet trading journal ka live P&L\n"
    "🔥 /trending — Abhi kya trend me hai\n"
    "📊 /performance — Saare past signals ka P&L + win rate\n"
    "🤖 /autoscan — 24/7 auto-scanner on/off (har ghante naye setups)\n\n"
    "<b>PORTFOLIO</b>\n"
    "📦 /portfolio — Holdings ka live P&L chart + advice\n"
    "➕ /add BTC 0.05 65000 — holding add karo\n"
    "➖ /remove BTC — holding hatao\n"
    "👁 /watch SOL | 🙈 /unwatch SOL — tracking\n\n"
    "<b>CHANNEL (paid community ke liye)</b>\n"
    "📺 /setchannel — channel connect karo (bot ko admin banao, fir channel ka koi post bot ko forward karo)\n"
    "🧪 /testchannel — channel pe test post\n"
    "🔗 /invite 5 — paid members ke liye 5 one-time join links\n\n"
    "<b>SETTINGS</b>\n"
    "🎚 /risk aggressive — safe / balanced / aggressive\n"
    "⏰ /time 9 — daily update ka time (IST)\n\n"
    "⚠️ <i>Educational analysis only — financial advice nahi. DYOR.</i>"
)

MODE_TEXT = {
    "safe": "🛡 <b>Safe mode</b> — sirf bade blue-chip coins, kam risk",
    "balanced": "⚖️ <b>Balanced mode</b> — top 100 coins me best picks",
    "aggressive": "🔥 <b>Aggressive mode</b> — top 250 + trending small caps, high risk-reward",
}


class CryptoBot:
    def __init__(self, token):
        self.token = token
        self._offset = 0
        self._analysis_cache = {}
        self._analysis_lock = threading.Lock()
        self._weekly_running = False

    # ---------------- Telegram API ----------------
    def _api(self, method, data=None, files=None, timeout=40):
        try:
            r = requests.post(API.format(token=self.token, method=method),
                              data=data or {}, files=files, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            # error ka detail log karo (pehle silent fail ho raha tha)
            try:
                desc = r.json().get("description", r.text[:120])
            except ValueError:
                desc = r.text[:120]
            log.warning("TG %s -> %s: %s", method, r.status_code, desc)
            return None
        except requests.RequestException as e:
            log.warning("TG %s error: %s", method, e)
            return None

    def send(self, chat_id, text):
        """HTML text bhejo (auto-chunk + parse-fallback). Returns True/False."""
        ok_all = True
        for i in range(0, len(text), 3900):
            part = text[i:i + 3900]
            sent = False
            for attempt in range(3):
                resp = self._api("sendMessage", data={
                    "chat_id": chat_id, "text": part, "parse_mode": "HTML",
                    "disable_web_page_preview": True})
                if resp and resp.get("ok"):
                    sent = True
                    break
                if resp and not resp.get("ok"):
                    desc = resp.get("description", "")
                    log.warning("sendMessage fail: %s", desc)
                    if "parse" in desc.lower():
                        r2 = self._api("sendMessage", data={"chat_id": chat_id,
                                       "text": part.replace("<", "")[:3900]})
                        sent = bool(r2 and r2.get("ok"))
                        break
                    if resp.get("error_code") == 429:
                        time.sleep(3)
                        continue
                    break
                time.sleep(2)
            if not sent:
                ok_all = False
                log.warning("sendMessage FAIL (chat_id=%s)", chat_id)
        return ok_all

    def send_photo(self, chat_id, path, caption=""):
        """Chart image bhejo; fail hone pe caption text me chala jayega."""
        try:
            with open(path, "rb") as f:
                resp = self._api("sendPhoto", data={
                    "chat_id": chat_id, "caption": caption[:1024],
                    "parse_mode": "HTML"}, files={"photo": f})
        except (FileNotFoundError, OSError):
            resp = None
        if not (resp and resp.get("ok")):
            log.warning("sendPhoto fail (%s), caption text me bhej raha hoon", path)
            if caption:
                return self.send(chat_id, caption)
            return False
        return True

    def send_video(self, chat_id, path, caption=""):
        """MP4 video bhejo (reel format); fail hone pe caption text me."""
        try:
            with open(path, "rb") as f:
                resp = self._api("sendVideo", data={
                    "chat_id": chat_id, "caption": caption[:1024],
                    "parse_mode": "HTML", "supports_streaming": True},
                    files={"video": f})
        except (FileNotFoundError, OSError):
            resp = None
        if not (resp and resp.get("ok")):
            log.warning("sendVideo fail (%s)", path)
            if caption:
                return self.send(chat_id, caption)
            return False
        return True

    def broadcast(self, text):
        for chat_id in storage.all_chat_ids():
            self.send(chat_id, text)
            time.sleep(0.6)

    # ---------------- Channel ----------------
    def channel_id(self):
        return storage.get_state().get("channel_id") or config.CHANNEL_ID or ""

    def is_admin(self, chat_id):
        admins = storage.get_state().get("admins", [])
        if str(chat_id) in admins or str(chat_id) in config.ADMIN_IDS:
            return True
        # pehla user jo channel set kare, wahi owner ban jayega
        return not admins and not config.ADMIN_IDS

    def _add_admin(self, chat_id):
        state = storage.get_state()
        admins = state.get("admins", [])
        if str(chat_id) not in admins:
            admins.append(str(chat_id))
            state["admins"] = admins
            storage.save_json("state.json", state)

    def set_channel(self, chat_id, cid, title=""):
        storage.set_state("channel_id", cid)
        self._add_admin(chat_id)
        log.info("Channel set: %s (%s)", cid, title)

    def post_channel(self, text, photo=None):
        """Connected channel pe post karo. Secret ID fail ho to known-good
        fallback ID try karta hai (delivery guarantee)."""
        cid = self.channel_id() or config.FALLBACK_CHANNEL
        if photo:
            ok = self.send_photo(cid, photo, caption=text)
        else:
            ok = self.send(cid, text)
        if not ok and cid != config.FALLBACK_CHANNEL:
            log.warning("channel post fail via %s — fallback try", cid)
            if photo:
                ok = self.send_photo(config.FALLBACK_CHANNEL, photo, caption=text)
            else:
                ok = self.send(config.FALLBACK_CHANNEL, text)
        log.info("CHANNEL POST %s (id=%s)", "OK" if ok else "FAIL", cid)
        return ok

    def post_channel_video(self, path, caption=""):
        cid = self.channel_id() or config.FALLBACK_CHANNEL
        ok = self.send_video(cid, path, caption)
        if not ok and cid != config.FALLBACK_CHANNEL:
            ok = self.send_video(config.FALLBACK_CHANNEL, path, caption)
        log.info("CHANNEL VIDEO %s", "OK" if ok else "FAIL")
        return ok

    def _notify_owner(self, text, video_path=None):
        """Admin/user chats ko video+text bhejo. CHAT_ID fail ho to
        hardcoded fallback chat guarantee."""
        targets = set(storage.get_state().get("admins", [])) | set(config.ADMIN_IDS)
        if config.CHAT_ID:
            targets.add(str(config.CHAT_ID))
        sent = False
        for t in targets:
            if video_path:
                sent = self.send_video(t, video_path, text) or sent
            else:
                sent = self.send(t, text) or sent
        if not sent and config.FALLBACK_CHAT:
            log.warning("owner chats sab FAIL — fallback chat (%s)",
                        config.FALLBACK_CHAT)
            if video_path:
                self.send_video(config.FALLBACK_CHAT, video_path, text)
            else:
                self.send(config.FALLBACK_CHAT, text)

    def test_channel(self, chat_id):
        if not self.channel_id():
            self.send(chat_id, "❌ Pehle channel connect karo: /setchannel")
            return
        ok = self.post_channel("✅ <b>CryptoBhai connected!</b>\n"
                               "Is channel pe ab saare trade signals, charts aur "
                               "updates auto-post honge. 🚀")
        self.send(chat_id, "✅ Test post channel pe bhej diya! Check karo."
                  if ok else "❌ Post fail — bot ko channel me <b>admin</b> "
                             "banao (post messages permission ke saath)")

    def create_invites(self, count):
        """Paid members ke liye one-time join links (member_limit=1)."""
        cid = self.channel_id()
        if not cid:
            return []
        links = []
        for _ in range(min(count, 10)):
            r = self._api("createChatInviteLink", data={
                "chat_id": cid, "member_limit": 1})
            if r and r.get("ok"):
                links.append(r["result"]["invite_link"])
            time.sleep(0.3)
        return links

    # ---------------- Publishing (charts + signals) ----------------
    def publish_trade_cards(self, buys, also_chat=None):
        """Har BUY pick ka chart + caption — chat me bhejo + channel pe post karo."""
        posted_any = False
        for a in buys[:4]:
            hist = analyzer.fetch_history(a["id"])
            if not hist:
                continue
            path = charts.trade_chart(a, hist)
            cap = reports.trade_caption(a)
            if also_chat:
                self.send_photo(also_chat, path, cap)
            if self.post_channel(cap, photo=path):
                posted_any = True
            time.sleep(0.5)
        return posted_any

    def publish_signal_updates(self, updates):
        """T1 hit / closed signals ka result post (chart ke saath)."""
        for u in updates:
            s = u["sig"]
            hist = analyzer.fetch_history(s["id"])
            path = None
            try:
                if hist:
                    path = charts.result_chart(s, hist)
            except Exception:
                log.exception("result_chart fail: %s", s["sym"])
            text = reports.signal_result_text(s, u["event"], u["pnl_pct"])
            self.post_channel(text, photo=path)
            for admin in storage.get_state().get("admins", []):
                self.send(admin, text)
            time.sleep(0.5)

            # ---- WIN (Target 2) -> AI result video ----
            if u["event"] == "CLOSED_TP2":
                try:
                    import video as video_mod
                    vid, cap = video_mod.make_result_video(s)
                    if vid:
                        self.post_channel_video(vid, "🎬 " + cap)
                        self._notify_owner(
                            "🎬 <b>NAYA CONTENT READY!</b>\n"
                            "Ye video Instagram Reels / YouTube Shorts pe post "
                            "kar do (caption niche).\n\n"
                            "📝 <b>Caption:</b>\n" + cap,
                            video_path=vid)
                        log.info("Result video ready: %s", vid)
                    else:
                        self._notify_owner(text)
                except Exception:
                    log.exception("video generation fail")
                    self._notify_owner(text)

    # ---------------- Analysis runners ----------------
    def get_weekly(self, mode, chat_id):
        with self._analysis_lock:
            cached = self._analysis_cache.get(mode)
            if cached and time.time() - cached["t"] < 6 * 3600:
                return cached["res"], True
            if self._weekly_running:
                return None, False
            self._weekly_running = True
        try:
            res = analyzer.run_weekly(
                mode, progress_cb=lambda m: self.send(chat_id, m))
            with self._analysis_lock:
                self._analysis_cache[mode] = {"t": time.time(), "res": res}
        finally:
            with self._analysis_lock:
                self._weekly_running = False
        return res, True

    # ---------------- Update routing ----------------
    def handle(self, update):
        # channel me bot ko admin banaya gaya -> auto-register
        mcm = update.get("my_chat_member")
        if mcm and (mcm.get("chat") or {}).get("type") == "channel":
            new = (mcm.get("new_chat_member") or {}).get("status", "")
            old = (mcm.get("old_chat_member") or {}).get("status", "")
            if new == "administrator" and old != "administrator":
                chat = mcm["chat"]
                self.set_channel(mcm["from"]["id"], chat["id"],
                                 chat.get("title", ""))
                self.send(mcm["from"]["id"],
                          f"✅ Channel <b>{html.escape(chat.get('title',''))}</b> "
                          "connect ho gaya! Ab saare signals auto-post honge.\n"
                          "🧪 /testchannel se check karo")
            return
        msg = update.get("message") or update.get("edited_message")
        if not msg:
            return
        chat_id = msg["chat"]["id"]

        # channel post forward karke register karne ka tarika
        fwd = msg.get("forward_from_chat")
        if fwd and fwd.get("type") == "channel":
            self.set_channel(chat_id, fwd["id"], fwd.get("title", ""))
            self.send(chat_id, f"✅ Channel <b>{html.escape(fwd.get('title',''))}</b> "
                               "connect ho gaya! Ab saare trade signals auto-post honge.\n"
                               "🧪 /testchannel se verify karo\n"
                               "🔗 Paid members ke liye: /invite 5")
            return

        text = (msg.get("text") or "").strip()
        if not text.startswith("/"):
            return
        parts = text.split()
        cmd = parts[0].split("@")[0][1:].lower()
        args = parts[1:]
        if cmd == "start":
            storage.register_chat(chat_id, {"username":
                (msg["chat"].get("username") or msg["chat"].get("first_name") or "")})
        try:
            self._dispatch(chat_id, cmd, args)
        except Exception:
            log.exception("command /%s failed", cmd)
            self.send(chat_id, "😕 Oops, kuch technical problem aayi. Thodi der baad try karo.")

    def _mode(self, chat_id):
        return storage.get_mode(chat_id) or config.DEFAULT_MODE

    def _dispatch(self, chat_id, cmd, args):
        if cmd in ("start", "help", "menu"):
            self.send(chat_id, HELP_TEXT)
        elif cmd == "weekly":
            self.cmd_weekly(chat_id)
        elif cmd == "daily":
            self.cmd_daily(chat_id)
        elif cmd == "analyze":
            self.cmd_analyze(chat_id, args)
        elif cmd == "futures":
            self.cmd_futures(chat_id)
        elif cmd == "majors":
            self.cmd_majors(chat_id)
        elif cmd == "pro":
            self.cmd_pro(chat_id, args)
        elif cmd == "content":
            self.cmd_content(chat_id)
        elif cmd == "journal":
            self.cmd_journal(chat_id)
        elif cmd in ("gold", "silver", "metals"):
            self.cmd_gold(chat_id)
        elif cmd == "autoscan":
            self.cmd_autoscan(chat_id)
        elif cmd == "trending":
            self.cmd_trending(chat_id)
        elif cmd == "portfolio":
            self.cmd_portfolio(chat_id)
        elif cmd == "add":
            self.cmd_add(chat_id, args)
        elif cmd == "remove":
            self.cmd_remove(chat_id, args)
        elif cmd == "watch":
            self.cmd_watch(chat_id, args)
        elif cmd == "unwatch":
            self.cmd_unwatch(chat_id, args)
        elif cmd == "risk":
            self.cmd_risk(chat_id, args)
        elif cmd == "time":
            self.cmd_time(chat_id, args)
        elif cmd == "setchannel":
            self.cmd_setchannel(chat_id, args)
        elif cmd == "testchannel":
            self.test_channel(chat_id)
        elif cmd == "invite":
            self.cmd_invite(chat_id, args)
        elif cmd in ("performance", "perf", "stats"):
            self.cmd_performance(chat_id)
        else:
            self.send(chat_id, "Ye command samajh nahi aaya. /help likho 🙏")

    # ---------------- Commands ----------------
    def cmd_weekly(self, chat_id):
        mode = self._mode(chat_id)
        res, ready = self.get_weekly(mode, chat_id)
        if not ready:
            self.send(chat_id, "⏳ Weekly analysis pehle se chal raha hai — result 1-2 min me aa raha hai...")
            return
        for chunk in reports.weekly_report(res):
            self.send(chat_id, chunk)
        new_sigs, _ = signals_mod.record_signals(res)
        self.send(chat_id, "📈 <b>Buy picks ke charts</b> bana raha hoon...")
        new_syms = {s["sym"] for s in new_sigs}
        cards = [a for a in res.get("buys", []) if a["symbol"] in new_syms] or res.get("buys", [])
        self.publish_trade_cards(cards, also_chat=chat_id)
        if new_sigs and self.channel_id():
            self.post_channel(reports.channel_overview(res))

    def cmd_daily(self, chat_id):
        self.send(chat_id, "⏳ Daily update ban raha hai...")
        res = analyzer.run_daily(self._mode(chat_id))
        chunks = reports.daily_report(res)
        for chunk in chunks:
            self.send(chat_id, chunk)
        if self.channel_id():
            self.post_channel("\n".join(chunks[:2])[:3500])
        updates, _ = signals_mod.check_signals(self._mode(chat_id))
        if updates:
            self.publish_signal_updates(updates)

    def cmd_analyze(self, chat_id, args):
        if not args:
            self.send(chat_id, "Coin ka naam batao: <code>/analyze solana</code> ya <code>/analyze SOL</code>")
            return
        sym = args[0]
        self.send(chat_id, f"🔬 <b>{html.escape(sym.upper())}</b> ka analysis chal raha hai...")
        a = analyzer.run_single(sym, self._mode(chat_id))
        if not a:
            self.send(chat_id, f"❌ '{html.escape(sym)}' naam ka coin nahi mila. Symbol try karo jaise <code>BTC</code>, <code>SOL</code>, <code>PEPE</code>")
            return
        for chunk in reports.single_report(a, self._mode(chat_id)):
            self.send(chat_id, chunk)
        hist = analyzer.fetch_history(a["id"])
        if hist:
            path = charts.trade_chart(a, hist)
            self.send_photo(chat_id, path, reports.trade_caption(a))

    # ---------------- Futures ----------------
    def cmd_futures(self, chat_id):
        import futures as futures_mod
        mode = self._mode(chat_id)
        self.send(chat_id, "\u26a1 <b>Futures scan</b> shuru \u2014 liquid coins ka LONG/SHORT analysis...")
        # fresh weekly analysis cached hai to usi se, warna futures scan
        with self._analysis_lock:
            cached = self._analysis_cache.get(mode)
        if cached and time.time() - cached["t"] < 6 * 3600:
            analyzed = cached["res"].get("analyzed") or []
            self.send(chat_id, "\u267b\ufe0f Recent analysis use kar raha hoon (fresh scan /weekly se)")
        else:
            analyzed = analyzer.run_futures(mode, progress_cb=lambda m: self.send(chat_id, m))
        longs, shorts = futures_mod.evaluate_setups(analyzed)
        self.send(chat_id, reports.futures_report(longs, shorts))
        self._publish_futures(longs + shorts, chat_id)

    def _publish_futures(self, setups, also_chat=None, skip_record=False):
        import futures as futures_mod
        if not setups:
            return
        if skip_record:
            new_syms = {(s.get("symbol") or s.get("sym"), s.get("side"))
                        for s in setups}
        else:
            new_sigs, _ = signals_mod.record_setups(
                [dict(s, kind="FUTURES") for s in setups], kind="FUTURES")
            new_syms = {(s.get("symbol") or s.get("sym"), s.get("side"))
                        for s in new_sigs}
        cards = setups[:4]
        if also_chat and not skip_record:
            cards = [a for a in setups
                     if (a.get("symbol") or a.get("sym"),
                         a.get("side")) in new_syms] or cards
        for a in cards:
            hist = analyzer.fetch_history(a["id"])
            if not hist:
                continue
            # futures = TradingView-style candle chart (S/R zones ke saath)
            try:
                path = charts.candle_chart(dict(a, kind="FUTURES"), hist)
            except Exception:
                log.exception("candle_chart fail, line chart pe fallback")
                path = charts.trade_chart(a, hist)
            cap = (reports.trade_caption(dict(a, kind="FUTURES"))
                   + futures_mod.funding_note(a["symbol"]))
            if also_chat:
                self.send_photo(also_chat, path, cap)
            self.post_channel(cap, photo=path)
            time.sleep(0.5)

    def cmd_pro(self, chat_id, args):
        import pro as pro_mod
        if not args:
            self.send(chat_id, "🎓 Coin do: <code>/pro btc</code>")
            return
        sym = args[0]
        self.send(chat_id, f"🎓 <b>{html.escape(sym.upper())}</b> ka PRO DESK "
                           "analysis (structure/MTF/volume/position size)...")
        markets = analyzer.fetch_markets(self._mode(chat_id))
        target = next((c for c in markets if c["symbol"].lower() == sym.lower()
                       or c["id"] == sym.lower()), None)
        if not target:
            self.send(chat_id, f"❌ '{html.escape(sym)}' nahi mila")
            return
        hist = analyzer.fetch_history(target["id"])
        if not hist:
            self.send(chat_id, "❌ history nahi mili")
            return
        a = analyzer.deep_analyze(target, hist, self._mode(chat_id), frozenset())
        a["_ath_dist"] = abs(target.get("ath_change_percentage") or 0)
        self.send(chat_id, pro_mod.professional_report(a, hist))
        path = charts.trade_chart(a, hist)
        self.send_photo(chat_id, path, reports.trade_caption(a))

    def cmd_majors(self, chat_id):
        import futures as futures_mod
        mode = self._mode(chat_id)
        self.send(chat_id, "👑 <b>BTC / ETH / SOL futures scan</b>...")
        setups, analyzed = futures_mod.majors_setups(mode)
        self.send(chat_id, reports.futures_report(
            [s for s in setups if s["side"] == "LONG"],
            [s for s in setups if s["side"] == "SHORT"]))
        if setups:
            new_sigs, _ = signals_mod.record_setups(
                [dict(s, kind="FUTURES") for s in setups], kind="FUTURES")
            if new_sigs:
                pub = [a for a in setups
                       if (a["symbol"], a["side"]) in
                       {(x["sym"], x["side"]) for x in new_sigs}]
                self._publish_futures(pub, also_chat=chat_id, skip_record=True)
            else:
                self.send(chat_id, "ℹ️ Ye setups already open/post ho chuke hain")
        else:
            self.send(chat_id, "📊 BTC/ETH/SOL me abhi koi clean setup nahi — "
                               "scanner har ghante check karta rahega ⏳")

    def cmd_content(self, chat_id):
        """Last winning trade ka video dobara banao (IG/YT content)."""
        import video as video_mod
        sigs = signals_mod.performance_summary()[0]
        wins = [s for s in sigs if s["status"] == "CLOSED_TP2"]
        if not wins:
            self.send(chat_id, "🎬 Abhi tak koi successful trade record nahi hua. "
                               "Jaise hi koi signal Target 2 hit karega, video "
                               "khud ban jayega!")
            return
        s = wins[0]
        self.send(chat_id, f"🎬 <b>{s['sym']}</b> ke winning trade ka video ban "
                           "raha hai (1-2 min)...")
        vid, cap = video_mod.make_result_video(s)
        if vid:
            self.send_video(chat_id, vid, "🎬 <b>CONTENT READY!</b>\n"
                            "Ye video Instagram Reels / YouTube Shorts pe post karo.\n\n"
                            "📝 <b>Caption (copy karo):</b>\n" + cap)
        else:
            self.send(chat_id, "😕 Video generate nahi ho paya (ffmpeg missing). "
                               "GitHub Actions pe ye automatic kaam karega.")

    def cmd_journal(self, chat_id):
        import journal as journal_mod
        if not config.JOURNAL_SHEET_URL:
            self.send(chat_id,
                "📒 <b>TRADING JOURNAL SETUP</b>\n\n"
                "1. Google Sheet banao in columns ke saath:\n"
                "<code>Date | Coin | Side | Entry | SL | Target | Qty | Lev | Notes</code>\n"
                "2. Sheet ko public karo: Share → Anyone with link → Viewer\n"
                "3. Sheet ka link mujhe do (JOURNAL_SHEET_URL)\n\n"
                "Uske baad har update me tumhari entries ka live P&L + "
                "win-rate + target/SL alerts automatic milenge! 📊")
            return
        self.send(chat_id, "📒 Journal sheet padh raha hoon...")
        entries, err = journal_mod.load_entries()
        if err:
            self.send(chat_id, f"❌ {err}")
            return
        markets = analyzer.fetch_markets(self._mode(chat_id))
        self.send(chat_id, journal_mod.journal_report(entries, markets))

    def cmd_gold(self, chat_id):
        """Gold + Silver metals desk (Yahoo hourly data)."""
        try:
            self.send(chat_id, "\U0001f947\U0001f948 <b>Metals Desk</b> \u2014 "
                               "GOLD + SILVER analysis aa raha hai...")
            import metals as metals_mod
            self.send(chat_id, metals_mod.report())
        except Exception:
            log.exception("cmd_gold fail")
            self.send(chat_id, "\u26a0\ufe0f Metals data nahi mila \u2014 "
                               "thodi der baad try karo.")

    def autoscan_hourly(self):
        """24/7 hourly scanner: movers -> setups -> channel post."""
        import futures as futures_mod
        mode = config.DEFAULT_MODE
        try:
            setups, note = futures_mod.quick_scan(mode)
            if setups:
                new_sigs, _ = signals_mod.record_setups(
                    [dict(s, kind="FUTURES") for s in setups], kind="FUTURES")
                if new_sigs:
                    log.info("AutoScan: %d naye futures setups (%s)",
                             len(new_sigs), note)
                    self._publish_futures(new_sigs, skip_record=True)
                    self.post_channel(
                        "\U0001f916 <b>AUTO-SCANNER: NAYA SETUP MILA!</b>\n"
                        f"<i>Movement: {html.escape(note)}</i>")
            # BTC/ETH/SOL futures watch (har ghante)
            try:
                import futures as fm2
                ms, analyzed = fm2.majors_setups(mode)
                if ms:
                    new_m, _ = signals_mod.record_setups(
                        [dict(s, kind="FUTURES") for s in ms], kind="FUTURES")
                    if new_m:
                        log.info("AutoScan: MAJORS setups %s",
                                 [s["symbol"] for s in new_m])
                        self._publish_futures(new_m, skip_record=True)
                        self.post_channel(
                            "\U0001f451 <b>MAJORS ALERT \u2014 BTC/ETH/SOL setup!</b>")
                # ---- EARLY ALERTS: setup forming (roz ek baar per coin) ----
                import pro as pro_mod
                today = time.strftime("%Y-%m-%d")
                early = storage.get_state().get("early_alerts", {})
                for a in analyzed:
                    ok, missing = pro_mod.setup_forming(a)
                    key = f"{a['symbol']}_LONG"
                    if ok and early.get(key) != today:
                        early[key] = today
                        storage.set_state("early_alerts", early)
                        self.post_channel(
                            f"\u26a1 <b>SETUP FORMING: {a['symbol']} LONG</b>\n"
                            f"Price {analyzer.fmt_price(a['price'])} | Score {a['score']:.0f}\n"
                            f"Baaki: {', '.join(missing)}\n"
                            f"<i>Confirm hote hi pura signal + chart milega.</i>")
                        log.info("Early alert: %s (missing: %s)", a["symbol"], missing)
            except Exception:
                log.exception("majors watch fail")

            # ---- GOLD/SILVER signals (har ghante, alert 12h gap) ----
            try:
                import metals as metals_mod
                msigs = metals_mod.scan_setups()
                strong = [s for s in msigs if s.get("tier") in ("A+", "A")]
                if strong:
                    mal = storage.get_state().get("metal_alerts", {})
                    bucket = time.strftime("%Y%m%d%H")
                    for s in strong:
                        key = f"{s['symbol']}_{s['side']}"
                        if mal.get(key, "") == bucket:
                            continue
                        mal[key] = bucket
                        storage.set_state("metal_alerts", mal)
                        self.post_channel(
                            "\U0001f6a8 <b>METALS SIGNAL!</b>\n"
                            + metals_mod.card(s))
                        log.info("Metal signal post: %s %s (%s)",
                                 s["symbol"], s["side"], s["tier"])
            except Exception:
                log.exception("metals scan fail")

            # ---- TOP OPPORTUNITIES guarantee (6h gap — HAMESHA kuch actionable)
            try:
                st_state = storage.get_state()
                if time.time() - st_state.get("last_top_post", 0) >= 6 * 3600:
                    pool = futures_mod.best_setups(mode, max_n=3)
                    try:
                        import metals as metals_mod2
                        pool = pool + metals_mod2.scan_setups()
                    except Exception:
                        pass
                    pool.sort(key=lambda x: x.get("conv", 0), reverse=True)
                    if pool:
                        lines = [
                            "\U0001f3c6 <b>TOP OPPORTUNITIES \u2014 ABHI KE BEST</b>",
                            "<i>Full confluence ka intezar na ho to ye bhi "
                            "actionable levels hain (Tier B = confirmation "
                            "pending)</i>", ""]
                        for s in pool[:3]:
                            lo, hi = s["entry"]
                            se = "\U0001f7e2" if s["side"] == "LONG" else "\U0001f534"
                            lines.append(
                                f"{se} "
                                f"<b>{html.escape(str(s['symbol']))} {s['side']}</b> "
                                f"[Tier {s.get('tier', '?')}] \u2014 Entry "
                                f"{analyzer.fmt_price(lo)}-{analyzer.fmt_price(hi)} "
                                f"| SL {analyzer.fmt_price(s['sl'])} | TP "
                                f"{analyzer.fmt_price(s['t1'])} "
                                f"<i>({html.escape(str(s.get('name', '')))})</i>")
                        lines.append("\n\u26a0\ufe0f Educational levels \u2014 "
                                     "DYOR, SL ke bina trade nahi.")
                        self.post_channel("\n".join(lines))
                        storage.set_state("last_top_post", time.time())
                        log.info("Top opportunities post: %d setups",
                                 len(pool[:3]))
            except Exception:
                log.exception("top opportunities fail")

            # existing signals bhi check karo (target/SL hits)
            updates, _ = signals_mod.check_signals(mode)
            if updates:
                self.publish_signal_updates(updates)
        except Exception:
            log.exception("autoscan_hourly failed")

    def cmd_autoscan(self, chat_id):
        cur = storage.get_state().get("autoscan", True)
        new = not cur
        storage.set_state("autoscan", new)
        if new:
            self.send(chat_id, "\U0001f916 <b>Auto-scanner ON!</b>\n"
                               "Ab har ghante market scan hoga \u2014 koi bhi trade setup "
                               "milega to khud signal channel pe aayega (bina poochhe). "
                               "Target/SL hits ki updates bhi auto.")
        else:
            self.send(chat_id, "\U0001f634 <b>Auto-scanner OFF.</b>\n"
                               "Ab signals sirf /weekly aur /futures commands pe milenge.")

    def cmd_trending(self, chat_id):
        self.send(chat_id, "🔥 Trending list nikal raha hoon...")
        trending = analyzer.fetch_trending()
        if not trending:
            self.send(chat_id, "Data nahi mila, thodi der baad try karo.")
            return
        lines = ["🔥 <b>COINGECKO TRENDING</b>\n"]
        for i, t in enumerate(trending[:10], 1):
            rank = f" (rank #{t['rank']})" if t.get("rank") else ""
            lines.append(f"{i}. <b>{t['symbol']}</b> — {html.escape(t['name'] or '')}{rank}")
        lines.append("\n⚠️ <i>Trending coins bahut volatile hote hain — chhota position, tight SL.</i>")
        self.send(chat_id, "\n".join(lines))

    # -------- performance --------
    def cmd_performance(self, chat_id):
        sigs, open_sigs, closed, wins = signals_mod.performance_summary()
        if not sigs:
            self.send(chat_id, "📊 Abhi tak koi signal record nahi hua.\n"
                               "<code>/weekly</code> chalao — picks auto-track hone lagenge!")
            return
        lines = ["📊 <b>SIGNAL PERFORMANCE TRACKER</b>\n"]
        wr = f"{len(wins)}/{len(closed)}" if closed else "-"
        wr_emo = "🟢" if (closed and len(wins) >= len(closed) / 2) else "🔴"
        lines.append(f"{wr_emo} Win rate: <b>{wr}</b> closed | 🔥 <b>{len(open_sigs)}</b> open\n")
        if open_sigs:
            lines.append("<b>🟡 OPEN POSITIONS</b>")
            for s in open_sigs:
                t1m = " ✅T1" if s["hit_t1"] else ""
                kind, side = s.get("kind", "SPOT"), s.get("side", "LONG")
                tag = (f" [{side}{' ' + str(s['lev']) + 'x' if s.get('lev') else ''}]"
                       if kind == "FUTURES" else "")
                lines.append(f"• <b>{s['sym']}</b>{tag} — entry {analyzer.fmt_price(s['entry'])} → "
                             f"{analyzer.fmt_price(s['last_price'])} "
                             f"({'🟢' if s['pnl_pct']>=0 else '🔴'}<b>{s['pnl_pct']:+.1f}%</b>){t1m}")
            lines.append("")
        if closed:
            lines.append("<b>📁 CLOSED</b>")
            for s in closed[:10]:
                r = s.get("result_pct") or 0
                emo = "✅" if r > 0 else "❌"
                why = {"CLOSED_TP2": "Target 2 hit 🎯", "CLOSED_SL": "Stop-loss",
                       "CLOSED_TIME": "30d time exit"}.get(s["status"], s["status"])
                lines.append(f"{emo} <b>{s['sym']}</b> <b>{r:+.1f}%</b> ({why}) — {s['ts'][:10]}")
        lines.append("\n⚠️ <i>Past performance future ka guarantee nahi. DYOR.</i>")
        self.send(chat_id, "\n".join(lines))

    # -------- portfolio --------
    def cmd_portfolio(self, chat_id):
        holdings = self._enriched_holdings(chat_id)
        for chunk in reports.portfolio_report(holdings, self._mode(chat_id)):
            self.send(chat_id, chunk)
        if holdings:
            path = charts.portfolio_chart(holdings)
            val = sum(h["qty"] * h["price"] for h in holdings)
            cost = sum(h["qty"] * h["buy"] for h in holdings)
            total_pnl = (val - cost) / cost * 100 if cost else 0
            self.send_photo(chat_id, path,
                            f"📦 Portfolio P&L: {'🟢' if total_pnl>=0 else '🔴'} <b>{total_pnl:+.1f}%</b>")

    def _enriched_holdings(self, chat_id):
        pf = storage.get_portfolio(chat_id)
        if not pf:
            return []
        markets = analyzer.fetch_markets(self._mode(chat_id))
        by_id = {c["id"]: c for c in markets}
        by_sym = {(c.get("symbol") or "").upper(): c for c in markets}
        out = []
        for sym, h in pf.items():
            coin = by_id.get(h.get("id")) or by_sym.get(sym)
            price = coin["current_price"] if coin else h["buy"]
            pnl = (price - h["buy"]) / h["buy"] * 100 if h["buy"] else 0
            out.append({"sym": sym, "qty": h["qty"], "buy": h["buy"],
                        "price": price, "pnl": pnl, "id": h.get("id")})
        return out

    def cmd_add(self, chat_id, args):
        if len(args) < 3:
            self.send(chat_id, "Format: <code>/add BTC 0.05 65000</code>\n(coin, quantity, buy price USD me)")
            return
        sym = args[0].upper()
        try:
            qty = float(args[1].replace(",", ""))
            buy = float(args[2].replace(",", "").replace("$", ""))
        except ValueError:
            self.send(chat_id, "Quantity aur price number me do. Jaise: <code>/add BTC 0.05 65000</code>")
            return
        markets = analyzer.fetch_markets(self._mode(chat_id))
        coin = next((c for c in markets if (c.get("symbol") or "").upper() == sym), None)
        if not coin:
            self.send(chat_id, f"❌ '{sym}' nahi mila top coins me. Symbol check karo.")
            return
        storage.add_holding(chat_id, sym, qty, buy, coin["id"], coin["name"])
        self.send(chat_id, f"✅ Added: <b>{qty} {sym}</b> @ {analyzer.fmt_price(buy)}\n"
                           f"📦 /portfolio se dekho")

    def cmd_remove(self, chat_id, args):
        if not args:
            self.send(chat_id, "Kaunsa hatana hai? <code>/remove BTC</code>")
            return
        ok = storage.remove_holding(chat_id, args[0])
        self.send(chat_id, f"{'✅ Hata diya ' + args[0].upper() if ok else '❌ ' + args[0].upper() + ' portfolio me nahi tha'}")

    # -------- watchlist --------
    def cmd_watch(self, chat_id, args):
        if not args:
            wl = storage.get_watchlist(chat_id)
            if wl:
                self.send(chat_id, "👁 Watching: " + ", ".join(f"<b>{w['symbol']}</b>" for w in wl))
            else:
                self.send(chat_id, "Watchlist khali hai. Add karo: <code>/watch SOL</code>")
            return
        sym = args[0].upper()
        markets = analyzer.fetch_markets(self._mode(chat_id))
        coin = next((c for c in markets if (c.get("symbol") or "").upper() == sym), None)
        if not coin:
            self.send(chat_id, f"❌ '{sym}' nahi mila.")
            return
        storage.watch(chat_id, sym, coin["id"], coin["name"])
        self.send(chat_id, f"👁 <b>{sym}</b> ab watchlist me hai — daily alerts milenge")

    def cmd_unwatch(self, chat_id, args):
        if not args:
            self.send(chat_id, "Kaunsa? <code>/unwatch SOL</code>")
            return
        ok = storage.unwatch(chat_id, args[0])
        self.send(chat_id, f"{'✅' if ok else '❌'} {args[0].upper()} {'watchlist se hata diya' if ok else 'watchlist me nahi tha'}")

    # -------- settings --------
    def cmd_risk(self, chat_id, args):
        if not args or args[0].lower() not in config.RISK_CONFIG:
            cur = self._mode(chat_id)
            self.send(chat_id, f"Abhi: <b>{cur}</b>\n"
                               "Options: <code>/risk safe</code>, <code>/risk balanced</code>, <code>/risk aggressive</code>")
            return
        mode = args[0].lower()
        storage.set_mode(chat_id, mode)
        with self._analysis_lock:
            self._analysis_cache.pop(mode, None)
        self.send(chat_id, MODE_TEXT[mode])

    def cmd_time(self, chat_id, args):
        if args and args[0].isdigit() and 0 <= int(args[0]) <= 23:
            config.DAILY_HOUR_IST = int(args[0])
            storage.set_state("daily_hour", config.DAILY_HOUR_IST)
            self.send(chat_id, f"⏰ Daily update ab roz <b>{config.DAILY_HOUR_IST}:00 IST</b> pe aayega")
        else:
            self.send(chat_id, f"⏰ Daily update time: <b>{config.DAILY_HOUR_IST}:00 IST</b>\nChange karo: <code>/time 9</code> (0-23)")

    # -------- channel commands --------
    def cmd_setchannel(self, chat_id, args):
        if args:
            cid = args[0]
            if cid.startswith("@") or cid.lstrip("-").isdigit():
                self.set_channel(chat_id, cid)
                self.send(chat_id, f"✅ Channel <b>{html.escape(cid)}</b> set ho gaya!\n"
                                   "🧪 /testchannel se verify karo (bot ko channel admin banaana mat bhoolna)")
                return
            self.send(chat_id, "Format: <code>/setchannel @channelusername</code> "
                               "ya numeric ID (-100...)")
            return
        self.send(chat_id,
                  "📺 <b>CHANNEL SETUP (2 minute)</b>\n\n"
                  "<b>Tarika 1 (sabse aasan):</b>\n"
                  "1. Apne Telegram channel me bot ko <b>Admin</b> banao\n"
                  "   (Post Messages + Invite Users permission)\n"
                  "2. Bas! Bot khud detect kar lega 🎉\n\n"
                  "<b>Tarika 2:</b>\n"
                  "Channel me koi bhi post <b>is chat me forward</b> kar do.\n\n"
                  "<b>Tarika 3:</b>\n"
                  "Public channel ho toh: <code>/setchannel @mychannel</code>")

    def cmd_invite(self, chat_id, args):
        if not self.is_admin(chat_id):
            self.send(chat_id, "🔒 Sirf admin hi invite links bana sakta hai.")
            return
        if not self.channel_id():
            self.send(chat_id, "❌ Pehle channel connect karo: /setchannel")
            return
        try:
            n = int(args[0]) if args else 1
        except ValueError:
            n = 1
        links = self.create_invites(max(1, min(n, 10)))
        if not links:
            self.send(chat_id, "❌ Link nahi ban paya. Bot ko channel me admin banao "
                               "<b>Invite Users via Link</b> permission ke saath.")
            return
        lines = [f"🔗 <b>{len(links)} one-time join link(s) ready!</b>\n"
                 "<i>Har link ek hi baar kaam karega — paid member ko ek link do, "
                 "join karte hi link dead (koi leak nahi).</i>\n"]
        for i, l in enumerate(links, 1):
            lines.append(f"{i}. {l}")
        lines.append("\n💡 <i>Payment ke baad link do — UPI/Razorpay/Gumroad se paisa lo, "
                     "ye bot sirf access manage karta hai.</i>")
        self.send(chat_id, "\n".join(lines))

    # ---------------- Polling loop ----------------
    def run(self):
        me = self._api("getMe", timeout=15)
        if not me or not me.get("ok"):
            raise RuntimeError("Telegram token invalid hai ya network issue hai!")
        log.info("Bot started as @%s", me["result"]["username"])
        saved = storage.get_state().get("tg_offset")
        if saved:
            self._offset = saved
        while True:
            try:
                r = self._api("getUpdates", data={"offset": self._offset, "timeout": 30},
                              timeout=40)
                for u in (r or {}).get("result", []):
                    self._offset = u["update_id"] + 1
                    storage.set_state("tg_offset", self._offset)
                    threading.Thread(target=self.handle, args=(u,), daemon=True).start()
            except Exception:
                log.exception("poll loop error")
                time.sleep(5)
