"""Futures signal engine — LONG/SHORT setups + leverage + liquidation + funding.

Futures me spot se alag risk hai (leverage = liquidation), isliye:
- Sirf LIQUID coins (mcap $50M+, volume $5M+) — manipulation se bachne ke liye
- Max leverage 5x (safety cap)
- SL hamesha liquidation se pehle (isolated margin approximation)
- Funding rate OKX se (free API)
"""
import threading
import time

import requests

import analyzer
import config

OKX_URL = "https://www.okx.com/api/v5/public/funding-rate"
_fund_cache = {}
_fund_lock = threading.Lock()

MAX_LEV = 5
MIN_SCORE_LONG = 55       # BUY threshold se aligned
MAX_SCORE_SHORT = 38


# ---------------------------------------------------------------------------
# Funding rate (OKX)
# ---------------------------------------------------------------------------

def fetch_funding(symbol):
    """OKX se funding rate (8h). symbol jaise 'BTC'. Fail -> None."""
    with _fund_lock:
        c = _fund_cache.get(symbol)
        if c and time.time() - c[1] < 1800:
            return c[0]
    try:
        rl = analyzer.rl
        rl.wait()
        r = requests.get(OKX_URL, params={"instId": f"{symbol.upper()}-USDT-SWAP"},
                         timeout=10)
        if r.status_code == 200:
            d = r.json().get("data", [{}])[0]
            rate = float(d.get("fundingRate", 0)) * 100
            out = {"rate": rate, "annualized": rate * 3 * 365}
            with _fund_lock:
                _fund_cache[symbol] = (out, time.time())
            return out
    except (requests.RequestException, ValueError, KeyError, IndexError):
        pass
    with _fund_lock:
        _fund_cache[symbol] = (None, time.time())
    return None


def funding_note(symbol):
    f = fetch_funding(symbol)
    if not f:
        return ""
    r = f["rate"]
    emo = "🟢" if abs(r) < 0.03 else ("🔥" if r > 0 else "🧊")
    side_hint = ""
    if r > 0.05:
        side_hint = " | longs crowded — caution"
    elif r < -0.05:
        side_hint = " | shorts crowded — squeeze risk"
    return f"\n💵 Funding: {r:+.4f}%/8h {emo}{side_hint}"


# ---------------------------------------------------------------------------
# Leverage + liquidation
# ---------------------------------------------------------------------------

def _leverage_for(risk_pct):
    """Volatility ke hisaab se safe leverage: SL liquidation se door rahe."""
    sl_frac = risk_pct / 100.0
    lev = int(0.80 / (sl_frac + 0.03))   # liq ~SL se aage
    return max(2, min(MAX_LEV, lev))


def _liq_price(entry, lev, side):
    mmr = 0.012  # approx maintenance margin
    if side == "LONG":
        return entry * (1 - 1 / lev + mmr)
    return entry * (1 + 1 / lev - mmr)


# ---------------------------------------------------------------------------
# Setup evaluation (analyzed list -> LONG/SHORT setups)
# ---------------------------------------------------------------------------

def _mk_setup(a, side):
    """deep_analyze result se futures setup banao (levels side ke hisaab se)."""
    px = a["price"]
    risk = a["risk_pct"] / 100.0
    lev = _leverage_for(a["risk_pct"])
    if side == "LONG":
        sl = px * (1 - risk)
        t1 = px * (1 + risk * 1.5)
        t2 = px * (1 + risk * 2.5)
        lo, hi = px * 0.99, px * 1.01
    else:
        sl = px * (1 + risk)
        t1 = px * (1 - risk * 1.5)
        t2 = px * (1 - risk * 2.5)
        lo, hi = px * 0.99, px * 1.01
    rr = risk * 1.5 / risk  # 1.5
    conf = "HIGH" if ((side == "LONG" and a["score"] >= 68) or
                      (side == "SHORT" and a["score"] <= 30)) else "MEDIUM"
    return dict(a, side=side, entry=(lo, hi), sl=sl, t1=t1, t2=t2,
                rr=rr, lev=lev, liq=_liq_price(px, lev, side),
                confidence=conf, verdict=f"FUTURES {side}",
                risk_pct=a["risk_pct"])


def evaluate_setups(analyzed):
    """Analyzed coins me se LONG + SHORT setups chhaanto."""
    longs, shorts = [], []
    for a in analyzed:
        mcap = a.get("mcap") or 0
        if mcap < 50_000_000:
            continue
        px = a["price"]
        s20, s50 = a.get("sma20"), a.get("sma50")
        macd_h = a.get("macd_hist") or 0
        rsi = a.get("rsi") or 50
        ch7, ch30 = a.get("ch7") or 0, a.get("ch30") or 0

        # ---- LONG setup: A+ (full confluence) ya A (relaxed) ----
        tier = None
        if (a["score"] >= MIN_SCORE_LONG and s20 and px > s20
                and macd_h > 0 and rsi < 74 and "parabolic" not in a.get("tags", [])):
            tier = "A+"
        elif (a["score"] >= 48 and s20 and px > s20
              and rsi < 78 and "parabolic" not in a.get("tags", [])):
            tier = "A"
        if tier:
            st = _mk_setup(a, "LONG")
            st["tier"] = tier
            st["conv"] = a["score"] + (10 if tier == "A+" else 0)
            longs.append(st)

        # ---- SHORT setup: A+ (full structure) ya A (relaxed) ----
        tier = None
        if (a["score"] <= MAX_SCORE_SHORT and s50 and px < s50
              and (s20 and s20 < s50 or not s20)
              and macd_h < 0 and ch7 <= -6 and ch30 <= -5
              and 30 <= rsi <= 68):
            tier = "A+"
        elif (a["score"] <= 45 and s50 and px < s50 and macd_h < 0):
            tier = "A"
        if tier:
            st = _mk_setup(a, "SHORT")
            st["tier"] = tier
            st["conv"] = 100 - a["score"] + (10 if tier == "A+" else 0)
            shorts.append(st)

    longs.sort(key=lambda x: x["score"], reverse=True)
    shorts.sort(key=lambda x: x["score"])
    return longs[:4], shorts[:3]


# ---------------------------------------------------------------------------
# Hourly quick scanner — naye moves pakdo (24/7 auto mode)
# ---------------------------------------------------------------------------

def quick_scan(mode="aggressive"):
    """Hourly run: bade moves detect karo -> deep analyze -> setups.

    Returns (setups, movers_note). Rate-limit friendly: markets 1 call
    (10min cache) + sirf trigger coins ka deep analysis (history cached).
    """
    markets = analyzer.fetch_markets(mode)
    if not markets:
        return [], ""
    universe = [c for c in analyzer.filter_universe(markets, mode)
                if (c.get("total_volume") or 0) >= 5_000_000
                and (c.get("market_cap") or 0) >= 50_000_000]

    movers = []
    for c in universe:
        ch1 = abs(c.get("price_change_percentage_1h_in_currency") or 0)
        ch24 = abs(c.get("price_change_percentage_24h_in_currency") or 0)
        if ch1 >= 1.2 or ch24 >= 4:
            movers.append((max(ch1, ch24 / 3), c))
    movers.sort(key=lambda x: x[0], reverse=True)
    candidates = [c for _, c in movers[:6]]
    have = {c["id"] for c in candidates}
    for cid in MAJOR_IDS:   # BTC/ETH/SOL hamesha scan me rakho
        if cid not in have:
            c = next((x for x in markets if x.get("id") == cid), None)
            if c:
                candidates.append(c)
                have.add(cid)

    setups = []
    for coin in candidates:
        hist = analyzer.fetch_history(coin["id"])
        if not hist:
            continue
        try:
            a = analyzer.deep_analyze(coin, hist, mode, frozenset())
            if a["score"] >= MIN_SCORE_LONG and "overbought" not in a["tags"] \
                    and "parabolic" not in a["tags"]:
                setups.append(_mk_setup(a, "LONG"))
            elif a["score"] <= MAX_SCORE_SHORT:
                l, s = evaluate_setups([a])
                setups += (l + s)
        except (KeyError, IndexError, ValueError, ZeroDivisionError):
            continue
    note = ", ".join(f"{c['symbol']} {(c.get('price_change_percentage_1h_in_currency') or 0):+.1f}%"
                     for _, c in movers[:3])
    return setups, note

# ---------------------------------------------------------------------------
# Majors watch — BTC/ETH/SOL ka futures scan (har ghante)
# ---------------------------------------------------------------------------

MAJOR_IDS = {"bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL"}


def majors_setups(mode="aggressive"):
    """BTC/ETH/SOL ka deep analysis -> LONG/SHORT setups (jab bhi bane).

    Returns (setups, analyzed_list)
    """
    markets = analyzer.fetch_markets(mode)
    setups, analyzed_all = [], []
    for cid, sym in MAJOR_IDS.items():
        coin = next((c for c in markets if c.get("id") == cid), None)
        if not coin:
            continue
        hist = analyzer.fetch_history(cid)
        if not hist:
            continue
        try:
            a = analyzer.deep_analyze(coin, hist, mode, frozenset())
            analyzed_all.append(a)
        except Exception:
            continue
    longs, shorts = evaluate_setups(analyzed_all)
    return longs + shorts, analyzed_all


def _best_side(a):
    """Coin ka best-side setup with tier (A+/A/B) + conviction score."""
    px = a["price"]
    s20, s50 = a.get("sma20"), a.get("sma50")
    macd_h = a.get("macd_hist") or 0
    score = a["score"]
    tags = a.get("tags", [])
    long_conv = short_conv = 0.0
    if score >= 55 and s20 and px > s20 and macd_h > 0 and "parabolic" not in tags:
        long_conv = score + 10.0                      # A+
    elif score >= 46 and s20 and px > s20:
        long_conv = float(score)                      # A
    elif score >= 30:
        long_conv = score * 0.6                       # B (watch)
    if score <= 38 and s50 and px < s50 and macd_h < 0:
        short_conv = (100 - score) + 10.0             # A+
    elif score <= 45 and s50 and px < s50:
        short_conv = 100.0 - score                    # A
    elif score <= 70:
        short_conv = (100 - score) * 0.6              # B (watch)
    if long_conv >= short_conv and long_conv >= 30:
        side, conv = "LONG", long_conv
    elif short_conv >= 30:
        side, conv = "SHORT", short_conv
    else:
        return None
    st = _mk_setup(a, side)
    st["tier"] = "A+" if conv >= 65 else ("A" if conv >= 46 else "B")
    st["conv"] = int(round(conv))
    return st


def best_setups(mode="aggressive", max_n=3):
    """GUARANTEED top opportunities: majors + movers + volume leaders.

    Kabhi khali nahi lautata (jab tak market data hai) — tier B watch tak.
    Har coin ka deep analysis (history cached, rate-limit safe).
    """
    markets = analyzer.fetch_markets(mode)
    if not markets:
        return []
    universe = [c for c in analyzer.filter_universe(markets, mode)
                if (c.get("total_volume") or 0) >= 5_000_000
                and (c.get("market_cap") or 0) >= 50_000_000]
    movers = []
    for c in universe:
        ch1 = abs(c.get("price_change_percentage_1h_in_currency") or 0)
        ch24 = abs(c.get("price_change_percentage_24h_in_currency") or 0)
        if ch1 >= 1.2 or ch24 >= 4:
            movers.append((max(ch1, ch24 / 3), c))
    movers.sort(key=lambda x: x[0], reverse=True)
    picked, ids = [], set()
    for _, c in movers[:6]:
        picked.append(c)
        ids.add(c["id"])
    for cid in MAJOR_IDS:
        if cid not in ids:
            c = next((x for x in markets if x.get("id") == cid), None)
            if c:
                picked.append(c)
                ids.add(cid)
    for c in sorted(universe, key=lambda x: x.get("total_volume") or 0,
                    reverse=True):
        if len(picked) >= 9:
            break
        if c["id"] not in ids:
            picked.append(c)
            ids.add(c["id"])
    setups = []
    for coin in picked[:9]:
        hist = analyzer.fetch_history(coin["id"])
        if not hist:
            continue
        try:
            a = analyzer.deep_analyze(coin, hist, mode, frozenset())
            st = _best_side(a)
            if st:
                setups.append(st)
        except (KeyError, IndexError, ValueError, ZeroDivisionError):
            continue
    setups.sort(key=lambda x: x.get("conv", 0), reverse=True)
    return setups[:max_n]
