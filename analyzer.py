"""Market analyzer — data fetching, scoring aur buy/sell signal engine.

Data source: CoinGecko free API (koi key mandatory nahi; optional demo key
se rate limit better hoti hai — config.py me COINGECKO_KEY daal do).
"""
import html
import logging
import math
import threading
import time

import requests

import config
import storage
from indicators import (atr, bollinger, last_valid, linreg_slope, macd,
                        resample_daily, rsi, sma)

log = logging.getLogger("analyzer")

CG_BASE = "https://api.coingecko.com/api/v3"
FNG_URL = "https://api.alternative.me/fng/"

TTL_MARKETS = 600        # 10 min
TTL_HISTORY = 6 * 3600   # 6 hours
TTL_TRENDING = 3600
TTL_FNG = 4 * 3600


def fmt_price(p):
    """Price ko readable format me."""
    if p is None:
        return "?"
    if p >= 1000:
        return f"${p:,.0f}"
    if p >= 1:
        return f"${p:,.2f}"
    if p >= 0.01:
        return f"${p:.4f}"
    if p >= 0.0001:
        return f"${p:.6f}"
    return f"${p:.10f}"


def fmt_pct(x):
    if x is None:
        return "?"
    arrow = "🟢+" if x >= 0 else "🔴"
    return f"{arrow}{x:.1f}%"


class RateLimiter:
    """CoinGecko free tier friendly — adaptive interval + 429 backoff."""

    def __init__(self, min_interval=2.2):
        self.base_interval = min_interval
        self.interval = min_interval
        self._last = 0.0
        self._lock = threading.Lock()

    def wait(self):
        with self._lock:
            gap = time.time() - self._last
            if gap < self.interval:
                time.sleep(self.interval - gap)
            self._last = time.time()

    def hit_limit(self):
        """429 aaya — interval badha do (max 8s)."""
        with self._lock:
            self.interval = min(self.interval * 1.6, 8.0)
            self._last = time.time()

    def ok(self):
        """Success — dheere dheere wapas base pe aa jao."""
        with self._lock:
            self.interval = max(self.base_interval, self.interval * 0.8)


rl = RateLimiter()
_session = requests.Session()
_session.headers.update({"User-Agent": "CryptoBhai-Agent/1.0"})


def _cg_get(path, params=None, retries=3):
    for attempt in range(retries):
        rl.wait()
        try:
            r = _session.get(f"{CG_BASE}{path}", params=params, timeout=25)
            if r.status_code == 429:
                rl.hit_limit()
                wait = int(r.headers.get("retry-after", "15"))
                log.warning("429 rate limit, %ss wait...", wait)
                time.sleep(min(wait, 30) + 1)
                continue
            if r.status_code == 200:
                rl.ok()
                return r.json()
            log.warning("CG %s -> %s", path, r.status_code)
        except requests.RequestException as e:
            log.warning("CG %s error: %s", path, e)
            time.sleep(2 * (attempt + 1))
    return None


# ---------------------------------------------------------------------------
# Data fetchers (cached)
# ---------------------------------------------------------------------------

def fetch_markets(mode="aggressive", force=False):
    """Top coins — ek call me sab kuch: price, changes, volume, sparkline."""
    cfg = config.RISK_CONFIG[mode]
    key = f"markets_{mode}"
    if not force:
        cached = storage.cache_get(key, TTL_MARKETS)
        if cached:
            return cached
    all_coins = []
    for page in range(1, cfg["pages"] + 1):
        data = _cg_get("/coins/markets", {
            "vs_currency": "usd", "order": "market_cap_desc",
            "per_page": cfg["per_page"], "page": page,
            "price_change_percentage": "1h,24h,7d,30d,200d",
            "sparkline": "true"})
        if not data:
            continue
        for c in data:
            if isinstance(c, dict) and c.get("current_price") is not None:
                all_coins.append(c)
    if all_coins:
        storage.cache_set(key, all_coins)
    return all_coins


def fetch_trending():
    cached = storage.cache_get("trending", TTL_TRENDING)
    if cached:
        return cached
    data = _cg_get("/search/trending")
    out = []
    for c in (data or {}).get("coins", []):
        item = c.get("item", {})
        out.append({"id": item.get("id"), "symbol": (item.get("symbol") or "").upper(),
                    "name": item.get("name"), "rank": item.get("market_cap_rank")})
    if out:
        storage.cache_set("trending", out)
    return out


def fetch_fear_greed():
    cached = storage.cache_get("fng", TTL_FNG)
    if cached:
        return cached
    try:
        rl.wait()
        r = _session.get(FNG_URL, timeout=15)
        if r.status_code == 200:
            d = r.json().get("data", [{}])[0]
            out = {"value": int(d["value"]), "label": d["value_classification"]}
            storage.cache_set("fng", out)
            return out
    except (requests.RequestException, KeyError, ValueError, IndexError):
        pass
    return None


def fetch_history(coin_id, days=90):
    """90 din ka hourly price/volume — deep indicators ke liye."""
    key = f"hist_{coin_id}_{days}"
    cached = storage.cache_get(key, TTL_HISTORY)
    if cached:
        return cached
    data = _cg_get(f"/coins/{coin_id}/market_chart",
                   {"vs_currency": "usd", "days": days})
    if data and data.get("prices"):
        storage.cache_set(key, data)
        return data
    return None


# ---------------------------------------------------------------------------
# Filtering + scoring
# ---------------------------------------------------------------------------

def filter_universe(coins, mode):
    """Stables, wrapped tokens, low-volume coins hatao."""
    cfg = config.RISK_CONFIG[mode]
    out = []
    for c in coins:
        sym = (c.get("symbol") or "").lower()
        if sym in config.STABLES or sym in config.WRAPPED:
            continue
        if "stable" in (c.get("name") or "").lower():
            continue
        price = c.get("current_price") or 0
        # $0.95-1.05 ke beech flat price = probably stablecoin
        if 0.95 <= price <= 1.05 and abs(c.get("price_change_percentage_7d_in_currency") or 0) < 1.5:
            continue
        if (c.get("total_volume") or 0) < 1_500_000:      # illiquid / pump-dump
            continue
        if (c.get("market_cap") or 0) < cfg["mcap_floor"]:
            continue
        out.append(c)
    return out


def quick_score(c, trending_syms):
    """Stage-1 score (0-100) sirf markets data + 7d sparkline se."""
    ch7 = c.get("price_change_percentage_7d_in_currency") or 0
    ch30 = c.get("price_change_percentage_30d_in_currency") or 0
    ch200 = c.get("price_change_percentage_200d_in_currency") or 0
    mcap = c.get("market_cap") or 1
    vol = c.get("total_volume") or 0
    vol_mcap = vol / mcap if mcap else 0
    spark = (c.get("sparkline_in_7d") or {}).get("price") or []
    slope = linreg_slope(spark) if len(spark) > 24 else 0
    sym = (c.get("symbol") or "").upper()
    ath_dist = abs(c.get("ath_change_percentage") or 100)

    def t(x, s):
        return math.tanh(x / s)

    score = (30 * t(ch7, 15) + 28 * t(ch30, 40) + 14 * t(ch200, 60)
             + 14 * t(vol_mcap, 0.12) + 14 * t(slope, 8))
    score = max(0.0, min(100.0, score))
    if sym in trending_syms:
        score = min(100.0, score + 5)
    # ATH se 85%+ door + weak momentum = dead coin penalty
    if ath_dist > 85 and ch30 < 0:
        score *= 0.75
    return round(score, 1)


def _daily_from_history(hist):
    prices = hist.get("prices") or []
    if len(prices) < 40:
        return None
    return resample_daily(prices)


def deep_analyze(coin, hist, mode, trending_syms=frozenset()):
    """Full technical analysis — RSI, MACD, SMA, ATR, BB + levels + verdict."""
    name = coin.get("name", "?")
    sym = (coin.get("symbol") or "?").upper()
    price = coin.get("current_price") or 0
    dates, opens, highs, lows, closes = _daily_from_history(hist)

    closes = closes[-100:]
    highs = highs[-100:]
    lows = lows[-100:]

    s20 = sma(closes, 20)
    s50 = sma(closes, 50)
    r = rsi(closes, 14)
    m_line, m_sig, m_hist = macd(closes)
    bb_u, bb_m, bb_l = bollinger(closes, 20, 2)
    a14 = atr(highs, lows, closes, 14)

    px = closes[-1]
    rsi_now = last_valid(r) or 50.0
    sma20_now = last_valid(s20)
    sma50_now = last_valid(s50)
    macd_now = last_valid(m_line)
    sig_now = last_valid(m_sig)
    hist_now = last_valid(m_hist)
    hist_prev = m_hist[-4] if len(m_hist) >= 4 and m_hist[-4] is not None else hist_now
    atr_now = last_valid(a14) or px * 0.04
    bbu_now = last_valid(bb_u)
    bbl_now = last_valid(bb_l)
    bbm_now = last_valid(bb_m)

    ch7 = coin.get("price_change_percentage_7d_in_currency") or 0
    ch30 = coin.get("price_change_percentage_30d_in_currency") or 0
    ch200 = coin.get("price_change_percentage_200d_in_currency") or 0
    mcap = coin.get("market_cap") or 0
    vol = coin.get("total_volume") or 0
    vol_mcap = vol / mcap if mcap else 0
    hi30 = max(highs[-30:])
    lo30 = min(lows[-30:])
    dip_from_high = (hi30 - px) / hi30 * 100 if hi30 else 0
    atr_pct = atr_now / px if px else 0.05

    tags = []
    reasons = []

    # ---------------- Trend score (28) ----------------
    ts = 0.0
    if sma20_now and px > sma20_now:
        ts += 6
    if sma20_now and sma50_now and sma20_now > sma50_now:
        ts += 6
    if sma50_now and px > sma50_now:
        ts += 5
    else:
        tags.append("below_sma50")
    if macd_now is not None and sig_now is not None and macd_now > sig_now:
        ts += 6
    if hist_now is not None and hist_prev is not None and hist_now > hist_prev:
        ts += 5
    else:
        tags.append("macd_weak")

    # ---------------- Momentum (22) ----------------
    ms = 0.0
    if 50 <= rsi_now <= 68:
        ms += 12
        reasons.append(f"RSI {rsi_now:.0f} — healthy momentum zone")
    elif 45 <= rsi_now < 50 or 68 < rsi_now <= 72:
        ms += 7
    elif rsi_now > 78:
        ms += 0
        tags.append("overbought")
    elif 72 < rsi_now <= 78:
        ms += 3
        tags.append("hot")
    else:
        tags.append("weak_rsi")
    ms += 5 * max(-1, min(1, ch7 / 15))
    ms += 5 * max(-1, min(1, ch30 / 40))
    ms = max(0.0, ms)

    # ---------------- Volume interest (12) ----------------
    vs = 7 * max(-1, min(1, math.tanh(vol_mcap / 0.12)))
    # volume trend: last 5 din vs pichle 20 din ka avg (hourly vols se)
    vols = hist.get("total_volumes") or []
    if len(vols) > 200:
        recent = sum(v for _, v in vols[-10:]) / 10
        prior = sum(v for _, v in vols[-220:-30]) / 190
        if prior > 0:
            vs += 5 * max(-1, min(1, (recent / prior - 1) / 0.5))
    vs = max(0.0, vs)

    # ---------------- Entry quality (20) ----------------
    eq = 0.0
    if 2 <= dip_from_high <= 14:
        eq += 10
        reasons.append(f"30d high se {dip_from_high:.0f}% neeche — pullback buy zone")
    elif dip_from_high < 2:
        eq += 4
    else:
        eq += 6
    if bbm_now and px <= bbm_now * 1.02:
        eq += 5
    if rsi_now < 70:
        eq += 5

    # ---------------- Risk (18) ----------------
    rk = 0.0
    if atr_pct < 0.04:
        rk += 10
    elif atr_pct < 0.07:
        rk += 7
    elif atr_pct < 0.10:
        rk += 4
    else:
        tags.append("high_volatility")
    floor = config.RISK_CONFIG[mode]["mcap_floor"]
    if mcap >= floor * 10:
        rk += 8
    elif mcap >= floor:
        rk += 5
    if mode != "aggressive" and mcap < 1_000_000_000:
        rk -= 3
    rk = max(0.0, rk)

    score = round(max(0.0, min(100.0, ts + ms + vs + eq + rk)), 1)

    # trending bonus
    if sym in trending_syms:
        score = min(100.0, score + 4)
        reasons.append("CoinGecko trending list me hai 🔥")

    # ---------------- Levels (entry / target / stop-loss) ----------------
    atr_dist = max(1.8 * atr_pct, 0.055)
    risk_pct = max(0.05, min(0.13, atr_dist))
    # Bade caps (position trade) me thoda wide
    if mcap > 50_000_000_000:
        risk_pct = max(risk_pct, 0.09)
    sl = px * (1 - risk_pct)
    t1 = px * (1 + risk_pct * 1.5)
    t2 = px * (1 + risk_pct * 2.5)
    entry_low = min(px, sma20_now) * 0.99 if sma20_now else px * 0.99
    entry_high = px * 1.01
    if entry_low > entry_high:
        entry_low = px * 0.99
    rr = (t1 - px) / (px - sl) if px > sl else 0

    # ---------------- Verdict ----------------
    cfg = config.RISK_CONFIG[mode]
    if score >= cfg["strong_buy"]:
        verdict = "STRONG BUY"
    elif score >= cfg["buy_min"]:
        verdict = "BUY"
    elif score >= 45:
        verdict = "HOLD / WATCH"
    elif score >= 33:
        verdict = "SELL"
        tags.append("weak")
    else:
        verdict = "AVOID / EXIT"
        tags.append("weak")

    # Overrides
    if rsi_now > 78 and score >= cfg["buy_min"]:
        verdict = "HOLD / WATCH"
        reasons.append("Overbought — abhi naya entry risky, dip ka wait karo")
    if sma50_now and px < sma50_now and (sma20_now and sma20_now < sma50_now):
        if verdict in ("BUY", "STRONG BUY"):
            verdict = "HOLD / WATCH"
            reasons.append("Trend abhi repair ho raha hai — confirmation ka wait")

    # Parabolic guard — pump ke baad FOMO entry se bachao
    if ch7 >= 90 or ch30 >= 220:
        tags.append("parabolic")
        if verdict in ("BUY", "STRONG BUY"):
            verdict = "HOLD / WATCH"
            reasons.insert(0, f"⚠️ Pump warning: 7d {ch7:+.0f}% / 30d {ch30:+.0f}% — "
                              "parabolic move hai, correction ka wait karo, FOMO mat karo")

    # Overbought coins ke liye reasoning clean karo
    if "overbought" in tags:
        reasons = ([f"RSI {rsi_now:.0f} — overbought! Yaha buy nahi, "
                    "profit-book karo (agar holding hai)"]
                   + [r for r in reasons if "pullback" not in r])

    if not reasons:
        reasons.append("Mixed signals — clear setup ka wait karo")

    return {
        "id": coin.get("id"), "symbol": sym, "name": name,
        "price": px, "mcap": mcap, "rank": coin.get("market_cap_rank"),
        "ch7": ch7, "ch30": ch30, "ch200": ch200,
        "rsi": rsi_now, "sma20": sma20_now, "sma50": sma50_now,
        "macd_hist": hist_now, "atr_pct": atr_pct * 100,
        "dip_from_high": dip_from_high, "hi30": hi30, "lo30": lo30,
        "vol_mcap": vol_mcap,
        "score": score, "verdict": verdict, "tags": tags, "reasons": reasons,
        "entry": (entry_low, entry_high), "t1": t1, "t2": t2, "sl": sl,
        "rr": rr, "risk_pct": risk_pct * 100,
    }


# ---------------------------------------------------------------------------
# Full runs
# ---------------------------------------------------------------------------

def _deep_universe(mode):
    """Deep-dive ke liye coins chuno: top quick-score + watchlists + portfolios."""
    markets = fetch_markets(mode)
    if not markets:
        return [], []
    universe = filter_universe(markets, mode)
    trending = fetch_trending()
    trend_syms = {t["symbol"] for t in trending if t.get("symbol")}

    scored = []
    for c in universe:
        scored.append((quick_score(c, trend_syms), c))
    scored.sort(key=lambda x: x[0], reverse=True)

    n_deep = config.DEEP_DIVE_COUNT[mode]
    picks = [c for _, c in scored[:n_deep]]

    # user watchlist + portfolios ke coins bhi include karo (sab chats se)
    extra_ids = set()
    for f in storage.load_json("chats.json", {}):
        ud = storage.load_json(f"user_{f}.json", {})
        for h in ud.get("portfolio", {}).values():
            extra_ids.add(h.get("id"))
        for w in ud.get("watchlist", []):
            extra_ids.add(w.get("id"))
    by_id = {c["id"]: c for c in universe}
    for cid in extra_ids:
        if cid and cid in by_id and cid not in {c["id"] for c in picks}:
            picks.append(by_id[cid])

    # trending coins jo universe me nahi mile (chhote caps) — aggressive me add
    if mode == "aggressive":
        in_uni = {c["symbol"] for c in universe}
        for t in trending[:4]:
            if t["id"] not in {c["id"] for c in picks} and t["symbol"] not in in_uni:
                picks.append({"id": t["id"], "symbol": t["symbol"],
                              "name": t["name"], "trending_only": True})
    return picks, universe


def _resolve_trending_only(coin):
    """Trending coin jiska markets data nahi mila — minimal coin banao."""
    hist = fetch_history(coin["id"])
    if not hist:
        return None
    prices = hist.get("prices") or []
    vols = hist.get("total_volumes") or []
    if len(prices) < 40:
        return None
    px = prices[-1][1]
    ch = lambda days: _pct_over(prices, days)  # noqa: E731
    return {"id": coin["id"], "symbol": coin["symbol"], "name": coin["name"],
            "current_price": px, "market_cap": 0, "market_cap_rank": None,
            "total_volume": vols[-1][1] if vols else 0,
            "price_change_percentage_7d_in_currency": ch(7 * 24),
            "price_change_percentage_30d_in_currency": ch(30 * 24),
            "price_change_percentage_200d_in_currency": ch(90 * 24),
            "ath_change_percentage": None,
            "sparkline_in_7d": {"price": [p for _, p in prices[-168:]]}}


def _pct_over(prices, n_points):
    if len(prices) <= n_points:
        first = prices[0][1]
    else:
        first = prices[-(n_points + 1)][1]
    now = prices[-1][1]
    return (now - first) / first * 100 if first else 0


def _analyze_picks(picks, mode, trend_syms, progress_cb=None):
    """Picks list ka deep analysis (shared by weekly + futures)."""
    def say(msg):
        if progress_cb:
            progress_cb(msg)
    analyzed = []
    for i, coin in enumerate(picks, 1):
        if coin.get("trending_only"):
            real = _resolve_trending_only(coin)
            coin = real if real else None
        if coin is None:
            continue
        hist = fetch_history(coin["id"])
        if not hist:
            continue
        try:
            analyzed.append(deep_analyze(coin, hist, mode, trend_syms))
        except (KeyError, IndexError, ValueError, ZeroDivisionError) as e:
            log.warning("deep_analyze failed for %s: %s", coin.get("id"), e)
        if i % 4 == 0:
            say(f"⏳ {i}/{len(picks)} coins complete...")
    analyzed.sort(key=lambda a: a["score"], reverse=True)
    return analyzed


def run_weekly(mode="aggressive", progress_cb=None):
    """Weekly deep analysis — top picks, sells, trending, market overview."""
    def say(msg):
        if progress_cb:
            progress_cb(msg)

    markets = fetch_markets(mode)
    universe = filter_universe(markets, mode)
    trending = fetch_trending()
    trend_syms = {t["symbol"] for t in trending if t.get("symbol")}
    fng = fetch_fear_greed()

    btc = next((c for c in markets if c["symbol"] == "btc"), None)
    eth = next((c for c in markets if c["symbol"] == "eth"), None)

    picks, _ = _deep_universe(mode)
    say(f"🔍 {len(picks)} coins ka deep analysis chal raha hai...")
    analyzed = _analyze_picks(picks, mode, trend_syms, progress_cb)

    cfg = config.RISK_CONFIG[mode]
    buys = [a for a in analyzed if a["verdict"] in ("BUY", "STRONG BUY")][:6]
    holds = [a for a in analyzed if a["verdict"] == "HOLD / WATCH"
             and "overbought" not in a["tags"] and "parabolic" not in a["tags"]][:4]
    book_profit = [a for a in analyzed if "overbought" in a["tags"]
                   or "parabolic" in a["tags"]][:4]
    sells = [a for a in analyzed if a["verdict"] in ("SELL", "AVOID / EXIT")][:4]

    return {"mode": mode, "generated": time.strftime("%d %b %Y, %H:%M IST"),
            "fng": fng, "btc": btc, "eth": eth,
            "universe_count": len(universe),
            "buys": buys, "holds": holds, "book_profit": book_profit,
            "sells": sells, "trending": trending[:8], "analyzed": analyzed}


def run_single(symbol_or_id, mode="aggressive"):
    """Ek coin ka detailed analysis."""
    markets = fetch_markets(mode)
    target = None
    q = symbol_or_id.lower().strip()
    for c in markets:
        if c["symbol"].lower() == q or c["id"] == q:
            target = c
            break
    if not target:  # top-250 me nahi? direct id try karo
        hist0 = fetch_history(q, 90)
        if hist0:
            target = {"id": q, "symbol": q.upper(), "name": q,
                      "current_price": hist0["prices"][-1][1], "market_cap": 0,
                      "market_cap_rank": None, "total_volume": 0,
                      "price_change_percentage_7d_in_currency": None,
                      "price_change_percentage_30d_in_currency": None,
                      "price_change_percentage_200d_in_currency": None,
                      "ath_change_percentage": None, "sparkline_in_7d": {"price": []}}
            hist = hist0
        else:
            return None
    hist = fetch_history(target["id"])
    if not hist:
        return None
    trending = fetch_trending()
    trend_syms = {t["symbol"] for t in trending if t.get("symbol")}
    return deep_analyze(target, hist, mode, trend_syms)


def run_futures(mode="aggressive", progress_cb=None):
    """Futures-focused analysis — liquid coins ka deep scan (LONG/SHORT dono)."""
    def say(msg):
        if progress_cb:
            progress_cb(msg)

    markets = fetch_markets(mode)
    trending = fetch_trending()
    trend_syms = {t["symbol"] for t in trending if t.get("symbol")}

    # futures ke liye sirf liquid coins (achhi volume wale)
    universe = [c for c in filter_universe(markets, mode)
                if (c.get("total_volume") or 0) >= 5_000_000
                and (c.get("market_cap") or 0) >= 50_000_000]

    scored = [(quick_score(c, trend_syms), c) for c in universe]
    scored.sort(key=lambda x: x[0], reverse=True)
    # long candidates (top) + short candidates (bottom) dono cover karo
    n = config.DEEP_DIVE_COUNT[mode]
    picks = [c for _, c in scored[:n]]
    bottom_ids = {c["id"] for c in picks}
    bottoms = [c for _, c in scored[-10:] if c["id"] not in bottom_ids]
    picks += bottoms
    say(f"🔍 {len(picks)} liquid coins ka LONG/SHORT scan...")
    analyzed = _analyze_picks(picks, mode, trend_syms, progress_cb)
    return analyzed


def run_daily(mode="aggressive"):
    """Daily light update — portfolio/watchlist alerts + movers + market mood."""
    markets = fetch_markets(mode)
    universe = filter_universe(markets, mode)
    fng = fetch_fear_greed()
    trending = fetch_trending()
    btc = next((c for c in markets if c["symbol"] == "btc"), None)
    eth = next((c for c in markets if c["symbol"] == "eth"), None)

    movers_up = sorted(universe, key=lambda c: c.get("price_change_percentage_24h_in_currency") or 0, reverse=True)[:5]
    movers_dn = sorted(universe, key=lambda c: c.get("price_change_percentage_24h_in_currency") or 0)[:5]

    # 7d momentum gainers (swing view)
    wk_up = sorted(universe, key=lambda c: c.get("price_change_percentage_7d_in_currency") or 0, reverse=True)[:5]

    # portfolio + watchlist coins ke alerts
    alerts = []
    holdings = []
    watch_syms = set()
    for chat_id in storage.all_chat_ids():
        ud = storage.load_json(f"user_{chat_id}.json", {})
        for sym, h in ud.get("portfolio", {}).items():
            coin = next((c for c in universe if c["id"] == h.get("id")
                         or c["symbol"].upper() == sym), None)
            if coin:
                pnl = (coin["current_price"] - h["buy"]) / h["buy"] * 100 if h.get("buy") else 0
                holdings.append({"sym": sym, "price": coin["current_price"],
                                 "buy": h["buy"], "qty": h.get("qty", 0), "pnl": pnl,
                                 "ch24": coin.get("price_change_percentage_24h_in_currency") or 0})
        for w in ud.get("watchlist", []):
            watch_syms.add(w["symbol"])

    # watchlist + portfolio coins ka quick RSI check sparkline se
    for c in universe:
        sym = (c.get("symbol") or "").upper()
        if sym in watch_syms or any(h["sym"] == sym for h in holdings):
            spark = (c.get("sparkline_in_7d") or {}).get("price") or []
            if len(spark) > 30:
                r = _rsi_quick(spark)
                ch24 = c.get("price_change_percentage_24h_in_currency") or 0
                if r >= 75:
                    alerts.append(f"⚠️ <b>{html.escape(c['name'])} ({sym})</b> overbought hai (RSI {r:.0f}) — profit booking socho")
                elif r <= 30 and (c.get("price_change_percentage_30d_in_currency") or 0) > 0:
                    alerts.append(f"💡 <b>{html.escape(c['name'])} ({sym})</b> dip pe hai (RSI {r:.0f}) — uptrend me dip buy ka chance")
                if ch24 <= -8:
                    alerts.append(f"🚨 <b>{sym}</b> 24h me {ch24:.1f}% gira hai — SL check karo")
                if ch24 >= 10:
                    alerts.append(f"🚀 <b>{sym}</b> aaj {ch24:.1f}% ud raha hai — trailing SL lagao")

    return {"mode": mode, "generated": time.strftime("%d %b %Y, %H:%M IST"),
            "fng": fng, "btc": btc, "eth": eth,
            "movers_up": movers_up, "movers_dn": movers_dn, "wk_up": wk_up,
            "holdings": holdings, "alerts": alerts[:8],
            "trending": trending[:6], "watch_syms": watch_syms}


def _rsi_quick(prices, period=14):
    """Sparkline (hourly) pe quick RSI."""
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [max(0, d) for d in deltas[-period * 3:]]
    losses = [max(0, -d) for d in deltas[-period * 3:]]
    if not gains or not losses:
        return 50.0
    avg_g = sum(gains) / len(gains)
    avg_l = sum(losses) / len(losses)
    if avg_l == 0:
        return 100.0
    return 100 - 100 / (1 + avg_g / avg_l)
