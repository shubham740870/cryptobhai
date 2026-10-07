"""FREE sentiment stack — paid-data loopholes (sab keyless):

1. Google News RSS   -> per-stock/coin headlines -> keyword sentiment score
2. Yahoo Finance RSS -> US/global headlines (insider-sell/buy flags keyword se)
3. Yahoo calendar    -> earnings dates -> pre-earnings risk alerts
4. Fear&Greed (crypto) + funding (OKX, futures.py) -> positioning extremes

Pro-equivalence: real-time news tone (approx, 15-min fresh), insider FLOW
news flags, earnings-call VOL awareness (date+consensus) — binary-event
discipline (Marks/PTJ) ke liye kaafi.
"""
import re
import threading
import time

import requests

UA = {"User-Agent": "Mozilla/5.0 (compatible; CryptoBhaiAgent/1.0)"}
_cache = {}
_lock = threading.Lock()

POS = ("surge surges jump jumps rally rallies record all-time high beat beats "
       "upgrade upgrades bullish profit gains boost strong growth expansion "
       "wins deal deals order orders dividend buyback buybacks unlock value "
       "hikes stake signs partnership breakthrough outperform inflows"
       ).split()
NEG = ("fall falls drop drops plunge plunges crash sink sinks slump weak "
       "loss losses downgrade downgrades bearish probe fraud lawsuit penalty "
       "fine exit shuts shut cut cuts layoff layoffs strike scam arrest raid "
       "dilution blocks warning sell-off selloff outflows crackdown default "
       "resign quits underperform miss misses recall ban ban"
       ).split()
INSIDER_SELL = ("insider selling", "sold shares", "stake sale", "promoter "
                "sold", "ceo sells", " CFO sells", "offload")
INSIDER_BUY = ("insider buying", "bought shares", "promoter bought",
               "open market purchase", "ceo buys")


def _score_titles(titles):
    """Titles -> (score -100..100, n_pos, n_neg, flags)."""
    pos = neg = 0
    flags = set()
    blob = " || ".join(t.lower() for t in titles)
    for w in POS:
        c = len(re.findall(rf"\b{re.escape(w)}\w*\b", blob))
        pos += c
    for w in NEG:
        c = len(re.findall(rf"\b{re.escape(w)}\w*\b", blob))
        neg += c
    low = blob
    if any(k in low for k in INSIDER_SELL):
        flags.add("INSIDER_SELL")
    if any(k in low for k in INSIDER_BUY):
        flags.add("INSIDER_BUY")
    if "results" in low or "earnings" in low or "q1" in low or "q2" in low \
            or "q3" in low or "q4" in low:
        flags.add("EARNINGS_TALK")
    total = pos + neg
    if total == 0:
        return 0, 0, 0, flags
    score = int(max(-100, min(100, (pos - neg) / max(total, 4) * 100)))
    return score, pos, neg, flags


def headlines_google(query, limit=12, ttl=7200):
    """Google News RSS -> [titles] (2h cache)."""
    key = f"g:{query}"
    with _lock:
        hit = _cache.get(key)
    if hit and time.time() - hit[1] < ttl:
        return hit[0]
    try:
        r = requests.get(
            "https://news.google.com/rss/search",
            params={"q": query, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"},
            headers=UA, timeout=12)
        titles = re.findall(r"<title>(.*?)</title>", r.text)[1:limit + 1]
        titles = [t.replace("&amp;", "&").replace("&#39;", "'")
                  .replace("&quot;", '"') for t in titles]
    except requests.RequestException:
        titles = []
    with _lock:
        _cache[key] = (titles, time.time())
    return titles


def earnings_date(sym, kind="NSE"):
    """Next earnings date (Yahoo calendarEvents) — cache 12h. None on fail."""
    key = f"e:{sym}"
    with _lock:
        hit = _cache.get(key)
    if hit and time.time() - hit[1] < 43200:
        return hit[0]
    out = None
    try:
        s = requests.Session()
        s.headers.update(UA)
        try:
            s.get("https://fc.yahoo.com", timeout=8)
        except requests.RequestException:
            pass
        crumb = s.get("https://query1.finance.yahoo.com/v1/test/getcrumb",
                      timeout=8).text.strip()
        ysym = f"{sym}.NS" if kind == "NSE" else (
            {"XAU": "GC=F", "XAG": "SI=F"}.get(sym, sym))
        r = s.get(
            f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ysym}",
            params={"modules": "calendarEvents", "crumb": crumb}, timeout=12)
        if r.status_code == 200:
            ce = (r.json()["quoteSummary"]["result"][0].get("calendarEvents")
                  or {}).get("earnings", {})
            d = ce.get("earningsDate")
            if d:
                out = d[0].get("fmt")
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        out = None
    with _lock:
        _cache[key] = (out, time.time())
    return out


def analyze(sym, kind="NSE", name=None):
    """Asset ka sentiment pack — news score + flags + earnings window.

    Returns dict: score(-100..100), pos, neg, flags, news_n,
                  earn_in (days int ya None), earn_date
    """
    if kind == "NSE":
        q = f"{name or sym} stock shares"
    elif kind == "CRYPTO":
        q = f"{name or sym} crypto price"
    elif kind == "FX":
        q = f"{name or sym} dollar currency"
    else:
        q = f"{name or sym} gold silver price"
    titles = headlines_google(q)
    score, pos, neg, flags = _score_titles(titles)
    earn = None
    if kind == "NSE":
        earn = earnings_date(sym, kind)
    earn_in = None
    if earn:
        try:
            import datetime as _dt
            ed = _dt.date.fromisoformat(earn[:10])
            earn_in = (ed - _dt.date.today()).days
        except ValueError:
            pass
    return dict(score=score, pos=pos, neg=neg, flags=flags,
                news_n=len(titles), earn_in=earn_in, earn_date=earn)


def line(pack):
    """Sentiment pack -> card line (emoji + score + flags)."""
    if not pack or not pack.get("news_n"):
        return ""
    s = pack["score"]
    emo = "\U0001f4c8" if s >= 20 else ("\U0001f4c9" if s <= -20 else "\u2696\ufe0f")
    parts = [f"{emo} News: {s:+d} ({pack['news_n']} headlines, "
             f"{pack['pos']}+/{pack['neg']}-)"]
    if "INSIDER_SELL" in pack["flags"]:
        parts.append("\U0001f464 insider-sell news!")
    if "INSIDER_BUY" in pack["flags"]:
        parts.append("\U0001f464 insider-BUY news!")
    ei = pack.get("earn_in")
    if ei is not None and -1 <= ei <= 7:
        parts.append(f"\u26a0\ufe0f Results {pack['earn_date']} "
                     f"({ei} din) \u2014 vol alert, size chhota karo!")
    return " | ".join(parts)
