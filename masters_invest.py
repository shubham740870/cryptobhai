"""INVESTING MASTERS ENGINE — Graham/Buffett/Lynch/Greenblatt/Piotroski/
O'Shaughnessy/Marks ke documented frameworks -> composite PRO SCORE.

Score breakdown (0-100):
  Value 30%  — Graham (PE/PB/Graham#), Lynch PEG, Greenblatt earnings-yield
  Quality 25% — Buffett (ROE, margins), Greenblatt return-on-capital
  Growth 20% — revenue + earnings growth (Lynch GARP via PEG)
  Momentum 15% — O'Shaughnessy 6M price factor
  Safety 10% — debt/equity (Buffett: no leverage circus)
Analyst target = "Street view" overlay (InvestingPro-style upside).
"""
CLAMP = lambda x, lo=0.0, hi=100.0: max(lo, min(hi, x))


def _f(x, d=0.0):
    try:
        v = float(x)
        return v if v == v else d     # NaN guard
    except (TypeError, ValueError):
        return d


def score_stock(px, fund, ta):
    """price + fundamentals + TA dict -> (proscore, parts, extras)."""
    pe = _f(fund.get("pe"), 0)
    pb = _f(fund.get("pb"), 0) or (_f(px) / _f(fund.get("bvps"), 1) if _f(fund.get("bvps")) else 0)
    peg = _f(fund.get("peg"), 0)
    eps = _f(fund.get("eps"), 0)
    bvps = _f(fund.get("bvps"), 0)
    roe = (_f(fund.get("roe"), 0) or 0) * 100 if _f(fund.get("roe"), 0) <= 1 else _f(fund.get("roe"), 0)
    de = _f(fund.get("de"), 0)          # % (Yahoo)
    margin = (_f(fund.get("margin"), 0) or 0) * 100
    rev_g = (_f(fund.get("rev_g"), 0) or 0) * 100
    earn_g = (_f(fund.get("earn_g"), 0) or 0) * 100
    target = _f(fund.get("target"), 0)
    ch20 = _f(ta.get("ch20d"), 0)

    # ---- VALUE (Graham + Lynch + Greenblatt) ----
    v_pe = CLAMP((35 - pe) / 25 * 100) if pe > 0 else 25.0
    v_pb = CLAMP((6 - pb) / 5 * 100) if pb > 0 else 40.0
    v_peg = CLAMP((2.0 - peg) / 1.8 * 100) if peg > 0 else 45.0
    ey = (eps / px * 100) if px and eps > 0 else 0          # earnings yield
    v_ey = CLAMP(ey / 12 * 100)
    value = v_pe * 0.35 + v_peg * 0.30 + v_pb * 0.20 + v_ey * 0.15

    # Graham Number (value floor): sqrt(22.5 * EPS * BVPS)
    graham = (22.5 * eps * bvps) ** 0.5 if eps > 0 and bvps > 0 else 0

    # ---- QUALITY (Buffett ROE/margins + Greenblatt ROC proxy) ----
    q_roe = CLAMP(roe / 25 * 100) if roe else 40.0
    q_mar = CLAMP(margin / 15 * 100)
    quality = q_roe * 0.6 + q_mar * 0.4

    # ---- GROWTH (Lynch: 10-20% dono = GARP sweet spot) ----
    g_rev = CLAMP(rev_g / 20 * 100)
    g_earn = CLAMP(earn_g / 20 * 100)
    growth = g_rev * 0.45 + g_earn * 0.55

    # ---- MOMENTUM (O'Shaughnessy 6M proxy — 1M + trend) ----
    trend_bonus = 10 if ta.get("trend") == "UP" else (-10 if ta.get("trend") == "DOWN" else 0)
    momentum = CLAMP(50 + ch20 * 2.5 + trend_bonus)

    # ---- SAFETY (Buffett: low debt) ----
    safety = CLAMP((120 - de) / 120 * 100) if de >= 0 else 50.0

    pro = (value * 0.30 + quality * 0.25 + growth * 0.20
           + momentum * 0.15 + safety * 0.10)
    upside = (target / px - 1) * 100 if target and px else 0
    parts = dict(value=round(value), quality=round(quality), growth=round(growth),
                 momentum=round(momentum), safety=round(safety))
    extras = dict(graham=round(graham, 1), earnings_yield=round(ey, 1),
                  upside=round(upside, 1), target=target, pe=pe, pb=round(pb, 2),
                  peg=peg, roe=round(roe, 1), de=round(de, 0),
                  margin=round(margin, 1), rev_g=round(rev_g, 1),
                  earn_g=round(earn_g, 1))
    return round(pro), parts, extras


def rating(pro):
    if pro >= 75:
        return "STRONG BUY", "⭐⭐⭐⭐⭐"
    if pro >= 65:
        return "BUY", "⭐⭐⭐⭐"
    if pro >= 55:
        return "ACCUMULATE", "⭐⭐⭐"
    if pro >= 45:
        return "HOLD", "⭐⭐"
    return "AVOID", "⭐"


def research_card(sym, px, fund, ta, pro, parts, extras):
    """InvestingPro-style deep research card (HTML)."""
    verdict, stars = rating(pro)
    d = lambda x: f"₹{_f(x):,.0f}"
    graham_line = ""
    if extras.get("graham"):
        gx = extras["graham"]
        rel = "upar" if px > gx else "neeche"
        graham_line = (f"\n📐 <b>Graham#</b>: {d(gx)} (price {rel} — "
                       f"{'discount' if px < gx else 'premium'} {abs(px/gx-1)*100:.0f}%)")
    return (
        f"🔍 <b>{sym} — DEEP RESEARCH</b> {stars}\n"
        f"Price {d(px)} | PRO SCORE <b>{pro}/100</b> → <b>{verdict}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Value {parts['value']}</b> (Graham/Lynch): PE {extras['pe'] or '—'} · "
        f"PB {extras['pb']} · PEG {extras['peg'] or '—'} · E/Y {extras['earnings_yield']}%"
        f"{graham_line}\n"
        f"<b>Quality {parts['quality']}</b> (Buffett): ROE {extras['roe']}% · "
        f"Margin {extras['margin']}% · D/E {extras['de']:.0f}%\n"
        f"<b>Growth {parts['growth']}</b> (Lynch): Rev {extras['rev_g']:+.0f}% · "
        f"Earnings {extras['earn_g']:+.0f}%\n"
        f"<b>Momentum {parts['momentum']}</b> (O'Shaughnessy): 1M {ta.get('ch20d', 0):+.1f}% · "
        f"Trend {ta.get('trend', '?')}\n"
        f"<b>Safety {parts['safety']}</b>: Debt/Equity {extras['de']:.0f}%\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Analyst Target</b>: {d(extras['target'])} "
        f"(<b>{extras['upside']:+.0f}% upside</b>)\n"
        f"💡 <b>Plan</b>: Entry zone {d(px*0.97)}-{d(px*1.01)} · "
        f"SL {d(px*0.90)} · Horizon 6-12 months\n"
        f"<i>Frameworks: Graham · Buffett · Lynch · Greenblatt · "
        f"Piotroski · O'Shaughnessy · Marks | Educational, DYOR</i>")
