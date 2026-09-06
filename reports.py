"""Hinglish reports — Telegram HTML format me weekly/daily/single/portfolio."""
import html
import time

import analyzer


def _esc(s):
    return html.escape(str(s), quote=False)


VERDICT_EMOJI = {
    "STRONG BUY": "🚀", "BUY": "✅", "HOLD / WATCH": "⏳",
    "SELL": "📉", "AVOID / EXIT": "🛑",
}


def _coin_header(a):
    emo = VERDICT_EMOJI.get(a["verdict"], "•")
    return (f"<b>{emo} {_esc(a['name'])} ({a['symbol']})</b> "
            f"<i>[Score: {a['score']:.0f}/100]</i>\n"
            f"💰 Price: <b>{analyzer.fmt_price(a['price'])}</b> | "
            f"7d: {analyzer.fmt_pct(a['ch7'])} | 30d: {analyzer.fmt_pct(a['ch30'])}\n")


def _levels_block(a):
    lo, hi = a["entry"]
    return (
        f"├ 🎯 Entry zone: <b>{analyzer.fmt_price(lo)} – {analyzer.fmt_price(hi)}</b>\n"
        f"├ 📈 Target 1: <b>{analyzer.fmt_price(a['t1'])}</b> (+{(a['t1']/a['price']-1)*100:.0f}%)\n"
        f"├ 🚀 Target 2: <b>{analyzer.fmt_price(a['t2'])}</b> (+{(a['t2']/a['price']-1)*100:.0f}%)\n"
        f"├ 🛑 Stop-loss: <b>{analyzer.fmt_price(a['sl'])}</b> ({a['risk_pct']:.0f}% risk)\n"
        f"└ ⚖️ Risk:Reward = 1 : {a['rr']:.1f} | RSI: {a['rsi']:.0f} | ATR: {a['atr_pct']:.1f}%\n")


def _reasons_block(a):
    return "".join(f"   • {r}\n" for r in a["reasons"][:3])


def _market_overview(res):
    lines = ["📊 <b>MARKET OVERVIEW</b>"]
    btc, eth = res.get("btc"), res.get("eth")
    if btc:
        lines.append(f"• BTC: <b>{analyzer.fmt_price(btc['current_price'])}</b> "
                     f"(7d {analyzer.fmt_pct(btc.get('price_change_percentage_7d_in_currency'))})")
    if eth:
        lines.append(f"• ETH: <b>{analyzer.fmt_price(eth['current_price'])}</b> "
                     f"(7d {analyzer.fmt_pct(eth.get('price_change_percentage_7d_in_currency'))})")
    fng = res.get("fng")
    if fng:
        emo = {"Extreme Fear": "😱", "Fear": "😰", "Neutral": "😐",
               "Greed": "🤑", "Extreme Greed": "🔥"}.get(fng["label"], "•")
        lines.append(f"• Market mood: {emo} <b>{fng['label']}</b> ({fng['value']}/100)")
        if fng["value"] <= 25:
            lines.append("  └ 😱 Extreme Fear = long-term buyers ke liye achha zone hota hai")
        elif fng["value"] >= 75:
            lines.append("  └ 🔥 Extreme Greed = careful raho, profit booking ka time")
    if res.get("universe_count"):
        lines.append(f"• Scan kiye gaye: <b>{res['universe_count']}</b> coins "
                     f"({res['mode']} mode)")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# WEEKLY
# ---------------------------------------------------------------------------

def weekly_report(res):
    chunks = []
    head = ("📅 <b>WEEKLY CRYPTO ANALYSIS</b>\n"
            f"<i>{_esc(res['generated'])}</i>\n\n") + _market_overview(res)

    buys = res.get("buys") or []
    if buys:
        body = "🟢 <b>IS WEEK KE TOP BUY PICKS</b>\n\n"
        for i, a in enumerate(buys, 1):
            body += (f"<b>{i}.</b> " + _coin_header(a) + _levels_block(a)
                     + "  💡 <i>Kyun?</i>\n" + _reasons_block(a) + "\n")
        chunks.append(head + body if len(chunks) == 0 else body)
    else:
        body = ("🟡 <b>IS WEEK KOI STRONG BUY SETUP NAHI</b>\n"
                "Market abhi confuse hai — cash me rahana bhi position hai.\n\n")
        chunks.append(head + body if len(chunks) == 0 else body)

    holds = res.get("holds") or []
    if holds:
        body = "🟡 <b>HOLD / WATCH LIST</b>\n<i>In me potential hai, entry ka wait karo:</i>\n\n"
        for a in holds:
            body += (f"{VERDICT_EMOJI.get(a['verdict'],'•')} <b>{a['symbol']}</b> "
                     f"[{a['score']:.0f}] — {analyzer.fmt_price(a['price'])} "
                     f"(7d {analyzer.fmt_pct(a['ch7'])}, RSI {a['rsi']:.0f})\n")
        body += "\n"
        chunks.append(body)

    booked = res.get("book_profit") or []
    if booked:
        body = ("💰 <b>PROFIT BOOKING ZONE</b>\n<i>Strong coins jo bahut ud chuke hain — "
                "holding ho toh profit book karo, NAYA entry mat lo:</i>\n\n")
        for a in booked:
            body += (f"💸 <b>{_esc(a['name'])} ({a['symbol']})</b> [{a['score']:.0f}] — "
                     f"{analyzer.fmt_price(a['price'])} | RSI {a['rsi']:.0f} | "
                     f"7d {analyzer.fmt_pct(a['ch7'])}\n")
            for r in a["reasons"][:1]:
                body += f"   • {r}\n"
        body += "\n"
        chunks.append(body)

    sells = res.get("sells") or []
    if sells:
        body = "🔴 <b>SELL / AVOID KARO</b>\n<i>Weak technicals — portfolio me hai toh exit socho:</i>\n\n"
        for a in sells:
            body += (f"📉 <b>{_esc(a['name'])} ({a['symbol']})</b> [{a['score']:.0f}] — "
                     f"{analyzer.fmt_price(a['price'])} | 7d {analyzer.fmt_pct(a['ch7'])}\n")
            for r in a["reasons"][:2]:
                if "pullback" not in r and "trending" not in r.lower():
                    body += f"   • {r}\n"
        body += "\n"
        chunks.append(body)

    invest = res.get("invest") or []
    if invest:
        body = "💼 <b>INVESTMENT CORNER (long-term DCA view)</b>\n"
        for s, a in invest:
            body += (f"• <b>{a['symbol']}</b> — {s['verdict']} "
                     f"({s['score']:.0f}/100)\n")
            for r in s["reasons"][:2]:
                body += f"   • {r}\n"
        body += "\n<i>Long-term = weeks/months hold. DCA karo, all-in nahi.</i>\n\n"
        chunks.append(body)

    trending = res.get("trending") or []
    if trending:
        tnames = ", ".join(f"<b>{t['symbol']}</b>" for t in trending[:6])
        chunks.append("🔥 <b>TRENDING COINS</b>\n" + tnames +
                      "\n<i>(Trending = high volatility, chhote position me khelo)</i>\n")

    chunks.append("━━━━━━━━━━━━━━━\n⚠️ <i>Ye analysis sirf educational purpose ke liye hai, "
                  "financial advice nahi. Apna research zaroor karo (DYOR). Crypto volatile hai — "
                  "sirf utna invest karo jitna afford kar sakte ho.</i>")
    return _merge_chunks(chunks)


# ---------------------------------------------------------------------------
# DAILY
# ---------------------------------------------------------------------------

def daily_report(res):
    chunks = []
    head = ("☀️ <b>DAILY CRYPTO UPDATE</b>\n"
            f"<i>{_esc(res['generated'])}</i>\n\n") + _market_overview(res)

    alerts = res.get("alerts") or []
    body = ""
    # ---- PRO DESK (BTC/ETH/SOL professional view) ----
    pb = res.get("pro_brief") or []
    if pb:
        body += "🎓 <b>PRO DESK — BTC/ETH/SOL</b>\n"
        for p in pb:
            s_txt = (", ".join(analyzer.fmt_price(z) for z in p["sup"]) or "-")
            r_txt = (", ".join(analyzer.fmt_price(z) for z in p["res"]) or "-")
            body += (f"• <b>{p['sym']}</b> {p['bias']} ({p['pct']:.0f}% confluence, "
                     f"{p['conviction']}) | Structure: {p['structure']['desc']}\n"
                     f"  S: {s_txt} | R: {r_txt}\n")
        body += "\n"
    fm = res.get("forming") or []
    if fm:
        body += "⚡ <b>SETUP FORMING</b> (confirm hote hi signal aayega):\n"
        for f in fm:
            body += (f"• <b>{f['sym']} {f['side']}</b> — baaki: "
                     f"{', '.join(f['missing'])}\n")
        body += "\n"
    if alerts:
        body += "🔔 <b>AAPKE COINS KE ALERTS</b>\n" + "\n".join(alerts) + "\n\n"
    mu = res.get("movers_up") or []
    md = res.get("movers_dn") or []
    if mu or md:
        body += "📈 <b>AAJ KE TOP MOVERS (24h)</b>\n"
        for c in mu[:4]:
            body += (f"🟢 <b>{(c.get('symbol') or '').upper()}</b> "
                     f"{analyzer.fmt_pct(c.get('price_change_percentage_24h_in_currency'))} "
                     f"— {analyzer.fmt_price(c.get('current_price'))}\n")
        for c in md[:3]:
            body += (f"🔻 <b>{(c.get('symbol') or '').upper()}</b> "
                     f"{analyzer.fmt_pct(c.get('price_change_percentage_24h_in_currency'))} "
                     f"— {analyzer.fmt_price(c.get('current_price'))}\n")
        body += "\n"
    wk = res.get("wk_up") or []
    if wk:
        body += "💪 <b>7-DAY ME SABSE STRONG</b>\n"
        for c in wk[:5]:
            body += (f"• <b>{(c.get('symbol') or '').upper()}</b> "
                     f"{analyzer.fmt_pct(c.get('price_change_percentage_7d_in_currency'))} "
                     f"— <i>ye momentum carry kar raha hai</i>\n")
        body += "\n"
    trending = res.get("trending") or []
    if trending:
        body += "🔥 <b>TRENDING:</b> " + ", ".join(
            f"<b>{t['symbol']}</b>" for t in trending[:6]) + "\n\n"
    if not body.strip():
        body = "Aaj koi bada move nahi — market shaant hai. ☕\n\n"
    chunks.append(head + body)
    chunks.append("━━━━━━━━━━━━━━━\n⚠️ <i>Educational analysis, financial advice nahi. DYOR.</i>")
    return _merge_chunks(chunks)


# ---------------------------------------------------------------------------
# SINGLE COIN
# ---------------------------------------------------------------------------

def single_report(a, mode):
    emo = VERDICT_EMOJI.get(a["verdict"], "•")
    body = (f"🔬 <b>DEEP ANALYSIS</b> ({mode} mode)\n\n"
            + _coin_header(a)
            + f"📊 Rank: #{a['rank'] or '?'} | MCap: {_mcap_fmt(a['mcap'])}\n"
            + f"📈 200d: {analyzer.fmt_pct(a['ch200'])} | "
              f"30d high: {analyzer.fmt_price(a['hi30'])} | low: {analyzer.fmt_price(a['lo30'])}\n"
            + f"📉 30d high se: {a['dip_from_high']:.1f}% neeche\n\n"
            + "🧮 <b>TECHNICALS</b>\n"
            + f"├ RSI(14): <b>{a['rsi']:.0f}</b>"
            + (" (overbought!)" if a["rsi"] > 75 else " (oversold)" if a["rsi"] < 30 else "") + "\n"
            + f"├ SMA20: {analyzer.fmt_price(a['sma20'])} "
              f"({'✅ price upar' if a['sma20'] and a['price'] > a['sma20'] else '❌ price neeche'})\n"
            + f"├ SMA50: {analyzer.fmt_price(a['sma50'])} "
              f"({'✅ price upar' if a['sma50'] and a['price'] > a['sma50'] else '❌ price neeche'})\n"
            + f"├ MACD: {'✅ bullish' if (a['macd_hist'] or 0) > 0 else '❌ bearish'}\n"
            + f"└ Volatility (ATR): {a['atr_pct']:.1f}%\n\n"
            + f"🎯 <b>TRADE PLAN</b> ({emo} {a['verdict']})\n"
            + _levels_block(a)
            + "💡 <i>Reasoning:</i>\n" + _reasons_block(a)
            + "\n⚠️ <i>Educational analysis, financial advice nahi. DYOR.</i>")
    return [body] if len(body) <= 3900 else [body[:3900] + "…"]


# ---------------------------------------------------------------------------
# CHANNEL POSTS (captions 1024 char limit)
# ---------------------------------------------------------------------------

def trade_caption(a):
    """Signal ka compact caption — chart photo ke saath jata hai."""
    lo, hi = a["entry"]
    side = a.get("side", "LONG")
    kind = a.get("kind", "SPOT")
    if side == "SHORT":
        head = f"🔴 <b>{side} SIGNAL (Futures)</b>"
        levels = (f"💰 <b>Entry Zone: {analyzer.fmt_price(lo)} – {analyzer.fmt_price(hi)}</b>\n"
                  f"🎯 Target 1: <b>{analyzer.fmt_price(a['t1'])}</b> "
                  f"({(a['t1']/a['price']-1)*100:+.0f}%)\n"
                  f"🚀 Target 2: <b>{analyzer.fmt_price(a['t2'])}</b> "
                  f"({(a['t2']/a['price']-1)*100:+.0f}%)\n"
                  f"🛑 Stop-loss: <b>{analyzer.fmt_price(a['sl'])}</b> "
                  f"(+{a['risk_pct']:.0f}% upar)\n")
    else:
        head = "🚀 <b>NEW SIGNAL</b>" + (" (Futures)" if kind == "FUTURES" else "")
        levels = (f"💰 <b>Entry Zone: {analyzer.fmt_price(lo)} – {analyzer.fmt_price(hi)}</b>\n"
                  f"🎯 Target 1: <b>{analyzer.fmt_price(a['t1'])}</b> "
                  f"(+{(a['t1']/a['price']-1)*100:.0f}%)\n"
                  f"🚀 Target 2: <b>{analyzer.fmt_price(a['t2'])}</b> "
                  f"(+{(a['t2']/a['price']-1)*100:.0f}%)\n"
                  f"🛑 Stop-loss: <b>{analyzer.fmt_price(a['sl'])}</b> "
                  f"(-{a['risk_pct']:.0f}%)\n")
    lev_line = ""
    if a.get("lev"):
        lev_line = (f"⚡ Leverage: <b>{a['lev']}x</b> (isolated) | "
                    f"💥 Liq ~{analyzer.fmt_price(a['liq'])}\n")
    conf = f"\n🎖 Confidence: <b>{a['confidence']}</b>" if a.get("confidence") else ""
    return (f"{head}\n"
            f"{'🔴' if side == 'SHORT' else '🟢'} <b>{_esc(a['name'])} ({a['symbol']})</b>\n"
            f"📊 Score: {a['score']:.0f}/100 | RSI: {a['rsi']:.0f} | "
            f"7d: {analyzer.fmt_pct(a['ch7'])}\n\n"
            f"{levels}{lev_line}"
            f"⚖️ Risk:Reward 1 : {a['rr']:.1f}{conf}\n"
            f"📅 {time.strftime('%d %b %Y, %H:%M IST')}\n\n"
            f"⚠️ <i>Educational only, not financial advice. "
            f"{'Futures me liquidation risk hai — chhota position!' if kind == 'FUTURES' else 'DYOR.'}</i>")


EVENT_TEXT = {
    "T1_HIT": ("🎯 <b>TARGET 1 HIT!</b>",
               "💡 SL ab entry pe shift karo — ab ye risk-free trade hai!"),
    "CLOSED_TP2": ("🚀 <b>TARGET 2 HIT — SIGNAL CLOSED!</b>",
                   "💡 Full profit book! 🎉"),
    "CLOSED_SL": ("🛑 <b>STOP-LOSS HIT — SIGNAL CLOSED</b>",
                  "💡 Chhota loss = part of the game. Discipline hi asli edge hai."),
    "CLOSED_TIME": ("⏳ <b>SIGNAL CLOSED (30 din complete)</b>",
                    "💡 Time exit — position close karo, capital free karo."),
}


def signal_result_text(sig, event, pnl):
    title, note = EVENT_TEXT.get(event, ("📢 SIGNAL UPDATE", ""))
    side = sig.get("side", "LONG")
    kind = sig.get("kind", "SPOT")
    emo = "🟢" if pnl >= 0 else "🔴"
    tag = ""
    if kind == "FUTURES":
        lev = f" {sig['lev']}x" if sig.get("lev") else ""
        tag = f" [{side}{lev}]"
    return (f"{title}\n"
            f"{emo} <b>{_esc(sig['name'])} ({sig['sym']})</b>{tag} — "
            f"P&L: <b>{pnl:+.1f}%</b>\n"
            f"Entry: {analyzer.fmt_price(sig['entry'])} → "
            f"Now: {analyzer.fmt_price(sig['last_price'])}\n"
            f"{note}\n\n"
            f"⚠️ <i>Educational only, not financial advice.</i>")


def futures_report(longs, shorts, note=""):
    """Futures scan ka chat report."""
    lines = ["⚡ <b>FUTURES SCANNER</b>"]
    if note:
        lines.append(f"<i>Bade moves: {note}</i>")
    lines.append("")
    if longs:
        lines.append("🟢 <b>LONG SETUPS</b> (uptrend coins)")
        for a in longs:
            lines.append(
                f"• <b>{a['symbol']}</b> [{a['confidence']}] — "
                f"{analyzer.fmt_price(a['price'])} | {a['lev']}x | "
                f"Entry {analyzer.fmt_price(a['entry'][0])}–{analyzer.fmt_price(a['entry'][1])} | "
                f"T1 {analyzer.fmt_price(a['t1'])} | SL {analyzer.fmt_price(a['sl'])}")
        lines.append("")
    if shorts:
        lines.append("🔴 <b>SHORT SETUPS</b> (downtrend coins)")
        for a in shorts:
            lines.append(
                f"• <b>{a['symbol']}</b> [{a['confidence']}] — "
                f"{analyzer.fmt_price(a['price'])} | {a['lev']}x | "
                f"Entry {analyzer.fmt_price(a['entry'][0])}–{analyzer.fmt_price(a['entry'][1])} | "
                f"T1 {analyzer.fmt_price(a['t1'])} | SL {analyzer.fmt_price(a['sl'])}")
        lines.append("")
    if not longs and not shorts:
        lines.append("Abhi koi clean futures setup nahi mila — market "
                     "confuse hai. Scanner har ghanta check karta rahega ⏳\n")
    lines.append("⚠️ <i>Futures = leverage risk. Max 5x, isolated margin, "
                 "SL ke bina trade mat karo. Educational only.</i>")
    return "\n".join(lines)


def channel_overview(res):
    """Weekly overview post — channel pe text post ke liye."""
    lines = ["📅 <b>WEEKLY MARKET UPDATE</b>\n"]
    lines.append(_market_overview(res))
    booked = res.get("book_profit") or []
    if booked:
        lines.append("💰 <b>PROFIT BOOKING ZONE</b> <i>(naya entry mat lo):</i>")
        for a in booked[:4]:
            lines.append(f"• <b>{a['symbol']}</b> — RSI {a['rsi']:.0f}, "
                         f"7d {analyzer.fmt_pct(a['ch7'])}")
        lines.append("")
    sells = res.get("sells") or []
    if sells:
        lines.append("🔴 <b>AVOID / EXIT:</b> " +
                     ", ".join(f"<b>{a['symbol']}</b>" for a in sells[:4]))
        lines.append("")
    trending = res.get("trending") or []
    if trending:
        lines.append("🔥 <b>Trending:</b> " +
                     ", ".join(f"<b>{t['symbol']}</b>" for t in trending[:6]))
    lines.append("\n⚠️ <i>Educational only, not financial advice. DYOR.</i>")
    return "\n".join(lines)


def _mcap_fmt(m):
    if not m:
        return "?"
    if m >= 1e12:
        return f"${m/1e12:.2f}T"
    if m >= 1e9:
        return f"${m/1e9:.1f}B"
    return f"${m/1e6:.0f}M"


# ---------------------------------------------------------------------------
# PORTFOLIO
# ---------------------------------------------------------------------------

def portfolio_report(holdings, mode="aggressive"):
    """holdings: [{sym, price, buy, qty, pnl, id}] — analyzer se verdict ke saath."""
    if not holdings:
        return ["📦 Portfolio khali hai. Add karo:\n"
                "<code>/add BTC 0.05 65000</code>\n"
                "<i>(coin, quantity, buy price)</i>"]
    lines = ["📦 <b>TUMHARA PORTFOLIO</b>\n"]
    total_val = total_cost = 0.0
    for h in holdings:
        val = h["price"] * h["qty"]
        cost = h["buy"] * h["qty"]
        total_val += val
        total_cost += cost
        emo = "🟢" if h["pnl"] >= 0 else "🔴"
        advice = _holding_advice(h)
        lines.append(f"{emo} <b>{h['sym']}</b> — {h['qty']} × {analyzer.fmt_price(h['price'])} "
                     f"= {analyzer.fmt_price(val) if val >= 1 else '$' + format(val, '.2f')}\n"
                     f"   Buy: {analyzer.fmt_price(h['buy'])} | P&L: {analyzer.fmt_pct(h['pnl'])}\n"
                     f"   👉 {advice}\n")
    total_pnl = (total_val - total_cost) / total_cost * 100 if total_cost else 0
    emo = "🟢" if total_pnl >= 0 else "🔴"
    lines.append(f"\n💰 <b>TOTAL:</b> {analyzer.fmt_price(total_val)} | "
                 f"P&L: {emo} <b>{total_pnl:+.1f}%</b> "
                 f"({analyzer.fmt_price(abs(total_val - total_cost))})")
    lines.append("\n⚠️ <i>Educational, financial advice nahi. DYOR.</i>")
    return _merge_chunks(["\n".join(lines)])


def _holding_advice(h):
    pnl = h["pnl"]
    if pnl >= 25:
        return "Bahut profit ho gaya — 30-50% profit book karo, baaki trail karo"
    if pnl >= 12:
        return "Target zone ke paas — partial profit booking socho"
    if pnl <= -15:
        return "Deep red — agar thesis break hai toh exit, warna average-down sirf blue-chips me"
    if pnl <= -7:
        return "Stop-loss zone — agar support toota hai toh exit karo"
    return "Hold — trend dekho, SMA50 ke upar hai toh tension mat lo"


def _merge_chunks(chunks, limit=3900):
    """Chunks ko 4096 limit ke andar merge karo (line boundary pe split)."""
    out, cur = [], ""
    for c in chunks:
        if len(c) > limit:
            parts = _split_big(c, limit)
            for p in parts:
                out.append(p)
            continue
        if len(cur) + len(c) + 1 <= limit:
            cur = (cur + "\n" + c).strip()
        else:
            if cur:
                out.append(cur)
            cur = c
    if cur:
        out.append(cur)
    return out


def _split_big(text, limit):
    parts = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    if text:
        parts.append(text)
    return parts
