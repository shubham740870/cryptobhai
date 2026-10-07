"""NSE fundamentals — Yahoo quoteSummary (cookie+crumb flow) + 24h disk cache.

Fields: PE, PB, PEG, EPS, BVPS, ROE, D/E, margins, rev/earn growth,
analyst target + consensus. InvestingPro-style data, free.
"""
import json
import os
import threading
import time

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "data", "fund_cache.json")
_lock = threading.Lock()
_sess = None
_crumb = {"v": None, "ts": 0}


def _cache_load():
    try:
        return json.load(open(CACHE_FILE))
    except (OSError, ValueError):
        return {}


def _cache_save(d):
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        json.dump(d, open(CACHE_FILE, "w"))
    except OSError:
        pass


def _session():
    global _sess
    if _sess is None:
        _sess = requests.Session()
        _sess.headers.update(UA)
        try:
            _sess.get("https://fc.yahoo.com", timeout=10)   # cookie set
        except requests.RequestException:
            pass
    if not _crumb["v"] or time.time() - _crumb["ts"] > 3600:
        try:
            r = _sess.get("https://query1.finance.yahoo.com/v1/test/getcrumb",
                          timeout=10)
            _crumb["v"] = r.text.strip()
            _crumb["ts"] = time.time()
        except requests.RequestException:
            _crumb["v"] = ""
    return _sess


def _g(x):
    return x.get("raw") if isinstance(x, dict) else x


def get_fundamentals(sym, ttl=86400):
    """sym jaise 'RELIANCE' -> fundamentals dict (24h cache). Fail -> None."""
    key = sym.upper()
    with _lock:
        cache = _cache_load()
    hit = cache.get(key)
    if hit and time.time() - hit.get("ts", 0) < ttl:
        return hit.get("data")
    s = _session()
    d = None
    for host in ("query1", "query2"):
        try:
            r = s.get(
                f"https://{host}.finance.yahoo.com/v10/finance/quoteSummary/{key}.NS",
                params={"modules": "financialData,defaultKeyStatistics,summaryDetail",
                        "crumb": _crumb["v"] or ""}, timeout=15)
            if r.status_code != 200:
                continue
            res = r.json()["quoteSummary"]["result"][0]
            fd = res.get("financialData", {})
            ks = res.get("defaultKeyStatistics", {})
            sd = res.get("summaryDetail", {})
            d = dict(
                pe=_g(sd.get("trailingPE")), pb=_g(sd.get("priceToBook")),
                peg=_g(ks.get("pegRatio")), eps=_g(ks.get("trailingEps")),
                bvps=_g(ks.get("bookValue")), roe=_g(fd.get("returnOnEquity")),
                de=_g(fd.get("debtToEquity")), margin=_g(fd.get("profitMargins")),
                rev_g=_g(fd.get("revenueGrowth")), earn_g=_g(fd.get("earningsGrowth")),
                target=_g(fd.get("targetMeanPrice")), beta=_g(ks.get("beta")),
                div=_g(sd.get("dividendYield")), mcap=_g(sd.get("marketCap")),
                rec=_g(fd.get("recommendationMean")),
            )
            break
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
            continue
    with _lock:
        cache = _cache_load()
        cache[key] = {"ts": time.time(), "data": d}
        _cache_save(cache)
    return d
