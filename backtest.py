"""Strategy backtester — har market ka 2 saal historical data → best params.

Ye hai "training": grid-search (SL mult x TP mult x RSI filter x trend type)
har asset class pe — jo rules historically best win-rate + profit factor de,
wahi params signals use karte hain (data/strategy_params.json me save).
"""
import itertools
import json
import os
import time

import requests

import indicators as ind

UA = {"User-Agent": "Mozilla/5.0 (compatible; CryptoBhaiAgent/1.0)"}
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "data", "strategy_params.json")

INSTRUMENTS = {
    "metals": ["GC=F", "SI=F"],
    "fx": ["GBPUSD=X", "EURUSD=X"],
    "crypto": ["BTC-USD", "ETH-USD"],
    "nse": ["RELIANCE.NS", "^NSEI", "TCS.NS", "HDFCBANK.NS"],
}

PARAM_GRID = {
    "sl_mult": [1.5, 1.8, 2.2],
    "tp_mult": [2.0, 2.5, 3.0],
    "rsi_filter": [True, False],   # True = RSI<72 long / >28 short (avoid exhaustion)
    "trend": ["ema20_50", "ema50_200"],
}
DEFAULTS = {"sl_mult": 1.8, "tp_mult": 2.2, "rsi_filter": True, "trend": "ema20_50"}


def fetch_daily(sym, rng="2y"):
    """Yahoo daily OHLC — [(close, high, low), ...] oldest→newest."""
    for host in ("query1", "query2"):
        try:
            r = requests.get(
                f"https://{host}.finance.yahoo.com/v8/finance/chart/{sym}",
                params={"interval": "1d", "range": rng}, headers=UA, timeout=15)
            if r.status_code != 200:
                continue
            q = r.json()["chart"]["result"][0]["indicators"]["quote"][0]
            out = [(c, h, l) for c, h, l in zip(q["close"], q["high"], q["low"])
                   if c and h and l]
            if out:
                return out
        except (requests.RequestException, ValueError, KeyError, IndexError):
            continue
    return []


def _simulate(bars, sl_mult, tp_mult, rsi_filter, trend):
    """Long+short swing sim: trend+MACD entry, ATR SL/TP (SL pehle agar dono touch)."""
    closes = [b[0] for b in bars]
    highs = [b[1] for b in bars]
    lows = [b[2] for b in bars]
    e_f = ind.ema(closes, 20)
    e_s = ind.ema(closes, 50)
    e_200 = ind.ema(closes, 200)
    rsi = ind.rsi(closes)
    _, _, hist = ind.macd(closes)
    atr = ind.atr(highs, lows, closes, 14)

    def lv(series, i):
        v = series[i] if i < len(series) else None
        if isinstance(v, list):
            v = ind.last_valid(v)
        return v

    n, wins, gross_w, gross_l = 0, 0, 0.0, 0.0
    pos = 0          # 0 flat, +1 long, -1 short
    entry = sl = tp = 0.0
    hold = 0
    for i in range(210, len(closes)):
        if pos:
            hold += 1
            hit_sl = (lows[i] <= sl) if pos > 0 else (highs[i] >= sl)
            hit_tp = (highs[i] >= tp) if pos > 0 else (lows[i] <= tp)
            if hit_sl:                        # conservative: SL first
                n += 1
                gross_l += 1
                pos = 0
            elif hit_tp:
                n += 1
                wins += 1
                gross_w += 1
                pos = 0
            elif hold >= 20:
                px = closes[i]
                r = ((px - entry) if pos > 0 else (entry - px)) / max(entry - sl, 1e-9)
                n += 1
                if r > 0:
                    wins += 1
                    gross_w += 1
                else:
                    gross_l += 1
                pos = 0
            continue
        ef, es = lv(e_f, i), lv(e_s, i)
        if ef is None or es is None:
            continue
        up = ef > es if trend == "ema20_50" else (ef > (lv(e_200, i) or ef))
        dn = ef < es if trend == "ema20_50" else (ef < (lv(e_200, i) or ef))
        mh, rs, av = lv(hist, i) or 0, lv(rsi, i) or 50, lv(atr, i) or 0
        if av <= 0:
            continue
        px = closes[i]
        rsi_ok = (not rsi_filter) or (rs < 72)
        if up and mh > 0 and rsi_ok:
            pos, entry, hold = 1, px, 0
            sl, tp = px - sl_mult * av, px + tp_mult * av
        elif dn and mh < 0 and ((not rsi_filter) or rs > 28):
            pos, entry, hold = -1, px, 0
            sl, tp = px + sl_mult * av, px - tp_mult * av
    return n, wins, gross_w, gross_l


def _score(instrument, bars):
    """Saare param combos try karo — (winrate, PF, n, params) sorted best."""
    results = []
    for sl_m, tp_m, rf, tr in itertools.product(
            PARAM_GRID["sl_mult"], PARAM_GRID["tp_mult"],
            PARAM_GRID["rsi_filter"], PARAM_GRID["trend"]):
        n, w, gw, gl = _simulate(bars, sl_m, tp_m, rf, tr)
        if n < 12:                      # kaafi trades nahi to skip
            continue
        wr = w / n
        pf = gw / gl if gl else 9.9
        results.append({"instrument": instrument, "trades": n,
                        "win_rate": round(wr * 100, 1), "profit_factor": round(pf, 2),
                        "params": {"sl_mult": sl_m, "tp_mult": tp_m,
                                   "rsi_filter": rf, "trend": tr}})
    results.sort(key=lambda x: (x["profit_factor"], x["win_rate"]), reverse=True)
    return results[:3]


def run(verbose=True):
    """Poora backtest chalao — {asset_class: best_params + stats} save."""
    out = {}
    for cls, syms in INSTRUMENTS.items():
        agg = []
        for sym in syms:
            bars = fetch_daily(sym)
            if not bars:            # Yahoo burst-limit — ek retry
                time.sleep(2)
                bars = fetch_daily(sym)
            time.sleep(0.5)         # polite: burst rate-limit se bacho
            if len(bars) < 260:
                continue
            top = _score(sym, bars)
            agg.append((sym, top))
            if verbose:
                for t in top[:1]:
                    print(f"  {sym:12s} WR {t['win_rate']:5.1f}%  PF {t['profit_factor']:4.2f}"
                          f"  n={t['trades']:3d}  {t['params']}")
        if agg:
            # asset class ka common param set = members ke top params ka vote
            votes = {}
            for sym, top in agg:
                if top:
                    k = json.dumps(top[0]["params"], sort_keys=True)
                    votes[k] = votes.get(k, 0) + 1
            best_key = max(votes, key=votes.get)
            best = json.loads(best_key)
            avg_wr = sum(t[1][0]["win_rate"] for t in agg if t[1]) / len(agg)
            avg_pf = sum(t[1][0]["profit_factor"] for t in agg if t[1]) / len(agg)
            out[cls] = dict(params=best, avg_win_rate=round(avg_wr, 1),
                            avg_profit_factor=round(avg_pf, 2),
                            instruments={s: (t[0]["win_rate"] if t[1] else None)
                                         for s, t in agg},
                            tuned_at=time.strftime("%Y-%m-%d"))
            if verbose:
                print(f"== {cls}: {best} | avg WR {avg_wr:.1f}% | avg PF"
                      f" {out[cls]['avg_profit_factor']} ==")
    try:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        json.dump(out, open(DATA_FILE, "w"), indent=1)
    except OSError:
        pass
    return out


def params(asset_class):
    """Asset class ke tuned params (fallback DEFAULTS)."""
    try:
        d = json.load(open(DATA_FILE))
        if asset_class in d and d[asset_class].get("params"):
            return dict(DEFAULTS, **d[asset_class]["params"])
    except (OSError, ValueError):
        pass
    return dict(DEFAULTS)
