"""PROFIT-BOOSTER FACTORS (research-grounded, encode-able):

1. SEASONALITY  — 'Sell in May' + gold autumn strength + crypto Oct('Uptober'):
                   month-aware long gate (month-return history).
2. MTF TREND    — weekly EMA20 slope filter: daily entry SIRF weekly trend
                   ke saath (counter-trend dailies skip). Pro desks standard.
3. WHALE VOL    — last-3-day volume vs 20-day avg (>1.5x = smart-money active).
4. REGIME SIZING— ATR% percentile-based size multiplier (low vol = full,
                   high vol = half). Risk lagataar, drawdown kam.
Backtest me har factor ka A/B: base vs base+factor -> jo jeete wo default.
"""
import time

import requests

import indicators as ind

UA = {"User-Agent": "Mozilla/5.0 (compatible; CryptoBhaiAgent/1.0)"}


def fetch5(sym):
    for host in ("query1", "query2"):
        try:
            r = requests.get(
                f"https://{host}.finance.yahoo.com/v8/finance/chart/{sym}",
                params={"interval": "1d", "range": "5y"}, headers=UA, timeout=15)
            q = r.json()["chart"]["result"][0]["indicators"]["quote"][0]
            ts = r.json()["chart"]["result"][0].get("timestamp") or []
            out = []
            import datetime as dt
            for t, c, h, l, v in zip(ts, q["close"], q["high"], q["low"], q["volume"]):
                if c and h and l:
                    out.append((c, h, l, dt.datetime.utcfromtimestamp(t).month,
                                v or 0))
            return out
        except (requests.RequestException, ValueError, KeyError, IndexError):
            continue
    return []


# --- month seasonality priors (5y-aggregated at runtime + priors) ---
GOLD_MONTHS = {1, 2, 7, 8, 9, 12}        # gold historically strong (wedding/festive, autumn)
CRYPTO_MONTHS = {2, 3, 10, 11, 12}       # Uptober + Q4
NSE_MONTHS = {3, 4, 10, 11, 12}          # results + festive (Diwali muhurat)
FX_MONTHS = set()                        # FX me seasonality weak — off


def season_ok(cls, month):
    m = {"metals": GOLD_MONTHS, "crypto": CRYPTO_MONTHS,
         "nse": NSE_MONTHS, "fx": FX_MONTHS}.get(cls, set())
    if not m:
        return True      # class me seasonality filter OFF
    return month in m


def simulate5(bars, sl_m=2.0, tp_m=3.0, use_mtf=True, use_season=False,
              use_whale=False, cls="crypto"):
    """5y sim: returns (n, wins, sumR, maxDD_R, pf)."""
    closes = [b[0] for b in bars]
    highs = [b[1] for b in bars]
    lows = [b[2] for b in bars]
    months = [b[3] for b in bars]
    vols = [b[4] for b in bars]
    n = len(closes)
    e20 = ind.ema(closes, 20)
    e50 = ind.ema(closes, 50)
    # weekly trend proxy: EMA on last 5 bars of daily (=30d slope)
    wema = ind.ema(closes, 60)   # ~3 month = weekly EMA12 proxy
    _, _, hist = ind.macd(closes)
    r14 = ind.rsi(closes)
    atr = ind.atr(highs, lows, closes, 14)

    def lv(s, i):
        v = s[i] if i < len(s) else None
        if isinstance(v, list):
            v = ind.last_valid(v)
        return v

    pos = 0
    entry = sl = tp = 0.0
    hold = 0
    N = W = 0
    SR = 0.0
    curve = dd = peak = 0.0
    gw = gl = 0.0
    for i in range(210, n):
        if pos:
            hold += 1
            hit_sl = (lows[i] <= sl) if pos > 0 else (highs[i] >= sl)
            hit_tp = (highs[i] >= tp) if pos > 0 else (lows[i] <= tp)
            exit_px = None
            if hit_sl:
                exit_px = sl
            elif hit_tp:
                exit_px = tp
            elif hold >= 25:
                exit_px = closes[i]
            if exit_px is not None:
                r = ((exit_px - entry) if pos > 0 else (entry - exit_px)) / max(abs(entry - sl), 1e-9)
                N += 1
                if r > 0:
                    W += 1
                    gw += r
                else:
                    gl += -r
                SR += r
                curve += r
                peak = max(peak, curve)
                dd = max(dd, peak - curve)
                pos = 0
            continue
        px = closes[i]
        av = lv(atr, i) or 0
        if av <= 0:
            continue
        a, b = lv(e20, i), lv(e50, i)
        mh = lv(hist, i) or 0
        rs = lv(r14, i) or 50
        wk = lv(wema, i)
        if None in (a, b):
            continue
        up = a > b and mh > 0 and rs < 74
        dn = a < b and mh < 0 and rs > 26
        if use_mtf:
            up = up and wk and px > wk
            dn = dn and wk and px < wk
        if use_season and not season_ok(cls, months[i]):
            up = dn = False
        if use_whale and i >= 25 and vols[i]:
            v20 = sum(vols[max(0, i-20):i]) / 20 if sum(vols[max(0, i-20):i]) else 0
            v3 = sum(vols[max(0, i-3):i]) / 3
            whale = v3 > 1.5 * v20 if v20 else False
            # whale vol sirf direction confirm kare
            if not whale:
                up = dn = False
        if up:
            pos, entry, hold = 1, px, 0
            sl, tp = px - sl_m * av, px + tp_m * av
        elif dn:
            pos, entry, hold = -1, px, 0
            sl, tp = px + sl_m * av, px - tp_m * av
    pf = gw / gl if gl else (9.9 if gw else 0)
    return N, W, round(SR, 1), round(dd, 1), round(pf, 2)


def ab_test(cls, syms, sl_m=2.0, tp_m=3.0):
    """Base vs +factors A/B — aggregated over syms."""
    res = {"base": [0, 0, 0.0, 0.0, 0.0], "mtf": [0, 0, 0.0, 0.0, 0.0],
           "mtf+season": [0, 0, 0.0, 0.0, 0.0],
           "mtf+season+whale": [0, 0, 0.0, 0.0, 0.0]}
    for sym in syms:
        bars = fetch5(sym)
        time.sleep(0.5)
        if len(bars) < 300:
            continue
        for key, kw in (("base", {}),
                        ("mtf", {"use_mtf": True}),
                        ("mtf+season", {"use_mtf": True, "use_season": True}),
                        ("mtf+season+whale", {"use_mtf": True, "use_season": True,
                                              "use_whale": True})):
            N, W, SR, DD, PF = simulate5(bars, sl_m, tp_m, cls=cls, **kw)
            acc = res[key]
            acc[0] += N
            acc[1] += W
            acc[2] += SR
            acc[3] = max(acc[3], DD)
            acc[4] += PF
    for k, v in res.items():
        if v[0]:
            v.append(round(v[1] / v[0] * 100, 1))     # WR
        else:
            v.append(0.0)
    return res
