"""Chart generation — trade plan + P&L charts (matplotlib, dark crypto theme).

  - trade_chart()     : 90d price + SMA + entry zone + targets + stop-loss
  - result_chart()    : signal ke baad ka price move + live P&L (result posts)
  - portfolio_chart() : holdings ka P&L bar chart
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from matplotlib.patches import Rectangle  # noqa: E402

from indicators import resample_daily, sma  # noqa: E402

# ---- dark theme ----
BG = "#0d1117"
PANEL = "#0d1117"
FG = "#e6edf3"
GRID = "#21262d"
GREEN = "#26a641"
RED = "#f85149"
BLUE = "#58a6ff"
ORANGE = "#d29922"
PURPLE = "#bc8cff"
GRAY = "#8b949e"

import config  # noqa: E402
CHARTS_DIR = os.path.join(config.REPORTS_DIR, "charts")
os.makedirs(CHARTS_DIR, exist_ok=True)


def _style_ax(ax):
    fig = ax.get_figure()
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(PANEL)
    ax.tick_params(colors=GRAY, labelsize=9)
    for sp in ax.spines.values():
        sp.set_color(GRID)
    ax.grid(True, color=GRID, lw=0.6, alpha=0.7)
    ax.title.set_color(FG)
    ax.title.set_fontsize(13)
    ax.title.set_fontweight("bold")


def _price_fmt(p):
    if p >= 1000:
        return f"${p:,.0f}"
    if p >= 1:
        return f"${p:,.2f}"
    if p >= 0.01:
        return f"${p:.4f}"
    return f"${p:.6f}"


def _yfmt(v):
    return _price_fmt(v) if v < 100000 else f"${v/1000:,.0f}k"


def trade_chart(a, hist, path=None):
    """BUY recommendation ka chart: price + SMA20/50 + entry/targets/SL."""
    prices = hist.get("prices") or []
    dates, _, _, _, closes = resample_daily(prices)
    closes = closes[-90:]
    if len(closes) < 10:
        return None
    s20 = sma(closes, 20)
    s50 = sma(closes, 50)
    lo, hi = a["entry"]
    side = a.get("side", "LONG")
    n = len(closes)
    x = list(range(n))

    fig, ax = plt.subplots(figsize=(11.5, 6.8), dpi=105)
    _style_ax(ax)

    ax.plot(x, closes, color=FG, lw=1.9, label="Price", zorder=5)
    ax.plot(x, s20, color=ORANGE, lw=1.2, alpha=0.9, label="SMA 20", zorder=4)
    ax.plot(x, s50, color=PURPLE, lw=1.2, alpha=0.9, label="SMA 50", zorder=4)

    # entry zone (green band)
    ax.axhspan(lo, hi, color=GREEN, alpha=0.16, zorder=1)
    # targets / SL
    ax.axhline(a["t1"], color=GREEN, ls="--", lw=1.3, alpha=0.95, zorder=2)
    ax.axhline(a["t2"], color=GREEN, ls="--", lw=1.3, alpha=0.6, zorder=2)
    ax.axhline(a["sl"], color=RED, ls="--", lw=1.4, alpha=0.95, zorder=2)
    # current price
    ax.axhline(a["price"], color=BLUE, ls=":", lw=1.2, alpha=0.9, zorder=3)

    # y-range: SHORT me SL upar + targets neeche — sab chart me rakho
    all_lvls = [min(closes), max(closes), a["sl"], a["t2"], lo, hi]
    ymin = min(all_lvls) * 0.97
    ymax = max(all_lvls) * 1.03
    span = ymax - ymin

    # right-side labels
    xlab = n + n * 0.015
    fs = 9.5
    now_y = a["price"]
    entry_y = (lo + hi) / 2
    if side == "SHORT" and abs(entry_y - now_y) < span * 0.06:
        now_y -= span * 0.045
        entry_y += span * 0.02
    ax.text(xlab, a["t2"], f"  TARGET 2  {_price_fmt(a['t2'])} (+{(a['t2']/a['price']-1)*100:.0f}%)",
            color=GREEN, fontsize=fs, va="center", fontweight="bold")
    ax.text(xlab, a["t1"], f"  TARGET 1  {_price_fmt(a['t1'])} (+{(a['t1']/a['price']-1)*100:.0f}%)",
            color=GREEN, fontsize=fs, va="center", fontweight="bold")
    ax.text(xlab, entry_y, f"  ENTRY ZONE\n  {_price_fmt(lo)} – {_price_fmt(hi)}",
            color="#7ee787", fontsize=fs, va="center", fontweight="bold")
    ax.text(xlab, a["sl"], f"  STOP-LOSS  {_price_fmt(a['sl'])} ({-a['risk_pct']:.0f}%)",
            color=RED, fontsize=fs, va="center", fontweight="bold")
    ax.text(xlab, now_y, f"  NOW  {_price_fmt(a['price'])}",
            color=BLUE, fontsize=fs, va="center", fontweight="bold")

    ax.set_ylim(ymin, ymax)
    ax.set_xlim(0, n * 1.34)

    verdict = a["verdict"]
    score = a["score"]
    ax.set_title(f"{a['name']} ({a['symbol']}/USDT)   |   {verdict}  •  Score {score:.0f}/100",
                 pad=14)
    ax.set_ylabel("Price (USDT)", color=GRAY, fontsize=9)
    leg = ax.legend(loc="upper left", fontsize=9, facecolor=PANEL,
                    edgecolor=GRID, framealpha=0.9)
    for t in leg.get_texts():
        t.set_color(FG)
    fig.text(0.99, 0.01, "CryptoBhai • educational only, not financial advice",
             color=GRAY, fontsize=7.5, ha="right")

    if path is None:
        path = os.path.join(CHARTS_DIR, f"{a['symbol']}_{a['id'][:10]}.png")
    fig.savefig(path, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    return path


def result_chart(sig, hist, path=None):
    """Closed/updated signal ka P&L chart — signal date se ab tak."""
    prices = hist.get("prices") or []
    dates, _, _, _, closes = resample_daily(prices)
    start = sig["ts"][:10]  # YYYY-MM-DD
    pts = [(d, c) for d, c in zip(dates, closes) if d >= start]
    if len(pts) < 3:
        pts = [(d, c) for d, c in zip(dates, closes)][-30:]
    ds = [d[5:] for d, _ in pts]  # MM-DD
    cs = [c for _, c in pts]
    n = len(cs)
    x = list(range(n))

    entry = sig["entry"]
    side = sig.get("side", "LONG")
    pnl = ((cs[-1] - entry) if side == "LONG" else (entry - cs[-1])) / entry * 100
    win = pnl >= 0
    col = GREEN if win else RED

    fig, ax = plt.subplots(figsize=(10.5, 6), dpi=105)
    _style_ax(ax)
    ax.fill_between(x, cs, min(min(cs), sig["sl"]) * 0.995, color=col, alpha=0.10)
    ax.plot(x, cs, color=FG, lw=2, zorder=5)
    ax.scatter([n - 1], [cs[-1]], color=col, s=60, zorder=6)

    ax.axhline(entry, color=BLUE, ls=":", lw=1.3, alpha=0.9)
    ax.axhline(sig["t1"], color=GREEN, ls="--", lw=1, alpha=0.6)
    ax.axhline(sig["sl"], color=RED, ls="--", lw=1, alpha=0.6)
    xlab = n + n * 0.02
    ax.text(xlab, entry, f"  ENTRY {_price_fmt(entry)}", color=BLUE, fontsize=9, va="center", fontweight="bold")
    ax.text(xlab, sig["t1"], f"  T1 {_price_fmt(sig['t1'])}", color=GREEN, fontsize=9, va="center")
    ax.text(xlab, sig["sl"], f"  SL {_price_fmt(sig['sl'])}", color=RED, fontsize=9, va="center")
    ax.text(xlab, cs[-1], f"  {_price_fmt(cs[-1])}", color=col, fontsize=9, va="center", fontweight="bold")

    ax.set_xlim(0, n * 1.30)
    ymin = min(min(cs), sig["sl"]) * 0.98
    ymax = max(max(cs), sig["t1"]) * 1.02
    ax.set_ylim(ymin, ymax)
    lev = f" {sig['lev']}x" if sig.get("lev") else ""
    side_tag = side + lev if sig.get("kind") == "FUTURES" else ""
    title = f"{sig['name']} ({sig['sym']}/USDT)"
    if side_tag:
        title += f"   |   {side_tag}"
    title += f"   |   P&L: {pnl:+.1f}%"
    ax.set_title(title, pad=14)
    ax.set_ylabel("Price (USDT)", color=GRAY, fontsize=9)
    step = max(1, n // 8)
    ax.set_xticks(x[::step])
    ax.set_xticklabels(ds[::step], rotation=0)
    fig.text(0.99, 0.01, "CryptoBhai • educational only, not financial advice",
             color=GRAY, fontsize=7.5, ha="right")

    if path is None:
        path = os.path.join(CHARTS_DIR, f"result_{sig['sym']}.png")
    fig.savefig(path, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    return path


def portfolio_chart(holdings, path=None):
    """Holdings ka P&L bar chart."""
    rows = [(h["sym"], h["pnl"], h["qty"] * h["price"]) for h in holdings]
    rows.sort(key=lambda r: r[1])
    syms = [r[0] for r in rows]
    pnls = [r[1] for r in rows]
    cols = [GREEN if p >= 0 else RED for p in pnls]

    fig, ax = plt.subplots(figsize=(9, max(3.2, 0.62 * len(rows) + 1.6)), dpi=105)
    _style_ax(ax)
    bars = ax.barh(syms, pnls, color=cols, alpha=0.88, height=0.6, zorder=3)
    ax.axvline(0, color=FG, lw=1)
    for b, p, val in zip(bars, pnls, [r[2] for r in rows]):
        xpos = p + (max(pnls + [1]) * 0.02 if p >= 0 else -max(pnls + [1]) * 0.02)
        ax.text(xpos, b.get_y() + b.get_height() / 2,
                f"{p:+.1f}%  ({_price_fmt(val)})",
                va="center", ha="left" if p >= 0 else "right",
                color=FG, fontsize=9.5, fontweight="bold")
    ax.set_title("Portfolio P&L (live)", pad=14)
    ax.set_xlabel("Profit / Loss %", color=GRAY, fontsize=9)
    xmin, xmax = ax.get_xlim()
    ax.set_xlim(xmin - (xmax - xmin) * 0.28, xmax + (xmax - xmin) * 0.28)
    fig.text(0.99, 0.01, "CryptoBhai • educational only", color=GRAY,
             fontsize=7.5, ha="right")
    if path is None:
        path = os.path.join(CHARTS_DIR, "portfolio.png")
    fig.savefig(path, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    return path

def _sr_zones(highs, lows, price, lookback=60):
    """Swing highs/lows se support/resistance zones (clustered)."""
    hs, ls = highs[-lookback:], lows[-lookback:]
    w = 2
    res_pts, sup_pts = [], []
    for i in range(w, len(hs) - w):
        if hs[i] >= max(hs[i - w:i + w + 1]):
            res_pts.append(hs[i])
        if ls[i] <= min(ls[i - w:i + w + 1]):
            sup_pts.append(ls[i])

    def cluster(pts, tol=0.012):
        if not pts:
            return []
        pts = sorted(pts)
        groups, cur = [], [pts[0]]
        for p in pts[1:]:
            if p <= cur[-1] * (1 + tol):
                cur.append(p)
            else:
                groups.append(cur)
                cur = [p]
        groups.append(cur)
        return [sum(g) / len(g) for g in groups]

    res = [z for z in cluster(res_pts) if z > price * 1.003]
    sup = [z for z in cluster(sup_pts) if z < price * 0.997]
    res.sort(key=lambda z: abs(z - price))
    sup.sort(key=lambda z: abs(z - price))
    return sup[:2], res[:2]


def candle_chart(a, hist, path=None):
    """TradingView-style candle chart: S/R zones + entry/TP/SL + projection."""
    prices = hist.get("prices") or []
    dates, opens, highs, lows, closes = resample_daily(prices)
    N = 70
    o, h, l, c = opens[-N:], highs[-N:], lows[-N:], closes[-N:]
    dd = [d[5:] for d in dates[-N:]]
    n = len(c)
    if n < 10:
        return None
    side = a.get("side", "LONG")
    price, t1, t2, sl = a["price"], a["t1"], a["t2"], a["sl"]
    lo_e, hi_e = a["entry"]
    sup, res = _sr_zones(h, l, price)

    fig = plt.figure(figsize=(12.8, 7.6), dpi=105)
    ax = fig.add_axes([0.055, 0.09, 0.63, 0.82])
    _style_ax(ax)

    # candles
    span = max(c) - min(c)
    for i in range(n):
        col = GREEN if c[i] >= o[i] else RED
        ax.plot([i, i], [l[i], h[i]], color=col, lw=1.1, zorder=4)
        b_lo, b_hi = min(o[i], c[i]), max(o[i], c[i])
        bh = max(b_hi - b_lo, span * 0.001)
        ax.add_patch(Rectangle((i - 0.33, b_lo), 0.66, bh,
                               facecolor=col, edgecolor=col, zorder=5))

    # volume bars (background, chhote)
    vols = hist.get("total_volumes") or []
    vol_by_day = {}
    for ts, v in vols:
        vol_by_day[ts] = v  # last hourly point of each window roughly
    if vols:
        vv = [v for _, v in vols[-n * 24:]]
        step = max(1, len(vv) // n)
        dv = [sum(vv[j:j + step]) for j in range(0, len(vv), step)][:n]
        if len(dv) < n:
            dv = dv + [dv[-1]] * (n - len(dv))
        ax2 = ax.twinx()
        ax2.bar(range(n), dv, color=[GREEN if c[i] >= o[i] else RED for i in range(n)],
                alpha=0.18, width=0.66, zorder=2)
        ax2.set_ylim(0, max(dv) * 5 if dv else 1)
        ax2.axis("off")

    # S/R zones
    all_lvls = [min(l), max(h), sl, t2, lo_e, hi_e]
    for z in sup:
        all_lvls += [z * 0.99, z * 1.01]
    for z in res:
        all_lvls += [z * 0.99, z * 1.01]
    ymin, ymax = min(all_lvls) * 0.985, max(all_lvls) * 1.015
    span = ymax - ymin

    for z in sup:
        ax.axhspan(z * 0.99, z * 1.01, color=BLUE, alpha=0.13, zorder=1)
    for z in res:
        ax.axhspan(z * 0.99, z * 1.01, color=ORANGE, alpha=0.15, zorder=1)

    # trade levels
    ax.axhspan(min(lo_e, hi_e), max(lo_e, hi_e), color=GREEN, alpha=0.18, zorder=2)
    ax.axhline(t1, color=GREEN, ls="--", lw=1.3, zorder=2)
    ax.axhline(t2, color=GREEN, ls="--", lw=1.3, alpha=0.7, zorder=2)
    ax.axhline(sl, color=RED, ls="--", lw=1.4, zorder=2)
    ax.axhline(price, color=BLUE, ls=":", lw=1.3, zorder=3)

    xlab = n + n * 0.012
    fs = 9
    def lbl(y, s, col, fw="bold"):
        ax.text(xlab, y, s, color=col, fontsize=fs, va="center", fontweight=fw)

    # S/R labels (band centers, chhote)
    for z in sup:
        lbl(z, f"  SUPPORT {_price_fmt(z)}", BLUE, "bold")
    for z in res:
        lbl(z, f"  RESIST {_price_fmt(z)}", ORANGE, "bold")
    lbl(t2, f"  TARGET 2  {_price_fmt(t2)} ({(t2/price-1)*100:+.0f}%)", GREEN)
    lbl(t1, f"  TARGET 1  {_price_fmt(t1)} ({(t1/price-1)*100:+.0f}%)", GREEN)
    lbl((lo_e + hi_e) / 2, f"  ENTRY  {_price_fmt(lo_e)}-{_price_fmt(hi_e)}", "#7ee787")
    lbl(sl, f"  STOP-LOSS  {_price_fmt(sl)} ({(sl/price-1)*100:+.0f}%)", RED)
    lbl(price, f"  NOW  {_price_fmt(price)}", BLUE)
    # NOW label overlap avoid (entry ke paas ho to thoda neeche)
    if abs(price - (lo_e + hi_e) / 2) < span * 0.03:
        ax.texts[-1].set_position((xlab, price - span * 0.035))

    # projection arrow — "kaha tak ja sakta hai"
    arc = -0.22 if side == "LONG" else 0.22
    arrow_end_y = t2 + (span * 0.045 if side == "LONG" else -span * 0.045)
    ax.annotate("", xy=(n + n * 0.09, arrow_end_y), xytext=(n - 1, price),
                arrowprops=dict(arrowstyle="->", color=GREEN if side == "LONG" else RED,
                                lw=1.8, ls="--", connectionstyle=f"arc3,rad={arc}"),
                zorder=6)
    ax.text(n + n * 0.09, arrow_end_y, f"  EXPECTED MOVE {(t2/price-1)*100:+.0f}%",
            color=GREEN if side == "LONG" else RED, fontsize=fs,
            va="center", fontweight="bold", style="italic")

    ax.set_ylim(ymin, ymax)
    ax.set_xlim(0, n * 1.30)
    step = max(1, n // 8)
    ax.set_xticks(range(0, n, step))
    ax.set_xticklabels([dd[i] for i in range(0, n, step)], fontsize=8)

    lev = f" {a['lev']}x" if a.get("lev") else ""
    mode = "FUTURES " if a.get("kind") == "FUTURES" or a.get("lev") else ""
    ax.set_title(f"{a['name']} ({a['symbol']}/USDT) · 1D   |   "
                 f"{mode}{side}{lev}  ·  Score {a['score']:.0f}/100", pad=14)
    ax.set_ylabel("Price (USDT)", color=GRAY, fontsize=9)
    leg = ax.legend(handles=[plt.Line2D([], [], color=FG, lw=2, label="Price"),
                             plt.Line2D([], [], color=ORANGE, lw=2, label="SMA20/Resistance"),
                             plt.Line2D([], [], color=BLUE, lw=2, label="Support")],
                    loc="upper left", fontsize=8, facecolor=PANEL, edgecolor=GRID)
    for t in leg.get_texts():
        t.set_color(FG)
    fig.text(0.99, 0.012, "CryptoBhai AI · educational only, not financial advice",
             color=GRAY, fontsize=8, ha="right")

    if path is None:
        path = os.path.join(CHARTS_DIR, f"candle_{a['symbol']}_{side}.png")
    fig.savefig(path, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    return path
