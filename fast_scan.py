"""5-min fast scanner — BTC/ETH/SOL ka turant analysis + auto-posting.

Sirf VPS/Termux (24/7 script) ke liye — GitHub Actions minimum 5 min ka
hai aur queue delays hote hain, isliye exact 5-min cadence yahan milta hai.

Kya karta hai har 5 min:
1. BTC/ETH/SOL ka price + 1h momentum + RSI (1 API call — rate-limit safe)
2. Koi bada move (1h >= 1% ya 24h >= 4%) ya RSI extreme → turant channel pe alert
3. Har 60 min me: deep scan (futures setups + signal check + journal)
4. Journal sheet (agar set hai) → live P&L check → koi target/SL hit → update

Spam protection: same coin ke liye min 2 ghante ka gap alerts ke beech.
"""
import logging
import os
import time

import analyzer
import config
import futures as futures_mod
import journal as journal_mod
import signals as signals_mod
import storage

log = logging.getLogger("fast")

ALERT_COOLDOWN = 2 * 3600     # same coin, same type alert: 2 ghante
DEEP_EVERY = 12               # 12 x 5min = har ghante deep scan


def _should_alert(key, state, min_gap=ALERT_COOLDOWN):
    last = state.get(key, 0)
    if time.time() - last >= min_gap:
        state[key] = time.time()
        storage.set_state("fast_alerts", state)
        return True
    return False


def run_fast_cycle(bot):
    """Ek 5-min cycle. bot = CryptoBot instance (channel post ke liye)."""
    mode = config.DEFAULT_MODE
    state = storage.get_state()
    fast_state = state.get("fast_alerts", {})
    cycle = state.get("fast_cycle", 0) + 1
    storage.set_state("fast_cycle", cycle)

    # 1) quick scan (1 API call)
    try:
        snap = analyzer.quick_scan_5min(mode)
    except Exception:
        log.exception("quick_scan_5min fail")
        return

    moves = []
    for sym, d in snap.items():
        if abs(d["ch1h"]) >= 1.0 or abs(d["ch24h"]) >= 4.0:
            moves.append((sym, d))
        # RSI extreme
        if d.get("rsi_1h"):
            if d["rsi_1h"] >= 75 and _should_alert(f"{sym}_RSIH", fast_state):
                bot.post_channel(
                    f"⚠️ <b>{sym}</b> 1h RSI <b>{d['rsi_1h']:.0f}</b> — overbought!\n"
                    f"Price {analyzer.fmt_price(d['price'])} | 24h {d['ch24h']:+.1f}%\n"
                    f"<i>Profit booking socho, naya LONG entry mat lo.</i>")
            elif d["rsi_1h"] <= 28 and _should_alert(f"{sym}_RSIL", fast_state):
                bot.post_channel(
                    f"💡 <b>{sym}</b> 1h RSI <b>{d['rsi_1h']:.0f}</b> — oversold dip!\n"
                    f"Price {analyzer.fmt_price(d['price'])} | 24h {d['ch24h']:+.1f}%\n"
                    f"<i>Uptrend me dip-buy ka chance — deep signal ka wait karo.</i>")

    if moves:
        for sym, d in moves:
            if _should_alert(f"{sym}_MOVE", fast_state):
                arrow = "🟢" if d["ch1h"] >= 0 else "🔻"
                bot.post_channel(
                    f"{arrow} <b>{sym} MOVE DETECTED</b>\n"
                    f"Price: {analyzer.fmt_price(d['price'])} | "
                    f"1h: {d['ch1h']:+.2f}% | 24h: {d['ch24h']:+.1f}%\n"
                    f"<i>Deep analysis chal raha — setup bana to signal + chart milega.</i>")
        # bade move pe turant deep check (rate-limit allow kare to)
        try:
            setups, _ = futures_mod.quick_scan(mode)
            if setups:
                new_sigs, _ = signals_mod.record_setups(
                    [dict(s, kind="FUTURES") for s in setups], kind="FUTURES")
                if new_sigs:
                    bot._publish_futures(new_sigs, skip_record=True)
        except Exception:
            log.exception("deep scan on move fail")

    # 2) hourly deep cycle
    if cycle % DEEP_EVERY == 0:
        log.info("fast cycle %d -> deep scan", cycle)
        try:
            bot.autoscan_hourly()
        except Exception:
            log.exception("deep scan fail")

    # 3) journal check (agar sheet set hai) — PRIVATE: personal chat only
    if config.JOURNAL_SHEET_URL:
        try:
            entries, err = journal_mod.load_entries()
            if err:
                if cycle % DEEP_EVERY == 0:
                    log.info("journal: %s", err)
            else:
                markets = analyzer.fetch_markets(mode)
                # sheet me live prices push (silent)
                try:
                    journal_mod.sheet_push_prices(entries, markets)
                except Exception:
                    pass
                # koi target/SL hit hua? -> PERSONAL alert (channel pe nahi)
                jtgt = os.environ.get("CHAT_ID", "").strip() or config.FALLBACK_CHAT
                for a in journal_mod.analyze(entries, markets):
                    key = f"JRNL_{a['sym']}_{a['side']}_{a['entry']}"
                    if a["status"] in ("TARGET_HIT", "SL_HIT") and \
                            _should_alert(key, fast_state, min_gap=6 * 3600):
                        emo = "✅" if a["status"] == "TARGET_HIT" else "🛑"
                        msg = (
                            f"{emo} <b>JOURNAL: {a['sym']} {a['side']}</b> — "
                            f"{a['status'].replace('_', ' ')}!\n"
                            f"Entry {analyzer.fmt_price(a['entry'])} → "
                            f"{analyzer.fmt_price(a['price'])}\n"
                            f"P&L: <b>{a['pnl_pct']:+.1f}%</b> (${a['pnl_usd']:+.2f})")
                        if not bot.send(jtgt, msg):
                            bot.send(config.FALLBACK_CHAT, msg)
        except Exception:
            log.exception("journal check fail")
