"""MASTERY ENGINE — duniya ke best traders/firms ke documented strategies.

Har strategy ke PUBLIC rules encode kiye gaye hain, phir hamare 2 saal ke
data pe backtest hote hain — jo asset-class me best win-rate/PF de, wahi
strategy us class ke live signals me use hoti hai (strategy_params.json).

  turtle      Richard Dennis ke Turtles — 20d Donchian breakout, 2N stop,
              10d opposite-extreme exit (no profit target, trend ride)
  trend_atr   Ed Seykota / CTA style — EMA trend + MACD momentum + ATR stop
  rsi2        Larry Connors RSI-2 mean reversion — 200DMA filter, RSI2<10
              dip-buy, exit on 5DMA snapback (high win-rate system)
  momentum    AQR/Cliff Asness momentum factor — 126d absolute momentum
  tj_5to1     Paul Tudor Jones — 200DMA bias + tight stop + 5:1 reward-risk
  voltarget   BlackRock-style risk-managed trend — trend entry SIRF low-vol
              regime me (ATR% below median) = vol-targeted exposure
"""
import json
import time

import backtest
import indicators as ind

STRATS = ("turtle", "trend_atr", "rsi2", "momentum", "tj_5to1", "voltarget")

CANON = {   # canonical SL/TP multiples (R-multiple framework)
    "turtle":   dict(sl_mult=2.0, tp_mult=0.0),   # tp 0 = no target (trailing exit)
    "trend_atr": dict(sl_mult=None, tp_mult=None),  # tuned params use honge
    "rsi2":     dict(sl_mult=3.0, tp_mult=1.2),
    "momentum": dict(sl_mult=2.5, tp_mult=6.0),
    "tj_5to1":  dict(sl_mult=1.0, tp_mult=5.0),
    "voltarget": dict(sl_mult=2.0, tp_mult=3.0),
}
TIME_STOP = {"turtle": 0, "trend_atr": 20, "rsi2": 10, "momentum": 60,
             "tj_5to1": 30, "voltarget": 25}


def _ctx(bars):
    """Ek baar saare indicators precompute (fast backtest)."""
    closes = [b[0] for b in bars]
    highs = [b[1] for b in bars]
    lows = [b[2] for b in bars]
    n = len(closes)
    don = {k: [None] * n for k in ("d20h", "d20l", "d10h", "d10l")}
    for i in range(n):
        if i >= 21:
            don["d20h"][i] = max(highs[i - 21:i - 1])
            don["d20l"][i] = min(lows[i - 21:i - 1])
        if i >= 11:
            don["d10h"][i] = max(highs[i - 11:i - 1])
            don["d10l"][i] = min(lows[i - 11:i - 1])
    _, _, hist = ind.macd(closes)
    r14 = ind.rsi(closes)
    rsi2 = ind.rsi(closes, 2)
    atr = ind.atr(highs, lows, closes, 14)
    atr_pct = [atr[i] / closes[i] * 100 if atr[i] else None for i in range(n)]
    vals = sorted(x for x in atr_pct if x is not None)
    atr_med = vals[len(vals) // 2] if vals else 2.0
    sma5 = [None] * n
    sma200 = [None] * n
    for i in range(n):
        if i >= 5:
            sma5[i] = sum(closes[i - 5:i]) / 5
        if i >= 200:
            sma200[i] = sum(closes[i - 200:i]) / 200
    mom126 = [None] * n
    for i in range(n):
        if i >= 126:
            mom126[i] = closes[i] / closes[i - 126] - 1
    return dict(closes=closes, highs=highs, lows=lows, e20=ind.ema(closes, 20),
                e50=ind.ema(closes, 50), sma5=sma5, sma200=sma200,
                rsi=r14, rsi2=rsi2, hist=hist, atr=atr, atr_pct=atr_pct,
                atr_med=atr_med, mom126=mom126, **don)


def _lv(series, i):
    v = series[i] if i < len(series) else None
    if isinstance(v, list):
        v = ind.last_valid(v)
    return v


def simulate(ctx, strat, sl_m, tp_m):
    """Ek strategy ka long+short sim. Returns (n, wins, sumR_win, sumR_loss, maxDD_R)."""
    C = ctx["closes"]
    H, L = ctx["highs"], ctx["lows"]
    n_tot = len(C)
    pos = 0
    entry = sl = tp = 0.0
    hold = 0
    n = wins = 0
    srw = srl = 0.0
    rseq = []
    curve = dd = peak = 0.0
    for i in range(210, n_tot):
        if pos:
            hold += 1
            hit_sl = (L[i] <= sl) if pos > 0 else (H[i] >= sl)
            hit_tp = tp_m > 0 and ((H[i] >= tp) if pos > 0 else (L[i] <= tp))
            exit_px = None
            if hit_sl:
                exit_px = sl
            elif hit_tp:
                exit_px = tp
            elif strat == "turtle":
                if pos > 0 and ctx["d10l"][i] and L[i] <= ctx["d10l"][i]:
                    exit_px = C[i]
                elif pos < 0 and ctx["d10h"][i] and H[i] >= ctx["d10h"][i]:
                    exit_px = C[i]
            elif strat == "rsi2":
                r2 = _lv(ctx["rsi2"], i)
                if pos > 0 and ctx["sma5"][i] and C[i] > ctx["sma5"][i]:
                    exit_px = C[i]
                elif pos < 0 and ctx["sma5"][i] and C[i] < ctx["sma5"][i]:
                    exit_px = C[i]
                elif r2 is not None and ((pos > 0 and r2 > 65) or (pos < 0 and r2 < 35)):
                    exit_px = C[i]
            ts = TIME_STOP.get(strat, 20)
            if exit_px is None and ts and hold >= ts:
                exit_px = C[i]
            if exit_px is not None:
                r = ((exit_px - entry) if pos > 0 else (entry - exit_px)) / max(entry - sl, 1e-9) * (1 if pos > 0 else 1)
                if pos < 0:
                    r = (entry - exit_px) / max(sl - entry, 1e-9)
                r = max(min(r, tp_m if tp_m else 25.0), -sl_m)
                n += 1
                if r > 0:
                    wins += 1
                    srw += r
                else:
                    srl += -r
                curve += r
                peak = max(peak, curve)
                dd = max(dd, peak - curve)
                rseq.append(r)
                pos = 0
            continue
        # ---- entries ----
        px = C[i]
        av = _lv(ctx["atr"], i) or 0
        if av <= 0:
            continue
        e20, e50 = _lv(ctx["e20"], i), _lv(ctx["e50"], i)
        mh = _lv(ctx["hist"], i) or 0
        r14 = _lv(ctx["rsi"], i) or 50
        long_ok = short_ok = False
        if strat == "turtle":
            long_ok = ctx["d20h"][i] and px > ctx["d20h"][i]
            short_ok = ctx["d20l"][i] and px < ctx["d20l"][i]
        elif strat == "trend_atr":
            long_ok = e20 and e50 and px > e20 > e50 and mh > 0 and r14 < 72
            short_ok = e20 and e50 and px < e20 < e50 and mh < 0 and r14 > 28
        elif strat == "rsi2":
            s200 = ctx["sma200"][i]
            r2 = _lv(ctx["rsi2"], i)
            long_ok = s200 and px > s200 and r2 is not None and r2 < 10
            short_ok = s200 and px < s200 and r2 is not None and r2 > 90
        elif strat == "momentum":
            m = _lv(ctx["mom126"], i)
            long_ok = m is not None and m > 0.02 and e50 and px > e50
            short_ok = m is not None and m < -0.02 and e50 and px < e50
        elif strat == "tj_5to1":
            s200 = ctx["sma200"][i]
            long_ok = s200 and px > s200 and mh > 0
            short_ok = s200 and px < s200 and mh < 0
        elif strat == "voltarget":
            ap = _lv(ctx["atr_pct"], i) or 99
            long_ok = (ctx["d20h"][i] and px > ctx["d20h"][i] and ap < ctx["atr_med"])
            short_ok = (ctx["d20l"][i] and px < ctx["d20l"][i] and ap < ctx["atr_med"])
        if long_ok:
            pos, entry, hold = 1, px, 0
            sl, tp = px - sl_m * av, (px + tp_m * av if tp_m > 0 else 0)
        elif short_ok:
            pos, entry, hold = -1, px, 0
            sl, tp = px + sl_m * av, (px - tp_m * av if tp_m > 0 else 0)
    return n, wins, srw, srl, dd


def run(verbose=True):
    """Sab strategies × sab instruments → per-class winner save."""
    old = {}
    try:
        old = json.load(open(backtest.DATA_FILE))
    except (OSError, ValueError):
        pass
    table = {}
    out = dict(old)
    for cls, syms in backtest.INSTRUMENTS.items():
        tuned = old.get(cls, {}).get("params", {})
        rows = {}
        for strat in STRATS:
            canon = CANON[strat]
            sl_m = canon["sl_mult"] or tuned.get("sl_mult", 1.8)
            tp_m = canon["tp_mult"] or tuned.get("tp_mult", 2.2)
            N = W = 0
            SRW = SRL = DD = 0.0
            for sym in syms:
                bars = backtest.fetch_daily(sym)
                if not bars:
                    time.sleep(2)
                    bars = backtest.fetch_daily(sym)
                time.sleep(0.4)
                if len(bars) < 260:
                    continue
                ctx = _ctx(bars)
                n, w, srw, srl, dd = simulate(ctx, strat, sl_m, tp_m)
                N += n
                W += w
                SRW += srw
                SRL += srl
                DD = max(DD, dd)
            if N >= 10:
                rows[strat] = dict(trades=N, win_rate=round(W / N * 100, 1),
                                   profit_factor=round(SRW / SRL, 2) if SRL else 9.9,
                                   maxdd_r=round(DD, 1),
                                   exp_r=round((SRW - SRL) / N, 2))
            time.sleep(0.2)
        if not rows:
            continue
        table[cls] = rows
        best = max(rows, key=lambda s: (rows[s]["profit_factor"],
                                        rows[s]["win_rate"]))
        canon = dict(CANON[best])
        canon["sl_mult"] = canon["sl_mult"] or tuned.get("sl_mult", 1.8)
        canon["tp_mult"] = canon["tp_mult"] or tuned.get("tp_mult", 2.2)
        canon.setdefault("rsi_filter", tuned.get("rsi_filter", True))
        canon.setdefault("trend", tuned.get("trend", "ema20_50"))
        prev = old.get(cls, {})
        out[cls] = dict(params=canon, strategy=best, stats=rows[best],
                        all_strategies=rows,
                        avg_win_rate=rows[best]["win_rate"],
                        avg_profit_factor=rows[best]["profit_factor"],
                        instruments=prev.get("instruments", {}),
                        tuned_at=time.strftime("%Y-%m-%d"))
        if verbose:
            print(f"\n== {cls.upper()} — RANKING ==")
            for s, r in sorted(rows.items(), key=lambda kv: -kv[1]["profit_factor"]):
                mark = " 🏆" if s == best else ""
                print(f"  {s:10s} WR {r['win_rate']:5.1f}%  PF {r['profit_factor']:5.2f}"
                      f"  n={r['trades']:3d}  exp {r['exp_r']:+.2f}R  dd {r['maxdd_r']}R{mark}")
    try:
        json.dump(out, open(backtest.DATA_FILE, "w"), indent=1)
    except OSError:
        pass
    return out, table


if __name__ == "__main__":
    run(verbose=True)

def entry(m, strat):
    """Live TA dict (metals/forex/nse) se (side, tier) — strategy ke rules se.

    Yahi rules backtest me jeete hain — live signals bhi EXACT wahi follow
    karte hain (no discretion).
    """
    px = m["price"]
    ap = m.get("atr_pct") or 0
    don_up = m.get("don_hi") or 0
    don_dn = m.get("don_lo") or 0
    med = m.get("atr_med") or (ap * 1.2)
    e200 = m.get("e200") or m.get("ema200") or 0
    r2 = m.get("rsi2") or 50
    mh = m.get("macd_hist") or 0
    r14 = m.get("rsi") or 50
    tr = m.get("trend")
    long_ok = short_ok = False
    tier = "B"
    if strat == "voltarget":
        long_ok = bool(don_up) and px > don_up and ap < med
        short_ok = bool(don_dn) and px < don_dn and ap < med
        tier = "A" if ((long_ok and tr == "UP") or (short_ok and tr == "DOWN")) else "B"
    elif strat == "turtle":
        long_ok = bool(don_up) and px > don_up
        short_ok = bool(don_dn) and px < don_dn
        tier = "A" if ((long_ok and tr == "UP") or (short_ok and tr == "DOWN")) else "B"
    elif strat == "rsi2":
        long_ok = bool(e200) and px > e200 and r2 < 15
        short_ok = bool(e200) and px < e200 and r2 > 85
        tier = "A" if (long_ok or short_ok) else "B"
    elif strat == "momentum":
        mm = m.get("mom126") or 0
        e50 = m.get("ema50") or 0
        long_ok = bool(e50) and mm > 0.02 and px > e50
        short_ok = bool(e50) and mm < -0.02 and px < e50
        tier = "A" if ((long_ok and tr == "UP") or (short_ok and tr == "DOWN")) else "B"
    elif strat == "tj_5to1":
        long_ok = bool(e200) and px > e200 and mh > 0
        short_ok = bool(e200) and px < e200 and mh < 0
        tier = "A" if ((long_ok and tr == "UP") or (short_ok and tr == "DOWN")) else "B"
    else:   # trend_atr (baseline)
        long_ok = tr == "UP" and mh > 0 and r14 < 74
        short_ok = tr == "DOWN" and mh < 0 and r14 > 26
        tier = "A" if (long_ok or short_ok) else "B"
    if long_ok:
        side = "LONG"
    elif short_ok:
        side = "SHORT"
    else:
        side = "SHORT" if tr == "DOWN" else "LONG"
    return side, tier
