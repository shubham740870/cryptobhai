"""FOREX — GBPUSD + EURUSD (Yahoo hourly) — backtest-tuned params ke saath."""
import time
from urllib.parse import quote

import requests

import backtest
import indicators as ind

UA = {"User-Agent": "Mozilla/5.0 (compatible; CryptoBhaiAgent/1.0)"}
PAIRS = {
    "GBPUSD": {"ysym": "GBPUSD=X", "name": "GBP/USD", "flag": "\U0001f1ec\U0001f1e7\U0001f1ec\U0001f1e7"},
    "EURUSD": {"ysym": "EURUSD=X", "name": "EUR/USD", "flag": "\U0001f1ea\U0001f1fa"},
}
_cache = {}


def _fmt(x, dec=4):
    try:
        return f"{x:,.{dec}f}"
    except (TypeError, ValueError):
        return str(x)


def candles(sym, interval="1h", rng="1mo"):
    """Yahoo candles -> [[ms, close], ...] (result-charts ke liye)."""
    meta = PAIRS[sym]
    try:
        r = requests.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            + quote(meta["ysym"]),
            params={"interval": interval, "range": rng}, headers=UA, timeout=15)
        res = r.json()["chart"]["result"][0]
        ts = res.get("timestamp") or []
        closes = res["indicators"]["quote"][0]["close"]
        return [[t * 1000, c] for t, c in zip(ts, closes) if c]
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        return []


def fetch_pair(sym, ttl=900):
    """Pair ka TA dict (cache 15 min) — tuned params ke saath."""
    c = _cache.get(sym)
    if c and time.time() - c[1] < ttl:
        return c[0]
    closes, highs, lows = [], [], []
    try:
        r = requests.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            + quote(PAIRS[sym]["ysym"]),
            params={"interval": "1h", "range": "1mo"}, headers=UA, timeout=15)
        res = r.json()["chart"]["result"][0]
        q = res["indicators"]["quote"][0]
        closes = [x for x in q["close"] if x]
        highs = [x for x in q["high"] if x]
        lows = [x for x in q["low"] if x]
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        pass
    if len(closes) < 60:
        _cache[sym] = (None, time.time())
        return None
    px = closes[-1]
    r_raw = ind.rsi(closes)
    rsi = ind.last_valid(r_raw) if isinstance(r_raw, (list, tuple)) else (r_raw or 50)
    e20 = ind.last_valid(ind.ema(closes, 20)) or px
    e50 = ind.last_valid(ind.ema(closes, 50)) or px
    _, _, hist = ind.macd(closes)
    macd_h = ind.last_valid(hist) or 0
    atr_v = ind.last_valid(ind.atr(highs, lows, closes, 14)) or px * 0.002
    atr_pct = atr_v / px * 100
    ch24 = (px / closes[-25] - 1) * 100 if len(closes) > 25 else 0.0
    ch7d = (px / closes[-169] - 1) * 100 if len(closes) > 169 else 0.0
    hi24, lo24 = max(highs[-25:]), min(lows[-25:])
    if px > e20 > e50:
        trend = "UP"
    elif px < e20 < e50:
        trend = "DOWN"
    else:
        trend = "SIDE"
    out = dict(symbol=sym, name=PAIRS[sym]["name"], dec=4,
               price=px, ch24h=ch24, ch7d=ch7d, rsi=rsi, ema20=e20, ema50=e50,
               macd_hist=macd_h, atr=atr_v, atr_pct=atr_pct, trend=trend,
               hi24=hi24, lo24=lo24, id=f"fx-{sym.lower()}")
    _cache[sym] = (out, time.time())
    return out


def make_signal(m):
    """Tuned FX params se setup: SL 2.2xATR, TP 2.0xATR (backtest best)."""
    p = backtest.params("fx")
    px, atr_v = m["price"], m["atr"]
    sl_d = p["sl_mult"] * atr_v
    tp_d = p["tp_mult"] * atr_v
    long_ok = m["trend"] == "UP" and m["macd_hist"] > 0 and m["rsi"] < 74
    short_ok = m["trend"] == "DOWN" and m["macd_hist"] < 0 and m["rsi"] > 26
    side = "LONG" if long_ok else ("SHORT" if short_ok else None)
    tier = "B"
    if side and m["atr_pct"] >= 0.15:
        tier = "A"
    if side is None:
        side = "SHORT" if m["trend"] == "DOWN" else "LONG"
    d = 1 if side == "LONG" else -1
    return dict(
        symbol=m["symbol"], name=m["name"], dec=4,
        id=m["id"], price=px, side=side, tier=tier,
        score=50 + (8 if tier == "A" else 0),
        conv={"A": 52, "B": 32}[tier],
        entry=(px * 0.9995, px * 1.0005), sl=px - d * sl_d,
        t1=px + d * tp_d * 0.7, t2=px + d * tp_d,
        rr=tp_d / sl_d, lev=1, liq=0, risk_pct=abs(sl_d) / px * 100,
        confidence="MEDIUM" if tier == "A" else "WATCH",
        verdict=f"FX {side}", kind="FX",
        ch24h=m["ch24h"], ch7d=m["ch7d"], rsi=m["rsi"], trend=m["trend"],
        atr=atr_v, atr_pct=m["atr_pct"], hi24=m["hi24"], lo24=m["lo24"])


def scan_setups():
    out = []
    for sym in PAIRS:
        m = fetch_pair(sym)
        if m:
            try:
                out.append(make_signal(m))
            except Exception:
                pass
    return out


def card(s):
    d = s.get("dec", 4)
    emo = "\U0001f7e2" if s["side"] == "LONG" else "\U0001f534"
    tier_emo = {"A+": "\U0001f48e", "A": "\u2705", "B": "\U0001f440"}.get(s["tier"], "\u2022")
    tr_emo = {"UP": "\U0001f4c8", "DOWN": "\U0001f4c9", "SIDE": "\u2194\ufe0f"}.get(s["trend"], "\u2022")
    return (
        f"\U0001f4b1 <b>{s['name']} (FX)</b> \u2014 {_fmt(s['price'])}\n"
        f"24h {s['ch24h']:+.2f}% \u00b7 7d {s['ch7d']:+.2f}% \u00b7 RSI {s['rsi']:.0f} \u00b7 "
        f"Trend {tr_emo} {s['trend']}\n"
        f"ATR {_fmt(s['atr'])} ({s['atr_pct']:.2f}%) | 24h H/L: "
        f"{_fmt(s['hi24'])} / {_fmt(s['lo24'])}\n"
        f"\n{emo} <b>SIGNAL: {s['side']}</b> {tier_emo} Tier {s['tier']} \u00b7 "
        f"Confidence: {s['confidence']}\n"
        f"\U0001f4cd Entry: {_fmt(s['entry'][0])} \u2013 {_fmt(s['entry'][1])}\n"
        f"\U0001f6d1 SL: {_fmt(s['sl'])} ({s['risk_pct']:.2f}% risk)\n"
        f"\U0001f3af TP1: {_fmt(s['t1'])} | TP2: {_fmt(s['t2'])}\n"
        f"<i>Hourly candles \u00b7 backtest-tuned \u00b7 educational, DYOR</i>")


def report():
    parts = ["\U0001f4b1 <b>FX DESK \u2014 GBP/USD + EUR/USD</b>\n"]
    for s in scan_setups():
        parts.append(card(s))
        parts.append("")
    if len(parts) < 3:
        parts.append("\u26a0\ufe0f FX data abhi available nahi. Thodi der me try karo.")
    return "\n".join(parts)
