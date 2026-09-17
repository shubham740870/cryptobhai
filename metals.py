"""GOLD (XAU) + SILVER (XAG) — Yahoo Finance free hourly data + full TA.

Bina API key: GC=F (gold futures) + SI=F (silver futures) 1h candles ->
RSI/EMA20/50/MACD/ATR -> tiered signals (A+/A/B) crypto engine ke format me.
"""
import time

import requests

import backtest
import indicators as ind

UA = {"User-Agent": "Mozilla/5.0 (compatible; CryptoBhaiAgent/1.0)"}
METALS = {
    "XAU": {"ysym": "GC=F", "name": "GOLD", "emoji": "\U0001f947", "dec": 1},
    "XAG": {"ysym": "SI=F", "name": "SILVER", "emoji": "\U0001f948", "dec": 3},
}
_cache = {}


def _fmt(x, dec=2):
    try:
        return f"{x:,.{dec}f}"
    except (TypeError, ValueError):
        return str(x)


def fetch_metal(sym, ttl=900):
    """Yahoo se 1h candles -> TA dict. Fail pe None (cache 15 min)."""
    c = _cache.get(sym)
    if c and time.time() - c[1] < ttl:
        return c[0]
    meta = METALS[sym]
    closes, highs, lows = [], [], []
    for host in ("query1", "query2"):
        try:
            r = requests.get(
                f"https://{host}.finance.yahoo.com/v8/finance/chart/{meta['ysym']}",
                params={"interval": "1h", "range": "1mo"},
                headers=UA, timeout=15)
            if r.status_code != 200:
                continue
            res = r.json()["chart"]["result"][0]
            q = res["indicators"]["quote"][0]
            closes = [x for x in q["close"] if x is not None]
            highs = [x for x in q["high"] if x is not None]
            lows = [x for x in q["low"] if x is not None]
            if closes:
                break
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
            continue
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
    atr_v = ind.last_valid(ind.atr(highs, lows, closes, 14)) or px * 0.004
    e200 = ind.last_valid(ind.ema(closes, 200)) or px
    r2v = ind.last_valid(ind.rsi(closes, 2)) or 50
    dhi = max(highs[-21:-1]) if len(highs) > 21 else px
    dlo = min(lows[-21:-1]) if len(lows) > 21 else px
    m126 = (px / closes[-127] - 1) if len(closes) > 127 else 0.0
    _atr_all = [x for x in (ind.atr(highs, lows, closes, 14) or []) if x]
    _apct = sorted(a / c * 100 for a, c in zip(_atr_all[-200:], closes[-len(_atr_all[-200:]):]) if c)
    amed = _apct[len(_apct) // 2] if _apct else (atr_v / px * 100) * 1.2
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
    out = dict(symbol=sym, name=meta["name"], emoji=meta["emoji"], dec=meta["dec"],
               price=px, ch24h=ch24, ch7d=ch7d, rsi=rsi, ema20=e20, ema50=e50,
               macd_hist=macd_h, atr=atr_v, atr_pct=atr_pct, trend=trend,
               hi24=hi24, lo24=lo24, id=f"metal-{sym.lower()}", e200=e200, rsi2=r2v, don_hi=dhi, don_lo=dlo, mom126=m126, atr_med=amed)
    _cache[sym] = (out, time.time())
    return out


def candles(sym, interval="1h", rng="3mo"):
    """Yahoo candles -> [[ms, close], ...] (result-charts ke liye)."""
    try:
        r = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{METALS[sym]['ysym']}",
            params={"interval": interval, "range": rng}, headers=UA, timeout=15)
        res = r.json()["chart"]["result"][0]
        ts = res.get("timestamp") or []
        closes = res["indicators"]["quote"][0]["close"]
        return [[t * 1000, c] for t, c in zip(ts, closes) if c]
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        return []


def make_signal(m):
    """Tuned METALS params (backtest: SL 2.2xATR, TP 3.0xATR, EMA20/50)."""
    p = backtest.params("metals")
    px, atr_v = m["price"], m["atr"]
    sl_d = p["sl_mult"] * atr_v
    tp_d = p["tp_mult"] * atr_v
    import masters as _masters
    side, tier = _masters.entry(m, p.get("strategy", "trend_atr"))
    d = 1 if side == "LONG" else -1
    sl = px - d * sl_d
    t1 = px + d * tp_d * 0.7
    t2 = px + d * tp_d
    risk = abs(px - sl) / px * 100
    return dict(
        symbol=m["symbol"], name=m["name"], emoji=m["emoji"], dec=m["dec"],
        id=m["id"], price=px, side=side, tier=tier,
        score=50 + (12 if tier == "A+" else 6 if tier == "A" else 0),
        conv={"A+": 70, "A": 55, "B": 35}[tier],
        entry=(px * 0.999, px * 1.001), sl=sl, t1=t1, t2=t2,
        rr=2.2 / 1.8, lev=1, liq=0, risk_pct=risk,
        confidence="HIGH" if tier in ("A+", "A") else "WATCH",
        verdict=f"METALS {side}", kind="METALS",
        ch24h=m["ch24h"], ch7d=m["ch7d"], rsi=m["rsi"], trend=m["trend"],
        atr=atr_v, atr_pct=m["atr_pct"], hi24=m["hi24"], lo24=m["lo24"])


def scan_setups():
    """[gold_setup, silver_setup] — jo bhi ban paye (tier ke saath)."""
    out = []
    for sym in METALS:
        m = fetch_metal(sym)
        if m:
            try:
                out.append(make_signal(m))
            except Exception:
                pass
    return out


def card(s):
    """Setup ko clean HTML card banao (channel + chat dono ke liye)."""
    d = s.get("dec", 2)
    emo = "\U0001f7e2" if s["side"] == "LONG" else "\U0001f534"
    tier_emo = {"A+": "\U0001f48e", "A": "\u2705", "B": "\U0001f440"}.get(s["tier"], "\u2022")
    tr_emo = {"UP": "\U0001f4c8", "DOWN": "\U0001f4c9", "SIDE": "\u2194\ufe0f"}.get(s["trend"], "\u2022")
    return (
        f"{s['emoji']} <b>{s['name']} ({s['symbol']}/USD)</b> \u2014 ${_fmt(s['price'], d)}\n"
        f"24h {s['ch24h']:+.2f}% \u00b7 7d {s['ch7d']:+.2f}% \u00b7 RSI {s['rsi']:.0f} \u00b7 "
        f"Trend {tr_emo} {s['trend']}\n"
        f"ATR {_fmt(s['atr'], d)} ({s['atr_pct']:.2f}%) | 24h H/L: "
        f"{_fmt(s['hi24'], d)} / {_fmt(s['lo24'], d)}\n"
        f"\n{emo} <b>SIGNAL: {s['side']}</b> {tier_emo} Tier {s['tier']} \u00b7 "
        f"Confidence: {s['confidence']}\n"
        f"\U0001f4cd Entry: {_fmt(s['entry'][0], d)} \u2013 {_fmt(s['entry'][1], d)}\n"
        f"\U0001f6d1 SL: {_fmt(s['sl'], d)} ({s['risk_pct']:.2f}% risk)\n"
        f"\U0001f3af TP1: {_fmt(s['t1'], d)} | TP2: {_fmt(s['t2'], d)}\n"
        f"<i>Hourly candles (Yahoo Finance) \u00b7 leverage suggest NAHI \u00b7 "
        f"educational, DYOR</i>")


def report():
    """Dono metals ka full report (/gold command)."""
    parts = ["\U0001f3c5 <b>METALS DESK \u2014 GOLD + SILVER</b>\n"]
    for s in scan_setups():
        parts.append(card(s))
        parts.append("")
    if len(parts) < 3:
        parts.append("\u26a0\ufe0f Metals data abhi available nahi (Yahoo down?). "
                     "Thodi der me try karo.")
    return "\n".join(parts)
