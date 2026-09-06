"""Professional trader & investor analysis layer.

Skills (jo real desk traders/investors use karte hain):
- Market structure: swing highs/lows se HH/HL (uptrend) vs LH/LL (downtrend)
- Multi-timeframe confluence: daily trend + short-term (7d hourly) bias
- Volume confirmation: recent volume vs 30d average
- Key S/R proximity: support/resistance zones ke paas entry quality
- Risk management: position sizing (fixed % risk), R-multiples, invalidation
- Investment scoring: long-term DCA view (trend + depth + rank + consistency)
"""
import math

import charts  # _sr_zones reuse (charts imports sirf config+indicators — no cycle)
from indicators import resample_daily, sma


# ---------------------------------------------------------------------------
# Market structure — swing analysis
# ---------------------------------------------------------------------------

def market_structure(highs, lows, lookback=60):
    hs, ls = highs[-lookback:], lows[-lookback:]
    w = 2
    swing_highs, swing_lows = [], []
    for i in range(w, len(hs) - w):
        if hs[i] >= max(hs[i - w:i + w + 1]):
            swing_highs.append((i, hs[i]))
        if ls[i] <= min(ls[i - w:i + w + 1]):
            swing_lows.append((i, ls[i]))

    def trend_of(swings, name):
        if len(swings) < 2:
            return None
        (i1, v1), (i2, v2) = swings[-2], swings[-1]
        return v2 > v1  # latest swing higher than previous?

    hh = trend_of(swing_highs, "high")
    hl = trend_of(swing_lows, "low")

    if hh is True and hl is not False:
        trend, desc = "uptrend", "Higher Highs + Higher Lows (HH/HL)"
    elif hh is False and hl is not True:
        trend, desc = "downtrend", "Lower Highs + Lower Lows (LH/LL)"
    else:
        trend, desc = "range", "Mixed swings — consolidation/range"

    last_sh = swing_highs[-1][1] if swing_highs else None
    last_sl = swing_lows[-1][1] if swing_lows else None
    return {"trend": trend, "desc": desc,
            "last_swing_high": last_sh, "last_swing_low": last_sl}


# ---------------------------------------------------------------------------
# Multi-timeframe bias
# ---------------------------------------------------------------------------

def mtf_bias(a, hist):
    """Daily bias (SMA20/50) + short-term bias (7d hourly SMA24 vs SMA72)."""
    daily = "bullish" if (a["sma20"] and a["price"] > a["sma20"]
                          and a["sma50"] and a["sma20"] > a["sma50"]) else \
        "bearish" if (a["sma50"] and a["price"] < a["sma50"]) else "neutral"

    prices = hist.get("prices") or []
    hourly = [p for _, p in prices[-24 * 7:]]
    short = "neutral"
    if len(hourly) > 72:
        s24 = sum(hourly[-24:]) / 24
        s72 = sum(hourly[-72:]) / 72
        short = "bullish" if s24 > s72 else "bearish"

    if daily == "bullish" and short == "bullish":
        aligned, label = True, "Bullish (daily + short-term aligned)"
    elif daily == "bearish" and short == "bearish":
        aligned, label = True, "Bearish (daily + short-term aligned)"
    else:
        aligned, label = False, f"Mixed (daily {daily}, short-term {short})"
    return {"daily": daily, "short": short, "aligned": aligned, "label": label}


# ---------------------------------------------------------------------------
# Volume confirmation
# ---------------------------------------------------------------------------

def volume_check(hist):
    vols = [v for _, v in hist.get("total_volumes") or []]
    if len(vols) < 200:
        return {"ratio": 1.0, "label": "normal"}
    recent = sum(vols[-10:]) / 10          # ~last 10 hours avg
    base = sum(vols[-220:-30]) / 190        # ~30d avg
    ratio = recent / base if base else 1.0
    label = "rising" if ratio >= 1.15 else "falling" if ratio <= 0.75 else "normal"
    return {"ratio": ratio, "label": label}


# ---------------------------------------------------------------------------
# Confluence checklist — pro verdict
# ---------------------------------------------------------------------------

def confluence(a, hist):
    ms = market_structure(a.get("_highs") or [], a.get("_lows") or [])
    mtf = mtf_bias(a, hist)
    vol = volume_check(hist)
    macd_ok = (a.get("macd_hist") or 0) > 0
    rsi_ok = 30 <= (a.get("rsi") or 50) <= 72
    dip = a.get("dip_from_high") or 0
    pullback_ok = 2 <= dip <= 14

    checks = [
        ("Daily trend (SMA20>50, price>SMA20)",
         bool(a["sma20"] and a["sma50"] and a["price"] > a["sma20"] and a["sma20"] > a["sma50"])),
        ("Market structure HH/HL", ms["trend"] == "uptrend"),
        ("MACD momentum positive", macd_ok),
        ("Short-term bias aligned", mtf["aligned"] and mtf["daily"] != "neutral"),
        ("Volume confirmation", vol["ratio"] >= 1.05),
        ("RSI healthy (30-72)", rsi_ok),
        ("Pullback entry zone (2-14% from high)", pullback_ok),
    ]
    met = sum(1 for _, ok in checks if ok)
    pct = met / len(checks) * 100
    if pct >= 85:
        conviction = "HIGH"
    elif pct >= 70:
        conviction = "MEDIUM-HIGH"
    elif pct >= 55:
        conviction = "MEDIUM"
    else:
        conviction = "LOW"

    bull_votes = int(pct >= 55) and sum(1 for _, ok in checks if ok)
    bias = "BULLISH" if pct >= 55 else "BEARISH" if pct <= 40 else "NEUTRAL"

    return {"checks": checks, "met": met, "pct": pct, "conviction": conviction,
            "bias": bias, "structure": ms, "mtf": mtf, "volume": vol}


# ---------------------------------------------------------------------------
# Setup forming (early alert) — sab conditions complete hone se pehle
# ---------------------------------------------------------------------------

def setup_forming(a):
    """LONG setup ban raha hai? (conditions 60%+ complete, par incomplete)"""
    missing = []
    if not (a["sma20"] and a["price"] > a["sma20"]):
        missing.append("price>SMA20")
    if not (a["sma50"] and a["sma20"] and a["sma20"] > a["sma50"]):
        missing.append("SMA20>SMA50")
    if not ((a.get("macd_hist") or 0) > 0):
        missing.append("MACD flip")
    if (a.get("rsi") or 50) >= 75:
        missing.append("RSI cool-down")
    if "parabolic" in (a.get("tags") or []):
        missing.append("parabolic cool-off")

    total = 5
    met = total - len(missing)
    if met >= 3 and len(missing) <= 2 and (a.get("score") or 0) >= 48:
        return True, missing
    return False, missing


# ---------------------------------------------------------------------------
# Investment view (long-term / DCA)
# ---------------------------------------------------------------------------

def investment_score(a):
    score = 0.0
    reasons = []
    ch200 = a.get("ch200") or 0
    if ch200 > 0:
        score += 25
        reasons.append(f"200d trend positive ({ch200:+.0f}%)")
    else:
        reasons.append("200d trend abhi negative")
    if a.get("sma50") and a["price"] > a["sma50"]:
        score += 15
        reasons.append("price SMA50 ke upar (structure strong)")
    rank = a.get("rank") or 999
    if rank <= 20:
        score += 20
        reasons.append(f"Top-20 coin (rank #{rank})")
    elif rank <= 50:
        score += 12
        reasons.append(f"Top-50 coin (rank #{rank})")
    elif rank <= 100:
        score += 8
        reasons.append(f"Top-100 coin (rank #{rank})")
    # ATH distance — deep discount on quality = opportunity, near ATH = strength
    ath_dist = abs(a.get("_ath_dist") or 0)
    if 50 <= ath_dist <= 85:
        score += 15
        reasons.append(f"ATH se {ath_dist:.0f}% neeche — discount zone")
    elif ath_dist < 20:
        score += 10
        reasons.append("ATH ke paas — strength mode")
    if (a.get("ch30") or 0) > -20:
        score += 10
    if (a.get("vol_mcap") or 0) > 0.03:
        score += 10
        reasons.append("liquidity healthy")
    if (a.get("dip_from_high") or 100) <= 15:
        score += 5

    score = max(0, min(100, score))
    if score >= 75:
        verdict = "ACCUMULATE / DCA ZONE"
    elif score >= 60:
        verdict = "HOLD / GRADUAL BUY"
    elif score >= 45:
        verdict = "WATCH"
    else:
        verdict = "AVOID (long-term)"
    return {"score": score, "verdict": verdict, "reasons": reasons}


# ---------------------------------------------------------------------------
# Position sizing — risk management
# ---------------------------------------------------------------------------

def position_size(capital_usd=1000, risk_pct=2.0, a=None):
    entry = (a["entry"][0] + a["entry"][1]) / 2
    risk_per_unit = abs(entry - a["sl"])
    if not risk_per_unit:
        return None
    risk_amt = capital_usd * risk_pct / 100
    qty = risk_amt / risk_per_unit
    return {"capital": capital_usd, "risk_pct": risk_pct,
            "risk_amt": risk_amt, "qty": qty, "entry": entry,
            "notional": qty * entry,
            "lev": a.get("lev"),
            "margin": (qty * entry / a["lev"]) if a.get("lev") else qty * entry}


# ---------------------------------------------------------------------------
# Professional report (chat ke liye)
# ---------------------------------------------------------------------------

def professional_report(a, hist):
    import analyzer
    highs_lows = _hl_from_hist(hist)
    a2 = dict(a, _highs=highs_lows[0], _lows=highs_lows[1],
              _ath_dist=abs(a.get("_ath_dist") or 0))
    conf = confluence(a2, hist)
    ms, mtf, vol = conf["structure"], conf["mtf"], conf["volume"]

    lines = ["🎓 <b>PRO DESK ANALYSIS</b>",
             f"<b>{a['symbol']}</b> — Bias: <b>{conf['bias']}</b> | "
             f"Conviction: <b>{conf['conviction']}</b> ({conf['met']}/{len(conf['checks'])})",
             ""]
    lines.append(f"📐 Structure: {ms['desc']}")
    lines.append(f"⏱ Timeframes: {mtf['label']}")
    lines.append(f"📊 Volume: {vol['label']} ({vol['ratio']:.2f}x avg)")
    sup, res = charts._sr_zones(highs_lows[0], highs_lows[1], a["price"])
    if sup:
        lines.append(f"🟦 Support: " + ", ".join(analyzer.fmt_price(z) for z in sup))
    if res:
        lines.append(f"🟧 Resistance: " + ", ".join(analyzer.fmt_price(z) for z in res))
    lines.append("")
    lines.append("<b>CONFLUENCE CHECKLIST</b>")
    for name, ok in conf["checks"]:
        lines.append(f"{'✅' if ok else '❌'} {name}")
    lines.append("")
    lines.append(f"🎯 Trade plan: Entry {analyzer.fmt_price(a['entry'][0])}-"
                 f"{analyzer.fmt_price(a['entry'][1])} | T1 {analyzer.fmt_price(a['t1'])} "
                 f"| T2 {analyzer.fmt_price(a['t2'])} | SL {analyzer.fmt_price(a['sl'])}")
    lines.append(f"🧮 Position size (example): $1000 capital, 2% risk → "
                 f"<b>${(position_size(1000, 2, a) or {}).get('risk_amt', 0):.0f} risk</b>, "
                 f"qty ≈ {(position_size(1000, 2, a) or {}).get('qty', 0):.4g}")
    lines.append("")
    inv = investment_score(a2)
    lines.append(f"💼 <b>INVESTMENT VIEW:</b> {inv['verdict']} ({inv['score']:.0f}/100)")
    for r in inv["reasons"][:3]:
        lines.append(f"   • {r}")
    lines.append("")
    lines.append("⚠️ <i>Educational only — not financial advice. DYOR.</i>")
    return "\n".join(lines)


def _hl_from_hist(hist):
    prices = hist.get("prices") or []
    _, _, highs, lows, _c = resample_daily(prices)
    return highs[-70:], lows[-70:]
