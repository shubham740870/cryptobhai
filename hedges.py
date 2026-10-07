"""HEDGE SLEEVE v16 (user-approved): 30% capital BTC→GOLD rotation
+ USDINR rupee-stress filter on NSE entries.

5y backtest (₹1L): 70% main + 30% rotation → ₹6.0L, maxDD -17.8%
(100% main: ₹3.0L, -24.4%). USDINR overlay: DD -24.4% → -17%, return ~same.
Rules:
- BTC close > EMA200  → sleeve BTC me (risk-ON)
- BTC close < EMA200  → sleeve GOLD me (risk-OFF)
- USDINR > EMA50      → NSE naye entries block (fail-open agar data na mile)
"""
import datetime as dt
import json
import os

import requests

import indicators as ind

UA = {"User-Agent": "Mozilla/5.0 (compatible; CryptoBhaiAgent/1.0)"}
STATE_FILE = os.path.join("data", "rotation_state.json")


def _daily(sym, rng="1y"):
    """Yahoo daily closes -> (dates, closes) ascending. Fail -> ([], [])."""
    try:
        r = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
            params={"interval": "1d", "range": rng}, headers=UA, timeout=15)
        j = r.json()["chart"]["result"][0]
        ts = j.get("timestamp") or []
        q = j["indicators"]["quote"][0]
        out = []
        for t, c in zip(ts, q["close"]):
            if c:
                out.append((dt.datetime.fromtimestamp(t, dt.timezone.utc).date(), c))
        if not out:
            return [], []
        dates = [d for d, _ in out]
        closes = [c for _, c in out]
        return dates, closes
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return [], []


def _lv(v):
    if isinstance(v, list):
        v = ind.last_valid(v)
    return v


def usdinr_stress():
    """True = USDINR EMA50 ke upar (rupee-stress) -> NSE naya risk OFF."""
    dates, c = _daily("INR=X", "1y")
    if len(c) < 60:
        return False          # fail-open: data nahi to block mat karo
    e = ind.ema(c, 50)
    v = _lv(e[-1])
    return bool(v and c[-1] > v)


def _load():
    try:
        return json.load(open(STATE_FILE, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(st):
    try:
        json.dump(st, open(STATE_FILE, "w", encoding="utf-8"), indent=1)
    except OSError:
        pass


def rotation_update(post=None):
    """BTC→GOLD state machine (30% sleeve). Flip pe channel alert. State return."""
    dates, c = _daily("BTC-USD", "1y")
    st = _load()
    if len(c) < 220:          # EMA200 ke liye kam data — purana state rakho
        return st
    e = ind.ema(c, 200)
    v = _lv(e[-1])
    if not v:
        return st
    mode = "BTC" if c[-1] > v else "GOLD"
    old = st.get("mode")
    today = str(dt.date.today())
    px_now = c[-1]
    if old != mode:
        _, gc = _daily("GC=F", "5d")
        entry = gc[-1] if (mode == "GOLD" and gc) else px_now
        st = {"mode": mode, "since": today, "entry_px": entry,
              "flips": (st.get("flips") or 0) + (1 if old else 0)}
        _save(st)
        if post and old:      # pehli baar silent init, flips pe hi alert
            try:
                if mode == "GOLD":
                    msg = ("🛡️ <b>HEDGE SLEEVE SHIFT</b> (30% capital)\n"
                           f"BTC → GOLD | BTC 200-EMA ke NEECHE (risk-OFF)\n"
                           f"GOLD entry: ~${entry:,.0f}\n"
                           "<i>Signal-book (70%) normal chalta rahega</i>")
                else:
                    msg = ("🚀 <b>HEDGE SLEEVE SHIFT</b> (30% capital)\n"
                           f"GOLD → BTC | BTC 200-EMA ke UPAR (risk-ON)\n"
                           f"BTC entry: ~${entry:,.0f}\n"
                           "<i>Signal-book (70%) normal chalta rahega</i>")
                post(msg)
            except Exception:
                pass
    else:
        st["last_px"] = px_now
        _save(st)
    return st


def sleeve_status():
    """Performance/report ke liye one-line status (MTM ke saath)."""
    st = _load()
    mode = st.get("mode")
    if not mode:
        return None
    dates, c = _daily("BTC-USD" if mode == "BTC" else "GC=F", "5d")
    px = c[-1] if c else st.get("last_px")
    ep = st.get("entry_px") or 0
    mtm = (px / ep - 1) * 100 if (px and ep) else 0.0
    emo = "🚀" if mode == "BTC" else "🛡️"
    return (f"{emo} <b>Hedge sleeve (30%): {mode}</b> since {st.get('since')} | "
            f"MTM {'🟢' if mtm >= 0 else '🔴'}<b>{mtm:+.1f}%</b>")
