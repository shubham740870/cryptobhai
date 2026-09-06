"""Trading Journal — Google Sheet integration (READ).

Kaise kaam karta hai:
1. Tum ek Google Sheet banate ho (template niche README me)
2. Sheet ko public share karte ho (Anyone with link = Viewer)
3. Yahan JOURNAL_SHEET_URL set karte ho (.env ya GitHub secret)
4. Bot har scan pe sheet padhta hai → live P&L personal chat pe (PRIVATE —
   channel pe KABHI nahi). SHEET_WEBAPP_URL ho to live prices sheet me
   push bhi karta hai taaki sheet ke P&L formulas live calc karein.

Tum sheet me sirf apne trades likho (entry/SL/target/notes) —
bot usko live P&L, R-multiple, win-rate stats me convert kar dega.
"""
import csv
import io
import re
from urllib.parse import quote_plus

import requests

import analyzer
import config

rl_wait = 0.5
_session = requests.Session()
_session.headers.update({"User-Agent": "CryptoBhai-Agent/1.0"})


def _candidate_urls():
    """Trade Log tab tak pahunchne ke raste (order me try hote hain).

    1. gviz CSV by tab NAME -> "Trade Log" (sabse robust, gid ki zaroorat nahi)
    2. export?format=csv&gid=0 -> original tab (buildAll se pehle ka)
    3. export?format=csv -> first tab (Dashboard ban sakta hai — last resort)

    Note: buildAll ke baad Dashboard index 0 pe aa jata hai, isliye
    bina-gid export galat tab de deta hai — isliye candidates order me.
    """
    url = (config.JOURNAL_SHEET_URL or "").strip()
    if not url:
        return []
    if "/export?" in url or url.endswith(".csv"):
        return [url]
    m = re.match(r"https://docs\.google\.com/spreadsheets/d/([\w-]+)", url)
    if not m:
        return [url]  # shayad already csv link
    sid = m.group(1)
    tab = quote_plus("Trade Log")
    return [
        f"https://docs.google.com/spreadsheets/d/{sid}/gviz/tq?tqx=out:csv&sheet={tab}",
        f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid=0",
        f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv",
    ]


def _fetch_csv(url):
    """Public Google Sheet CSV fetch karo (gviz ya export endpoint)."""
    try:
        r = _session.get(url, timeout=20)
        if r.status_code == 200 and r.text.strip():
            return list(csv.DictReader(io.StringIO(r.text)))
    except requests.RequestException:
        pass
    return []


def _looks_like_journal(rows):
    """Pehli row me Coin/Symbol header ho tabhi accept karo.

    Isse gviz error pages / Dashboard CSV ko journal samajhne se bachate hain.
    """
    if not rows:
        return False
    keys = [(k or "").strip().lower() for k in rows[0].keys()]
    return any(k in ("coin", "symbol") for k in keys)


# Tumhare sheet ke column headers (flexibility ke liye multiple naam support)
COL = {
    "date":   ["date", "Date", "DATE", "tarikh", "date_entered"],
    "sym":    ["coin", "Coin", "COIN", "symbol", "Symbol", "SYMBOL"],
    "side":   ["side", "Side", "SIDE", "type", "Type", "direction"],
    "entry":  ["entry", "Entry", "ENTRY", "entry_price", "buy_price"],
    "sl":     ["sl", "SL", "stop", "Stop", "stop_loss", "SL Price"],
    "tp":     ["target", "Target", "TARGET", "tp", "TP", "take_profit"],
    "qty":    ["qty", "Qty", "QTY", "quantity", "size", "Size"],
    "lev":    ["lev", "Lev", "LEVERAGE", "leverage", "Leverage"],
    "notes":  ["notes", "Notes", "NOTES", "note", "reason", "Reason", "thesis"],
}


def _pick(row, *names):
    for n in names:
        for k, v in row.items():
            if k and k.strip() == n:
                if v is not None and str(v).strip():
                    return str(v).strip()
    return ""


def _f(x, default=0.0):
    try:
        return float(str(x).replace("$", "").replace(",", ""))
    except (ValueError, TypeError):
        return default


def load_entries():
    """Sheet se sab journal entries parse karo (candidates order me try)."""
    urls = _candidate_urls()
    if not urls:
        return [], "JOURNAL_SHEET_URL set nahi hai (.env ya GitHub secret)"
    rows = []
    for u in urls:
        cand = _fetch_csv(u)
        if _looks_like_journal(cand):
            rows = cand
            break
    if not rows:
        return [], "Sheet khali hai ya public share nahi hai (Viewer access chahiye)"

    entries = []
    for row in rows:
        sym = _pick(row, *COL["sym"]).upper()
        entry = _f(_pick(row, *COL["entry"]), 0)
        if not sym or entry <= 0:
            continue  # khali/galat row skip
        side = _pick(row, *COL["side"]).upper() or "LONG"
        if side not in ("LONG", "SHORT"):
            side = "LONG"
        e = {
            "date": _pick(row, *COL["date"]),
            "sym": sym,
            "side": side,
            "entry": entry,
            "sl": _f(_pick(row, *COL["sl"]), 0) or None,
            "target": _f(_pick(row, *COL["tp"]), 0) or None,
            "qty": _f(_pick(row, *COL["qty"]), 0) or 1.0,
            "lev": int(_f(_pick(row, *COL["lev"]), 1)) or 1,
            "notes": _pick(row, *COL["notes"]),
        }
        entries.append(e)
    return entries, None


def analyze(entries, markets):
    """Har entry ka live P&L + journal report banao."""
    by_sym = {}
    for c in markets:
        by_sym[(c.get("symbol") or "").upper()] = c
    analyzed = []
    for e in entries:
        coin = by_sym.get(e["sym"])
        if not coin:
            analyzed.append(dict(e, price=None, status="NO_DATA"))
            continue
        price = coin["current_price"]
        direction = 1 if e["side"] == "LONG" else -1
        pnl_pct = (price - e["entry"]) / e["entry"] * 100 * direction
        pnl_usd = pnl_pct / 100 * e["entry"] * e["qty"] * e["lev"]
        status = "OPEN"
        if e["target"] and ((price >= e["target"]) if e["side"] == "LONG"
                            else (price <= e["target"])):
            status = "TARGET_HIT"
        elif e["sl"] and ((price <= e["sl"]) if e["side"] == "LONG"
                          else (price >= e["sl"])):
            status = "SL_HIT"
        analyzed.append(dict(e, price=price, pnl_pct=pnl_pct,
                             pnl_usd=pnl_usd, status=status))
    return analyzed


def journal_report(entries, markets):
    """Channel/note ke liye journal summary."""
    if not entries:
        return "📒 Trading Journal: koi entries nahi mili sheet me.\n" \
               "Sheet me coin/entry/SL/target bharo — bot live P&L bana dega!"
    analyzed = analyze(entries, markets)
    if not analyzed:
        return "📒 Trading Journal: coins market data me nahi mile."

    open_t = [a for a in analyzed if a["status"] == "OPEN"]
    wins_t = [a for a in analyzed if a["status"] == "TARGET_HIT"]
    loss_t = [a for a in analyzed if a["status"] == "SL_HIT"]

    lines = ["📒 <b>TRADING JOURNAL (Google Sheet)</b>\n"]
    total_pnl = sum(a.get("pnl_usd", 0) for a in analyzed if a.get("pnl_usd"))
    total_open = sum(a.get("pnl_usd", 0) for a in open_t if a.get("pnl_usd"))
    for a in analyzed:
        emo = {"TARGET_HIT": "✅", "SL_HIT": "🛑", "OPEN": "🔄"}.get(a["status"], "•")
        price = a.get("price")
        pnl = a.get("pnl_pct")
        if price is None:
            lines.append(f"{emo} <b>{a['sym']}</b> — data nahi mila")
            continue
        lev = f" {a['lev']}x" if a["lev"] > 1 else ""
        lines.append(
            f"{emo} <b>{a['sym']} {a['side']}{lev}</b> @ {analyzer.fmt_price(a['entry'])}"
            f" → {analyzer.fmt_price(price)}\n"
            f"    {'🟢' if (pnl or 0) >= 0 else '🔴'} P&L: <b>{pnl:+.1f}%</b>"
            f" (${a.get('pnl_usd', 0):+.2f})"
            + (f" — <b>{a['status'].replace('_', ' ')}</b>" if a["status"] != "OPEN" else "")
            + (f"\n    📝 {a['notes'][:60]}" if a["notes"] else ""))
        lines.append("")

    lines.append("📊 <b>SUMMARY</b>")
    lines.append(f"• Open: <b>{len(open_t)}</b> | Target hit: <b>{len(wins_t)}</b> | "
                 f"SL hit: <b>{len(loss_t)}</b>")
    closed = len(wins_t) + len(loss_t)
    if closed:
        wr = len(wins_t) / closed * 100
        lines.append(f"• Win rate: <b>{wr:.0f}%</b> ({len(wins_t)}/{closed})")
    lines.append(f"• Unrealized P&L (open): "
                 f"<b>${total_open:+.2f}</b>")
    lines.append(f"• Total realized+unrealized: <b>${total_pnl:+.2f}</b>")
    lines.append("\n⚠️ <i>Tumhari khud ki entries — educational tracking. DYOR.</i>")
    return "\n".join(lines)


def weekly_stats(entries, markets):
    """Weekly report ke liye chhota summary."""
    if not entries:
        return ""
    analyzed = analyze(entries, markets)
    if not analyzed:
        return ""
    open_t = [a for a in analyzed if a["status"] == "OPEN"]
    wins_t = [a for a in analyzed if a["status"] == "TARGET_HIT"]
    loss_t = [a for a in analyzed if a["status"] == "SL_HIT"]
    total_pnl = sum(a.get("pnl_usd", 0) for a in analyzed if a.get("pnl_usd"))
    lines = [f"📒 <b>JOURNAL:</b> {len(open_t)} open | {len(wins_t)} TP | "
             f"{len(loss_t)} SL | P&L <b>${total_pnl:+.2f}</b>"]
    return "\n".join(lines)

def sheet_push_prices(entries, markets):
    """Open trades ke coins ke live prices sheet me push karo.

    Sheet web app (?action=update) Trade Log ke O col me Live Price likhta hai
    (sirf un rows pe jinka Exit khali hai) — sheet ke P&L formulas live calc
    karte hain. Silent helper: fail hone pe False, kabhi exception nahi.
    """
    url = (getattr(config, "SHEET_WEBAPP_URL", "") or "").strip()
    if not url or not entries:
        return False
    by_sym = {}
    for c in markets:
        sym = (c.get("symbol") or "").upper()
        if sym and c.get("current_price") and sym not in by_sym:
            by_sym[sym] = c["current_price"]
    pairs, seen = [], set()
    for e in entries:
        s = e["sym"]
        if s in seen or s not in by_sym:
            continue
        seen.add(s)
        pairs.append(f"{s}:{by_sym[s]}")
    if not pairs:
        return False
    try:
        r = _session.get(
            url,
            params={"action": "update", "prices": ",".join(pairs)},
            timeout=15,
        )
        return r.status_code == 200 and "OK" in r.text
    except requests.RequestException:
        return False
