#!/usr/bin/env python3
"""CryptoBhai Agent — main entry point.

  python agent.py                → Telegram bot start (scheduler ke saath)
  python agent.py --demo weekly  → weekly report banao (bot ke bina, test ke liye)
  python agent.py --demo daily   → daily report banao
  python agent.py --demo analyze sol → ek coin ka analysis
  python agent.py --selftest     → quick sanity check
"""
import argparse
import logging
import sys
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import config
import storage

IST = ZoneInfo("Asia/Kolkata")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("agent")


# ---------------------------------------------------------------------------
# Scheduler — daily update + weekly report (IST)
# ---------------------------------------------------------------------------

class Scheduler(threading.Thread):
    def __init__(self, bot):
        super().__init__(daemon=True)
        self.bot = bot

    def _next_run(self, hour, weekday=None):
        """Agla run time (IST). weekday=None => roz, warna 0=Mon..6=Sun."""
        now = datetime.now(IST)
        run = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if weekday is None:
            if run <= now:
                run += timedelta(days=1)
        else:
            days_ahead = (weekday - now.weekday()) % 7
            run += timedelta(days=days_ahead)
            if run <= now:
                run += timedelta(days=7)
        return run

    def run(self):
        log.info("Scheduler started: daily %02d:00 IST, weekly day=%d",
                 config.DAILY_HOUR_IST, config.WEEKLY_DAY_ISO - 1)
        state = storage.get_state()
        self._next_daily = self._next_run(config.DAILY_HOUR_IST)
        self._next_weekly = self._next_run(config.WEEKLY_HOUR_IST,
                                           config.WEEKLY_DAY_ISO - 1)
        if state.get("daily_hour") is not None:
            config.DAILY_HOUR_IST = state["daily_hour"]
            self._next_daily = self._next_run(config.DAILY_HOUR_IST)
        self._next_hourly = datetime.now(IST) + timedelta(minutes=60)
        log.info("24/7 auto-scanner: %s", "ON" if state.get("autoscan", True) else "OFF")
        while True:
            now = datetime.now(IST)
            if now >= self._next_daily:
                log.info("=> Daily run")
                try:
                    self._do_daily()
                except Exception:
                    log.exception("daily failed")
                self._next_daily = self._next_run(config.DAILY_HOUR_IST)
            if now >= self._next_weekly:
                log.info("=> Weekly run")
                try:
                    self._do_weekly()
                except Exception:
                    log.exception("weekly failed")
                self._next_weekly = self._next_run(config.WEEKLY_HOUR_IST,
                                                   config.WEEKLY_DAY_ISO - 1)
            if now >= self._next_hourly:
                # 24/7 hourly scanner — naye futures setups + signal hits
                self._next_hourly = now + timedelta(minutes=60)
                if storage.get_state().get("autoscan", True):
                    log.info("=> Hourly auto-scan")
                    try:
                        self.bot.autoscan_hourly()
                    except Exception:
                        log.exception("hourly scan failed")
            time.sleep(60)

    def _do_daily(self):
        import analyzer
        import reports
        import signals as signals_mod
        res = analyzer.run_daily(config.DEFAULT_MODE)
        chunks = reports.daily_report(res)
        text = "\n".join(chunks)
        self.bot.broadcast(text)
        self.bot.post_channel(text[:3500])
        log.info("Daily update bhej diya (%d chats)", len(storage.all_chat_ids()))
        # open signals check karo -> result posts (T1 hit / TP / SL)
        try:
            updates, open_sigs = signals_mod.check_signals(config.DEFAULT_MODE)
            if updates:
                self.bot.publish_signal_updates(updates)
                log.info("Signal updates: %d", len(updates))
            log.info("Open signals: %d", len(open_sigs))
        except Exception:
            log.exception("signal check failed")

    def _do_weekly(self):
        import analyzer
        import reports
        import signals as signals_mod
        res = analyzer.run_weekly(config.DEFAULT_MODE)
        chunks = reports.weekly_report(res)
        self.bot.broadcast("\n".join(chunks))
        # naye signals record karo + channel pe charts ke saath post karo
        try:
            new_sigs, _ = signals_mod.record_signals(res)
            new_syms = {s["sym"] for s in new_sigs}
            cards = [a for a in res.get("buys", [])
                     if a["symbol"] in new_syms] or res.get("buys", [])[:4]
            self.bot.publish_trade_cards(cards)
            if new_sigs:
                self.bot.post_channel(reports.channel_overview(res))
            log.info("Weekly report bhej di (%d chats, %d naye signals)",
                     len(storage.all_chat_ids()), len(new_sigs))
        except Exception:
            log.exception("weekly publish failed")


# ---------------------------------------------------------------------------
# Fast loop — 5-min scanner (VPS/Termux 24/7 ke liye)
# ---------------------------------------------------------------------------

def fast_loop():
    """Har 5 min quick scan + har ghante deep scan + journal check.

    Telegram commands bhi saath me chalte hain (background thread me polling).
    """
    from bot import CryptoBot

    if not config.TELEGRAM_TOKEN:
        print("TELEGRAM_TOKEN missing hai (.env me daalo)")
        sys.exit(1)
    bot = CryptoBot(config.TELEGRAM_TOKEN)
    import threading
    threading.Thread(target=bot.run, daemon=True).start()

    import time as _t
    import fast_scan
    log.info("FAST mode: har 5 min scan + har ghante deep | journal: %s",
             "ON" if config.JOURNAL_SHEET_URL else "off")
    while True:
        try:
            fast_scan.run_fast_cycle(bot)
        except Exception:
            log.exception("fast cycle fail")
        _t.sleep(300)


# ---------------------------------------------------------------------------
# Run-once mode (GitHub Actions / cron ke liye) — ek cycle chalao aur exit
# ---------------------------------------------------------------------------

def run_once():
    """Ek analysis cycle: signal checks + autoscan + daily/weekly agar waqt hai.
    Telegram polling NAHI karta (commands nahi) — sirf khud post karta hai."""
    import os
    # video engine ke deps ensure karo (GitHub Actions pe workflow file
    # update na ho paye to bhi videos kaam karein)
    try:
        import gtts  # noqa: F401
    except ImportError:
        try:
            import subprocess as _sp
            _sp.run([sys.executable, "-m", "pip", "install", "--quiet",
                     "gtts", "imageio-ffmpeg"], timeout=180)
        except Exception:
            pass
    import analyzer
    import reports
    import signals as signals_mod
    from bot import CryptoBot

    if not config.TELEGRAM_TOKEN:
        print("TELEGRAM_TOKEN missing (GitHub Secrets me daalo)")
        sys.exit(1)
    bot = CryptoBot(config.TELEGRAM_TOKEN)
    now = datetime.now(IST)
    today = now.strftime("%Y-%m-%d")
    state = storage.get_state()
    my_chat = os.environ.get("CHAT_ID", "").strip()

    log.info("Run-once cycle @ %s", now.strftime("%d %b %H:%M IST"))

    # 1) Har run: open signals check (T1 hit / TP2 / SL -> channel)
    try:
        updates, open_sigs = signals_mod.check_signals(config.DEFAULT_MODE)
        if updates:
            bot.publish_signal_updates(updates)
            log.info("Signal updates: %d", len(updates))
        log.info("Open signals: %d", len(open_sigs))
    except Exception:
        log.exception("signal check failed")

    # 2) Har run: hourly autoscan (naye futures setups -> channel)
    if state.get("autoscan", True):
        try:
            bot.autoscan_hourly()
        except Exception:
            log.exception("autoscan failed")

    # 2b) Trading journal check (agar sheet set hai)
    if config.JOURNAL_SHEET_URL:
        try:
            import journal as journal_mod
            entries, err = journal_mod.load_entries()
            if not err:
                markets = analyzer.fetch_markets(config.DEFAULT_MODE)
                rep = journal_mod.journal_report(entries, markets)
                bot.post_channel(rep)
                if my_chat:
                    bot.send(my_chat, rep[:3800])
                log.info("Journal post ho gaya (%d entries)", len(entries))
            else:
                log.info("journal: %s", err)
        except Exception:
            log.exception("journal fail")

    # 3) Daily update (din me ek baar)
    if now.hour >= config.DAILY_HOUR_IST and state.get("last_daily") != today:
        try:
            res = analyzer.run_daily(config.DEFAULT_MODE)
            chunks = reports.daily_report(res)
            bot.post_channel("\n".join(chunks)[:3500])
            if my_chat:
                if not bot.send(my_chat, "\n".join(chunks)[:3800]):
                    bot.send(config.FALLBACK_CHAT, "\n".join(chunks)[:3800])
            else:
                bot.send(config.FALLBACK_CHAT, "\n".join(chunks)[:3800])
            storage.set_state("last_daily", today)
            log.info("Daily post ho gaya")
        except Exception:
            log.exception("daily failed")

    # 4) Weekly report (har WEEKLY_DAY ko)
    if (now.weekday() == config.WEEKLY_DAY_ISO - 1
            and now.hour >= config.WEEKLY_HOUR_IST
            and state.get("last_weekly") != today):
        try:
            res = analyzer.run_weekly(config.DEFAULT_MODE)
            chunks = reports.weekly_report(res)
            bot.post_channel("\n".join(chunks)[:3800])
            if my_chat:
                for c in chunks:
                    bot.send(my_chat, c)
            else:
                for c in chunks:
                    bot.send(config.FALLBACK_CHAT, c)
            new_sigs, _ = signals_mod.record_signals(res)
            new_syms = {s["sym"] for s in new_sigs}
            cards = [a for a in res.get("buys", []) if a["symbol"] in new_syms] \
                    or res.get("buys", [])[:4]
            bot.publish_trade_cards(cards)
            if new_sigs:
                bot.post_channel(reports.channel_overview(res))
            storage.set_state("last_weekly", today)
            log.info("Weekly post ho gaya (%d naye spot signals)", len(new_sigs))
        except Exception:
            log.exception("weekly failed")

    # 5) Channel ID abhi bhi missing? Owner ko batao
    if not bot.channel_id():
        log.warning("CHANNEL_ID set nahi hai! GitHub repo -> Settings -> "
                    "Secrets and variables -> Actions -> CHANNEL_ID add karo")
    log.info("Run-once complete")


# ---------------------------------------------------------------------------
# Demo mode — bot ke bina report console + file me
# ---------------------------------------------------------------------------

def demo(kind, arg=None):
    import analyzer
    import reports

    def save(chunks, fname):
        text = "\n\n".join(c.replace("<b>", "**").replace("</b>", "**")
                           .replace("<i>", "_").replace("</i>", "_")
                           .replace("<code>", "`").replace("</code>", "`")
                           for c in chunks)
        path = f"{config.REPORTS_DIR}/{fname}"
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print("\n" + "=" * 70)
        for c in chunks:
            plain = (c.replace("<b>", "").replace("</b>", "")
                     .replace("<i>", "").replace("</i>", "")
                     .replace("<code>", "").replace("</code>", ""))
            print(plain)
        print("=" * 70)
        print(f"\n📁 Report saved: {path}")

    if kind == "weekly":
        import charts
        import signals as signals_mod
        t0 = time.time()
        res = analyzer.run_weekly(arg or config.DEFAULT_MODE,
                                  progress_cb=lambda m: print(f"  {m}"))
        save(reports.weekly_report(res), "weekly_sample.md")
        # charts + signal tracking demo
        new_sigs, open_sigs = signals_mod.record_signals(res)
        print(f"\n📈 {len(res['buys'])} buy picks ke charts ban raha hai...")
        for a in res["buys"][:4]:
            hist = analyzer.fetch_history(a["id"])
            if hist:
                p = charts.trade_chart(a, hist)
                print(f"  🖼 chart: {p}")
        print(f"\n📡 Naye signals recorded: {len(new_sigs)} | "
              f"Open: {len(open_sigs)}")
        for s in open_sigs:
            print(f"  • {s['sym']} entry {s['entry']:.4g} T1 {s['t1']:.4g} "
                  f"T2 {s['t2']:.4g} SL {s['sl']:.4g} [{s['status']}]")
        log.info("Done in %.0fs", time.time() - t0)
    elif kind == "daily":
        import signals as signals_mod
        res = analyzer.run_daily(arg or config.DEFAULT_MODE)
        save(reports.daily_report(res), "daily_sample.md")
        updates, open_sigs = signals_mod.check_signals(arg or config.DEFAULT_MODE)
        if updates:
            print("\n📡 SIGNAL UPDATES:")
            for u in updates:
                s = u["sig"]
                txt = reports.signal_result_text(s, u["event"], u["pnl_pct"])
                print("  " + txt.replace("\n", " | ")[:200])
        print(f"\n📊 Open signals: {len(open_sigs)}")
        for s in open_sigs:
            print(f"  • {s['sym']}: {s['pnl_pct']:+.1f}% [{'T1 hit' if s['hit_t1'] else 'OPEN'}]")
    elif kind == "futures":
        import charts
        import futures as futures_mod
        import signals as signals_mod
        analyzed = analyzer.run_futures(arg or config.DEFAULT_MODE,
                                        progress_cb=lambda m: print(f"  {m}"))
        longs, shorts = futures_mod.evaluate_setups(analyzed)
        print(reports.futures_report(longs, shorts)
              .replace("<b>", "").replace("</b>", "").replace("<i>", ""))
        # charts of top setups
        for a in (longs + shorts)[:3]:
            hist = analyzer.fetch_history(a["id"])
            if hist:
                p = charts.trade_chart(a, hist)
                print(f"  \U0001f5bc chart: {p}")
        # demo record
        new_sigs, _ = signals_mod.record_setups(
            [dict(s, kind="FUTURES") for s in longs[:2] + shorts[:1]], kind="FUTURES")
        print(f"\U0001f4e1 Recorded: {len(new_sigs)} futures signals")
    elif kind == "analyze":
        if not arg:
            print("Coin do: python agent.py --demo analyze sol")
            return
        import charts
        a = analyzer.run_single(arg, config.DEFAULT_MODE)
        if not a:
            print(f"'{arg}' nahi mila.")
            return
        save(reports.single_report(a, config.DEFAULT_MODE),
             f"analyze_{arg.lower()}.md")
        hist = analyzer.fetch_history(a["id"])
        if hist:
            p = charts.trade_chart(a, hist)
            print(f"🖼 Chart saved: {p}")
    else:
        print("Kind: weekly | daily | analyze <coin>")


def selftest():
    import analyzer
    import indicators as ind
    import reports

    # indicator sanity
    closes = [100 + i + (i % 3) for i in range(60)]
    assert ind.last_valid(ind.sma(closes, 20)) is not None
    assert ind.last_valid(ind.rsi(closes, 14)) is not None
    m, s, h = ind.macd(closes)
    assert ind.last_valid(h) is not None
    print("✅ indicators OK")

    # chunking sanity
    big = "\n".join(f"line {i} " + "x" * 50 for i in range(300))
    chunks = reports._merge_chunks([big])
    assert all(len(c) <= 4096 for c in chunks)
    print(f"✅ chunking OK ({len(chunks)} chunks)")

    # API sanity
    fng = analyzer.fetch_fear_greed()
    print(f"✅ API OK — Fear&Greed: {fng}")
    print("\n🎉 Sab tests pass! Bot chalane ke liye: python agent.py")


def main():
    ap = argparse.ArgumentParser(description="CryptoBhai Agent")
    ap.add_argument("--demo", nargs="*", default=None,
                    help="weekly | daily | futures | analyze <coin>")
    ap.add_argument("--coin", help="--demo analyze ke saath coin symbol")
    ap.add_argument("--run-once", action="store_true",
                    help="ek analysis cycle chalao aur exit (GitHub Actions ke liye)")
    ap.add_argument("--fast", action="store_true",
                    help="5-min fast scanner mode (VPS/Termux ke liye 24/7 loop)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return
    if args.run_once:
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s %(levelname)s %(name)s: %(message)s")
        run_once()
        return
    if args.fast:
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s %(levelname)s %(name)s: %(message)s")
        fast_loop()
        return
    if args.demo:
        kind = args.demo[0]
        coin = args.coin or (args.demo[1] if len(args.demo) > 1 else None)
        demo(kind, coin)
        return

    if not config.TELEGRAM_TOKEN:
        print("\n" + "=" * 60)
        print("❌ TELEGRAM_TOKEN missing hai!")
        print("\nSetup (2 minute ka kaam):")
        print("1. Telegram me @BotFather kholo")
        print("2. /newbot likho, naam do (jaise: CryptoBhai Bot)")
        print("3. Jo token mile (123456:ABC-xyz...), usse .env file me daalo:")
        print('   echo "TELEGRAM_TOKEN=123456:ABC-xyz" > .env')
        print("4. Fir se chalao: python agent.py")
        print("=" * 60 + "\n")
        sys.exit(1)

    from bot import CryptoBot
    bot = CryptoBot(config.TELEGRAM_TOKEN)
    Scheduler(bot).start()
    storage.cache_cleanup()
    print("🤖 CryptoBhai chal raha hai! Ctrl+C se band karo.")
    print(f"   Daily update: {config.DAILY_HOUR_IST}:00 IST | "
          f"Weekly: day {config.WEEKLY_DAY_ISO}, {config.WEEKLY_HOUR_IST}:00 IST")
    try:
        bot.run()
    except KeyboardInterrupt:
        print("\n👋 Band ho gaya. Phir milenge!")
    except RuntimeError as e:
        print(f"\n❌ {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
