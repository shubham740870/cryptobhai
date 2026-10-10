"""INVESTING PRO SYSTEM — monthly model portfolio + daily tracking.

Har mahine: NSE large-caps scan -> TOP-10 "Model Portfolio" (InvestingPro-style
cards: PRO score, fair value, upside, entry, SL, horizon).
Har din: holdings check -> HOLD / BOOK PROFIT / TRAIL SL / EXIT alert.
Har hafte: 1 stock ka DEEP RESEARCH card.
Har mahine: rebalance — naye ADD, weak REMOVE (score gir gaya ya SL hit).
"""
import json
import os
import time

import fundamentals
import masters_invest
import nse

PF_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "data", "model_portfolio.json")
# BUGFIX (v16.3c): pehle ye `nse.TICKERS[:60]` tha — v16.2 ke champion-4 lock ne
# universe 60→4 silently tod diya. Ab independent hardcoded NIFTY-60 large-cap list
# (Yahoo-live verified Oct-2026; TATAMOTORS/LTIM dead-tha isliye exclude).
UNIVERSE = [
    "RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS", "ITC", "LT",
    "KOTAKBANK", "AXISBANK", "SBIN", "BHARTIARTL", "M&M", "MARUTI", "TITAN",
    "SUNPHARMA", "NTPC", "POWERGRID", "TATASTEEL", "HCLTECH", "BAJFINANCE",
    "ULTRACEMCO", "ASIANPAINT", "NESTLEIND", "WIPRO", "TECHM", "JSWSTEEL",
    "ADANIENT", "ADANIPORTS", "COALINDIA", "GRASIM", "HINDUNILVR", "HINDALCO",
    "CIPLA", "DRREDDY", "DIVISLAB", "EICHERMOT", "BRITANNIA", "TATACONSUM",
    "INDUSINDBK", "APOLLOHOSP", "HEROMOTOCO", "BAJAJ-AUTO", "BAJAJFINSV",
    "SHRIRAMFIN", "SBILIFE", "HDFCLIFE", "BPCL", "ONGC", "BEL", "TRENT",
    "JIOFIN", "TVSMOTOR", "VEDL", "DLF", "HAL", "SIEMENS", "PIDILITIND",
    "PFC", "LICI", "ZYDUSLIFE",
]
UNIVERSE = list(dict.fromkeys(UNIVERSE))   # dedupe, order preserve
TOP_N = 10
NOTIONAL = 10000   # ₹ per pick (simulated track — 5y methodology: +96% vs NIFTY +27%)


def _fmt(x):
    try:
        return f"₹{x:,.0f}"
    except (TypeError, ValueError):
        return str(x)


def _load_pf():
    try:
        return json.load(open(PF_FILE))
    except (OSError, ValueError):
        return {"month": "", "holdings": []}


def _save_pf(pf):
    try:
        json.dump(pf, open(PF_FILE, "w"), indent=1)
    except OSError:
        pass


def scan_all(max_n=60):
    """Universe score karo -> [(pro, sym, px, fund, ta, parts, extras)] sorted."""
    out = []
    for sym in UNIVERSE[:max_n]:
        ta = nse.fetch_stock(sym)
        if not ta or ta.get("price", 0) <= 0:
            continue
        fund = fundamentals.get_fundamentals(sym)
        if not fund or not fund.get("pe"):
            continue
        try:
            pro, parts, extras = masters_invest.score_stock(ta["price"], fund, ta)
            out.append((pro, sym, ta["price"], fund, ta, parts, extras))
        except (TypeError, ValueError, KeyError, ZeroDivisionError):
            pass
        time.sleep(0.35)   # BUGFIX: continue pe sleep skip ho raha tha — ab har symbol ke baad pace
    out.sort(key=lambda x: x[0], reverse=True)
    return out


def _pick_card(pro, sym, px, fund, ta, parts, extras):
    verdict, stars = masters_invest.rating(pro)
    return (f"{'🥇' if pro >= 75 else '⭐'} <b>{sym}</b> — PRO {pro}/100 "
            f"{stars} <b>{verdict}</b>\n"
            f"   ₹{px:,.0f} | V{parts['value']} Q{parts['quality']} "
            f"G{parts['growth']} M{parts['momentum']} S{parts['safety']}\n"
            f"   PE {extras['pe'] or '—'} · ROE {extras['roe']}% · "
            f"PEG {extras['peg'] or '—'} · D/E {extras['de']:.0f}%\n"
            f"   🎯 Analyst: {_fmt(extras['target'])} "
            f"(<b>{extras['upside']:+.0f}%</b>) | Entry {_fmt(px*0.97)}-"
            f"{_fmt(px*1.01)} | SL {_fmt(px*0.90)}")


def monthly_rebalance(post_fn, dry=False):
    """Mahine ki scan: TOP-10 picks + purane holdings review (ADD/REMOVE/HOLD)."""
    results = scan_all()
    if not results:
        return "⚠️ NSE scan fail — data nahi mila."
    month = time.strftime("%Y-%m")
    pf = _load_pf()
    old = {h["sym"]: h for h in pf.get("holdings", [])}
    top_syms = [sym for _, sym, *_ in results[:TOP_N]]
    top_map = {sym: row for row in results for sym in [row[1]]}

    lines = [f"📊 <b>MONTHLY MODEL PORTFOLIO — {time.strftime('%b %Y')}</b>\n"
             f"<i>InvestingPro-style: fundamentals + 7 masters frameworks</i>\n"]
    adds, removes, keeps = [], [], []
    for rank, row in enumerate(results[:TOP_N], 1):
        pro, sym, px, fund, ta, parts, extras = row
        if sym not in old:
            adds.append(sym)
        lines.append(f"<b>#{rank}</b> " + _pick_card(*row) + "\n")
    # removals: purane holdings jo ab top-30 me bhi nahi
    ranked = {sym: i for i, (_, sym, *_) in enumerate(results)}
    for sym, h in old.items():
        r = ranked.get(sym, 999)
        if r >= 30 and sym not in top_syms:
            removes.append(sym)
        else:
            keeps.append(sym)
    # persist new holdings (add-only; remove sirf report me suggest, exit daily-check me)
    new_hold = []
    for sym in top_syms:
        row = top_map[sym]
        pro, _, px, _, _, parts, extras = row
        if sym in old:
            h = old[sym]
            if not h.get("qty"):            # retro-fit: purane picks ko bhi ₹-track do
                h["qty"] = round(NOTIONAL / px, 4) if px else 0
                h["buy"] = px
            new_hold.append(h)
        else:
            new_hold.append(dict(sym=sym, entry=px, stop=px * 0.90,
                                 target=extras.get("target") or px * 1.25,
                                 score=pro, added=month,
                                 qty=round(NOTIONAL / px, 4) if px else 0, buy=px))
    # BUGFIX (v16.3c): keeps (rank<30, top-10 ke bahar) pehle pf se SILENTLY DROP
    # ho rahe the — ₹-track/history loss. Unhe track karte rehna hai jab tak
    # daily-check unhe exit na kare ya monthly report REMOVE suggest na kare.
    in_new = {h["sym"] for h in new_hold}
    for sym, h in old.items():
        if sym not in in_new and ranked.get(sym, 999) < 30:
            new_hold.append(h)
    pf = {"month": month, "holdings": new_hold}
    _save_pf(pf)

    if adds:
        lines.append("🟢 <b>ADD karo</b>: " + ", ".join(adds))
    if removes:
        lines.append("🔴 <b>REMOVE/Exit zone</b>: " + ", ".join(removes)
                     + " <i>(thesis weak / ranking gira)</i>")
    if keeps:
        lines.append(f"⚪ <b>HOLD</b>: {len(keeps)} positions tracking me")
    lines.append("\n<i>Har din status update milega · har hafte 1 deep research · "
                 "monthly rebalance · Educational, DYOR</i>")
    txt = "\n".join(lines)
    if not dry:
        post_fn(txt)
    return txt


def daily_check(post_fn):
    """Har din holdings check -> HOLD/PROFIT/EXIT alerts (InvestingPro alerts)."""
    pf = _load_pf()
    holds = pf.get("holdings", [])
    if not holds:
        return None
    lines = ["📈 <b>MODEL PORTFOLIO — DAILY CHECK</b>"]
    tot = 0.0
    actions = []
    for h in holds:
        # results-week alert (binary event discipline)
        try:
            import sentiment as _sent
            ei = _sent.earnings_date(h["sym"], "NSE")
            if ei:
                import datetime as _dt
                ed = _dt.date.fromisoformat(ei[:10])
                din = (ed - _dt.date.today()).days
                if 0 <= din <= 7:
                    lines.append(f"\U000026a0\ufe0f <b>{h['sym']}</b>: results "
                                 f"{ei} ({din} din) \u2014 event risk, size "
                                 "review karo!")
        except Exception:
            pass
        ta = nse.fetch_stock(h["sym"], ttl=1800)
        if not ta:
            continue
        px = ta["price"]
        entry = h.get("entry") or px
        stop = h.get("stop") or entry * 0.90
        target = h.get("target") or entry * 1.25
        pnl = (px / entry - 1) * 100
        tot += pnl
        act, emo = "HOLD", "⚪"
        if px <= stop:
            act, emo = "🛑 EXIT — SL broke", "🔴"
        elif pnl >= 25:
            act, emo = "🎯 BOOK 50% profit", "🟢"
        elif pnl >= 12:
            act, emo = "🔒 SL trail karo entry pe (risk-free)", "🟡"
        if act != "HOLD":
            h["stop"] = entry if pnl >= 12 else h.get("stop")
            actions.append(f"{emo} <b>{h['sym']}</b> {pnl:+.1f}% → {act}")
        lines.append(f"{emo} <b>{h['sym']}</b> {_fmt(px)} ({pnl:+.1f}%) — {act}")
    _save_pf(pf)
    lines.append(f"\n💼 <b>Portfolio avg P&L</b>: {tot / max(len(holds), 1):+.1f}% "
                 f"({len(holds)} stocks) · #NSE #Investing #LongTerm")
    txt = "\n".join(lines)
    post_fn(txt)
    return txt


def weekly_deep_dive(post_fn):
    """Hafte ka best-scoring stock — full research card."""
    results = scan_all(max_n=25)
    if not results:
        return None
    pro, sym, px, fund, ta, parts, extras = results[0]
    card = masters_invest.research_card(sym, px, fund, ta, pro, parts, extras)
    txt = ("📚 <b>WEEKLY DEEP RESEARCH</b> — Investment Masters Series\n\n"
           + card + "\n\n#Research #" + sym.replace("&", "") + " #NSE #Investing")
    post_fn(txt)
    return txt


def status():
    """Current model portfolio card (/invest command)."""
    pf = _load_pf()
    holds = pf.get("holdings", [])
    if not holds:
        return ("📊 Model portfolio abhi khali hai — pehla monthly scan "
                "Actions pe chalta hi portfolio ban jayega.")
    lines = [f"📊 <b>MODEL PORTFOLIO</b> ({pf.get('month', '?')}) — "
             f"{len(holds)} stocks\n"]
    tot = 0.0; tot_rs = 0.0; has_qty = any(h.get("qty") for h in holds)
    for h in holds:
        ta = nse.fetch_stock(h["sym"], ttl=1800)
        px = ta["price"] if ta else (h.get("entry") or 0)
        pnl = (px / h["entry"] - 1) * 100 if h.get("entry") and px else 0
        tot += pnl
        rs = 0.0
        if h.get("qty") and px:
            rs = h["qty"] * (px - (h.get("buy") or h["entry"]))
            tot_rs += rs
        emo = "🟢" if pnl >= 0 else "🔴"
        extra = f" | ₹{rs:+,.0f}" if has_qty else ""
        lines.append(f"{emo} <b>{h['sym']}</b> {fmt_inr(px)} "
                     f"({pnl:+.1f}%){extra} | SL {fmt_inr(h.get('stop', 0))} | "
                     f"TP {fmt_inr(h.get('target', 0))} | PRO {h.get('score', '?')}")
    if has_qty:
        alloc = sum(h.get("qty", 0) * (h.get("buy") or h.get("entry") or 0) for h in holds)
        lines.append(f"\n💼 <b>Avg P&L</b>: {tot / max(len(holds), 1):+.1f}% | "
                     f"₹-track: {fmt_inr(alloc)} → {fmt_inr(alloc + tot_rs)} "
                     f"({tot_rs:+,.0f})")
    else:
        lines.append(f"\n💼 <b>Avg P&L</b>: {tot / max(len(holds), 1):+.1f}% | "
                     f"Added: {pf.get('month')}")
    return "\n".join(lines)


def fmt_inr(x):
    try:
        return f"₹{x:,.0f}"
    except (TypeError, ValueError):
        return str(x)
