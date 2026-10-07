"""ORDER-FLOW + INSTITUTIONAL FOOTPRINT — 100% free/public sources.

Crypto : OKX public trade-tape (last N trades ka buy/sell aggressor volume)
         = real order-flow direction, sub-second freshness on-demand.
NSE    : nseindia.com official APIs (public-by-law):
         delivery % (investor conviction), volumes, bulk/block deals.
         Sandbox/Akamai pe 403 ho sakta hai -> GitHub Actions pe chalta hai
         (cookie-dance, jugaad-data repo jaisa). Fail = None (kabhi crash nahi).
US     : SEC EDGAR filings public (13F/Form-4) — sentiment.py ke insider
         flags + Yahoo RSS se covered.
"""
import threading
import time

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"}
_cache = {}
_lock = threading.Lock()

OKX_INST = {  # hamare signals -> OKX perpetuals (public tape)
    "BTC": "BTC-USDT-SWAP", "ETH": "ETH-USDT-SWAP", "SOL": "SOL-USDT-SWAP",
    "XRP": "XRP-USDT-SWAP", "DOGE": "DOGE-USDT-SWAP", "ADA": "ADA-USDT-SWAP",
    "XLM": "XLM-USDT-SWAP", "LINK": "LINK-USDT-SWAP", "ZEC": "ZEC-USDT-SWAP",
}


def crypto_tape(sym, limit=50, ttl=300):
    """OKX last-trades tape -> dict(buy, sell, ratio, bias, big_trades).

    bias: BUYING / SELLING / MIXED (aggressor side = taker order-flow).
    """
    inst = OKX_INST.get(str(sym).upper())
    if not inst:
        return None
    key = f"tape:{inst}"
    with _lock:
        hit = _cache.get(key)
    if hit and time.time() - hit[1] < ttl:
        return hit[0]
    out = None
    try:
        r = requests.get("https://www.okx.com/api/v5/market/trades",
                         params={"instId": inst, "limit": limit},
                         timeout=10)
        if r.status_code == 200:
            trades = r.json().get("data", [])
            buy = sum(float(t["sz"]) for t in trades if t.get("side") == "buy")
            sell = sum(float(t["sz"]) for t in trades if t.get("side") == "sell")
            tot = buy + sell
            bias = "MIXED"
            if tot > 0:
                ratio = buy / tot
                bias = "BUYING" if ratio >= 0.60 else ("SELLING" if ratio <= 0.40 else "MIXED")
            else:
                ratio = 0.5
            big = [t for t in trades if float(t["sz"]) * float(t.get("px", 0)) > 500_000]
            out = dict(buy=round(buy, 2), sell=round(sell, 2),
                       ratio=round(ratio, 2), bias=bias,
                       big_n=len(big), n=len(trades))
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        out = None
    with _lock:
        _cache[key] = (out, time.time())
    return out


def tape_line(sym):
    """Signal card ke liye ek line (ya '')."""
    f = crypto_tape(sym)
    if not f:
        return ""
    emo = "\U0001f7e2" if f["bias"] == "BUYING" else (
        "\U0001f534" if f["bias"] == "SELLING" else "\u2696\ufe0f")
    big = (f" \u00b7 {f['big_n']} whale-print(s) \U0001f4b0"
           if f.get("big_n") else "")
    return (f"{emo} Order-flow: <b>{f['bias']}</b> "
            f"(taker buy/sell {f['buy']}/{f['sell']} "
            f"= {f['ratio']*100:.0f}% buy){big}")


def _nse_session():
    s = requests.Session()
    s.headers.update(dict(UA, Accept="*/*",
                          Referer="https://www.nseindia.com/market-data/live-equity-market"))
    try:
        s.get("https://www.nseindia.com", timeout=10)
        s.get("https://www.nseindia.com/market-data/live-equity-market",
              timeout=10)
    except requests.RequestException:
        pass
    return s


def nse_flows(sym, ttl=3600):
    """NSE official quote -> delivery% + volume (institutional conviction).

    Delivery% high (>60%) = investors taking delivery (conviction);
    low (<25%) = intraday speculation. None on block (sandbox IP).
    """
    key = f"nseflow:{sym}"
    with _lock:
        hit = _cache.get(key)
    if hit and time.time() - hit[1] < ttl:
        return hit[0]
    out = None
    try:
        s = _nse_session()
        r = s.get("https://www.nseindia.com/api/quote-equity",
                  params={"symbol": sym}, timeout=12)
        if r.status_code == 200:
            d = r.json()
            pi = d.get("priceInfo", {})
            dp = d.get("securityWiseDP") or {}
            out = dict(
                last=pi.get("lastPrice"),
                deliv_pct=float(dp.get("deliveryPercentage") or 0) or None,
                deliv_qty=dp.get("quantityTraded"),
                volume=pi.get("totalTradedVolume"),
            )
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        out = None
    with _lock:
        _cache[key] = (out, time.time())
    return out


def nse_line(sym):
    """NSE signal card line (ya '')."""
    f = nse_flows(sym)
    if not f or not f.get("deliv_pct"):
        return ""
    d = f["deliv_pct"]
    emo = "\U0001f4aa" if d >= 55 else ("\U0001f3ad" if d <= 30 else "\u2696\ufe0f")
    note = ("conviction delivery" if d >= 55 else
            ("intraday speculation" if d <= 30 else "balanced"))
    return (f"{emo} Delivery {d:.0f}% ({note}) "
            f"\u00b7 vol {f.get('volume') or 0:,.0f}")
