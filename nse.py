"""NSE — India Top-100 stocks (NIFTY 100) — Yahoo daily candles + tuned params.

Rate-limit friendly: har hour 25-stock ka rotating batch (pura cycle 4 hour),
open signals har check pe fresh price (60-min cache).
"""
import json
import os
import time
from urllib.parse import quote

import requests

import backtest
import indicators as ind

UA = {"User-Agent": "Mozilla/5.0 (compatible; CryptoBhaiAgent/1.0)"}
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "data", "nse_state.json")

# NIFTY 100 — India ke top 100 large caps
TICKERS = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "HINDUNILVR", "ITC",
    "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK", "BAJFINANCE",
    "ASIANPAINT", "MARUTI", "SUNPHARMA", "TITAN", "ULTRACEMCO", "NESTLEIND",
    "WIPRO", "ONGC", "NTPC", "POWERGRID", "M&M", "TATAMOTORS", "TATASTEEL",
    "JSWSTEEL", "ADANIENT", "ADANIPORTS", "COALINDIA", "HCLTECH", "TECHM",
    "DRREDDY", "CIPLA", "DIVISLAB", "APOLLOHOSP", "GRASIM", "SHREECEM",
    "HINDALCO", "VEDL", "DLF", "PIDILITIND", "SIEMENS", "ABB", "EICHERMOT",
    "HEROMOTOCO", "BAJAJ-AUTO", "TVSMOTOR", "MOTHERSON", "INDIGO", "BRITANNIA",
    "DABUR", "GODREJCP", "MARICO", "BAJAJFINSV", "HDFCAMC", "SBILIFE",
    "HDFCLIFE", "ICICIPRULI", "ICICIGI", "PFC", "RECLTD", "IOC", "BPCL",
    "GAIL", "BANKINDIA", "PNB", "CANBK", "UNIONBANK", "INDIANB", "BANKBARODA",
    "INDUSINDBK", "FEDERALBNK", "IDFCFIRSTB", "AUBANK", "LICI", "BEL", "HAL",
    "MAZDOCK", "IRFC", "RVNL", "BHEL", "TATAPOWER", "ADANIENSOL", "ATGL",
    "ADANIGREEN", "CONCOR", "UPL", "LTIM", "PERSISTENT", "COFORGE", "MPHASIS",
    "OFSS", "KPITTECH", "TATAELXSI", "CUMMINSIND", "BOSCHLTD", "TORNTPOWER",
    "NHPC", "SUZLON", "INDHOTEL", "TRENT", "JIOFIN", "HAVELLS", "VOLTAS",
]
TICKERS = list(dict.fromkeys(TICKERS))   # dedupe, order preserve
BATCH = 25
_cache = {}


def _fmt(x):
    try:
        return f"\u20b9{x:,.1f}"
    except (TypeError, ValueError):
        return str(x)


def _load_state():
    try:
        return json.load(open(STATE_FILE))
    except (OSError, ValueError):
        return {}


def _save_state(st):
    try:
        json.dump(st, open(STATE_FILE, "w"))
    except OSError:
        pass


def candles(sym, interval="1d", rng="1y"):
    """Yahoo NSE candles -> [[ms, close], ...]."""
    try:
        r = requests.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            + quote(f"{sym}.NS"),
            params={"interval": interval, "range": rng}, headers=UA, timeout=15)
        res = r.json()["chart"]["result"][0]
        ts = res.get("timestamp") or []
        closes = res["indicators"]["quote"][0]["close"]
        return [[t * 1000, c] for t, c in zip(ts, closes) if c]
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return []


def fetch_stock(sym, ttl=3600):
    """Stock ka TA dict (cache 60 min)."""
    c = _cache.get(sym)
    if c and time.time() - c[1] < ttl:
        return c[0]
    closes, highs, lows = [], [], []
    try:
        r = requests.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            + quote(f"{sym}.NS"),
            params={"interval": "1d", "range": "1y"}, headers=UA, timeout=15)
        res = r.json()["chart"]["result"][0]
        q = res["indicators"]["quote"][0]
        closes = [x for x in q["close"] if x]
        highs = [x for x in q["high"] if x]
        lows = [x for x in q["low"] if x]
    except (requests.RequestException, ValueError, KeyError, IndexError):
        pass
    if len(closes) < 120:
        _cache[sym] = (None, time.time())
        return None
    px = closes[-1]
    r_raw = ind.rsi(closes)
    rsi = ind.last_valid(r_raw) if isinstance(r_raw, (list, tuple)) else (r_raw or 50)
    e20 = ind.last_valid(ind.ema(closes, 20)) or px
    e50 = ind.last_valid(ind.ema(closes, 50)) or px
    e200 = ind.last_valid(ind.ema(closes, 200)) or px
    _, _, hist = ind.macd(closes)
    macd_h = ind.last_valid(hist) or 0
    atr_v = ind.last_valid(ind.atr(highs, lows, closes, 14)) or px * 0.02
    atr_pct = atr_v / px * 100
    ch5 = (px / closes[-6] - 1) * 100 if len(closes) > 6 else 0.0
    ch20 = (px / closes[-21] - 1) * 100 if len(closes) > 21 else 0.0
    hi52, lo52 = max(highs), min(lows)
    if px > e20 > e50:
        trend = "UP"
    elif px < e20 < e50:
        trend = "DOWN"
    else:
        trend = "SIDE"
    out = dict(symbol=sym, name=sym, dec=2, price=px, ch5d=ch5, ch20d=ch20,
               rsi=rsi, ema20=e20, ema50=e50, ema200=e200, macd_hist=macd_h,
               atr=atr_v, atr_pct=atr_pct, trend=trend,
               hi52=hi52, lo52=lo52, id=f"nse-{sym.lower().replace('&', '').replace('-', '')}")
    _cache[sym] = (out, time.time())
    return out


def make_signal(m):
    """Tuned NSE params: EMA50/200 trend, SL 2.2xATR, TP 2.0xATR (backtest)."""
    p = backtest.params("nse")
    px, atr_v = m["price"], m["atr"]
    sl_d = p["sl_mult"] * atr_v
    tp_d = p["tp_mult"] * atr_v
    long_ok = (m["price"] > m["ema50"]
               and (m["ema50"] > m["ema200"] if p["trend"] == "ema50_200" else True)
               and m["macd_hist"] > 0 and m["rsi"] < 74)
    short_ok = (m["price"] < m["ema50"]
                and (m["ema50"] < m["ema200"] if p["trend"] == "ema50_200" else True)
                and m["macd_hist"] < 0 and m["rsi"] > 26)
    side = "LONG" if long_ok else ("SHORT" if short_ok else None)
    tier = "B"
    if side:
        align = (m["trend"] == "UP") if side == "LONG" else (m["trend"] == "DOWN")
        tier = "A" if align else "B"
    if side is None:
        side = "SHORT" if m["trend"] == "DOWN" else "LONG"
    d = 1 if side == "LONG" else -1
    return dict(
        symbol=m["symbol"], name=m["name"], dec=2,
        id=m["id"], price=px, side=side, tier=tier,
        score=50 + (10 if tier == "A" else 0),
        conv={"A": 56, "B": 34}[tier],
        entry=(px * 0.997, px * 1.003), sl=px - d * sl_d,
        t1=px + d * tp_d * 0.7, t2=px + d * tp_d,
        rr=tp_d / sl_d, lev=1, liq=0, risk_pct=abs(sl_d) / px * 100,
        confidence="MEDIUM" if tier == "A" else "WATCH",
        verdict=f"NSE {side}", kind="NSE",
        ch5d=m["ch5d"], ch20d=m["ch20d"], rsi=m["rsi"], trend=m["trend"],
        atr=atr_v, atr_pct=m["atr_pct"], hi52=m["hi52"], lo52=m["lo52"])


def scan_setups(batch=BATCH):
    """Rotating batch scan -> tier A/A+ setups (movers hamesha included)."""
    st = _load_state()
    cursor = st.get("cursor", 0)
    batch_syms = [TICKERS[(cursor + i) % len(TICKERS)] for i in range(batch)]
    st["cursor"] = (cursor + batch) % len(TICKERS)
    _save_state(st)
    out = []
    for sym in batch_syms:
        m = fetch_stock(sym)
        if not m:
            continue
        try:
            s = make_signal(m)
            if s["tier"] in ("A", "A+"):
                out.append(s)
        except Exception:
            continue
        time.sleep(0.3)   # Yahoo polite
    out.sort(key=lambda x: x["conv"], reverse=True)
    return out


def movers_report(n=8):
    """Cached TA se top movers table (sirf cached — fast)."""
    rows = []
    for sym in TICKERS[:BATCH]:
        m = _cache.get(sym)
        if m and m[0]:
            m = m[0]
            rows.append((abs(m["ch20d"]), m))
    rows.sort(key=lambda x: x[0], reverse=True)
    lines = ["\U0001f1ee\U0001f1f3 <b>NSE SPOTLIGHT</b> (top movers)\n"]
    for _, m in rows[:n]:
        emo = "\U0001f7e2" if m["ch20d"] >= 0 else "\U0001f534"
        lines.append(f"{emo} <b>{m['symbol']}</b> {_fmt(m['price'])} "
                     f"({m['ch20d']:+.1f}% 1m) | RSI {m['rsi']:.0f} | {m['trend']}")
    return "\n".join(lines)


def card(s):
    emo = "\U0001f7e2" if s["side"] == "LONG" else "\U0001f534"
    tier_emo = {"A+": "\U0001f48e", "A": "\u2705", "B": "\U0001f440"}.get(s["tier"], "\u2022")
    tr_emo = {"UP": "\U0001f4c8", "DOWN": "\U0001f4c9", "SIDE": "\u2194\ufe0f"}.get(s["trend"], "\u2022")
    return (
        f"\U0001f1ee\U0001f1f3 <b>{s['symbol']} (NSE)</b> \u2014 {_fmt(s['price'])}\n"
        f"1M {s['ch20d']:+.1f}% \u00b7 RSI {s['rsi']:.0f} \u00b7 Trend {tr_emo} {s['trend']}\n"
        f"52w H/L: {_fmt(s['hi52'])} / {_fmt(s['lo52'])}\n"
        f"\n{emo} <b>SIGNAL: {s['side']}</b> {tier_emo} Tier {s['tier']} \u00b7 "
        f"Confidence: {s['confidence']}\n"
        f"\U0001f4cd Entry: {_fmt(s['entry'][0])} \u2013 {_fmt(s['entry'][1])}\n"
        f"\U0001f6d1 SL: {_fmt(s['sl'])} ({s['risk_pct']:.1f}% risk)\n"
        f"\U0001f3af TP1: {_fmt(s['t1'])} | TP2: {_fmt(s['t2'])}\n"
        f"<i>Daily candles \u00b7 swing 1-3 weeks \u00b7 backtest-tuned \u00b7 educational, DYOR</i>")


def report(batch_only=True):
    """NSE report — setups + movers (/nse command)."""
    parts = ["\U0001f1ee\U0001f1f3 <b>NSE DESK \u2014 INDIA TOP STOCKS</b>\n"]
    setups = scan_setups(batch=BATCH)
    strong = [s for s in setups if s["tier"] in ("A", "A+")]
    if strong:
        parts.append("\U0001f3af <b>LIVE SETUPS (Tier A/A+):</b>\n")
        for s in strong[:4]:
            parts.append(card(s))
            parts.append("")
    else:
        parts.append("\U0001f44d Koi bada setup nahi — patience best strategy.\n")
    parts.append(movers_report())
    parts.append("\n<i>Har hour 25 stocks rotate hote hain (100 = 4 hour cycle) · "
                 "educational, DYOR</i>")
    return "\n".join(parts)
