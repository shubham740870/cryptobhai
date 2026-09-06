"""Technical indicators — pure python, no external deps (pandas/numpy ki zaroorat nahi)."""
from datetime import datetime, timezone


def sma(values, period):
    """Simple Moving Average — None-padded list, input ke same length."""
    out = [None] * len(values)
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= period:
            s -= values[i - period]
        if i >= period - 1:
            out[i] = s / period
    return out


def ema(values, period):
    """Exponential Moving Average — None-padded."""
    out = [None] * len(values)
    if len(values) < period:
        return out
    k = 2.0 / (period + 1)
    e = sum(values[:period]) / period
    out[period - 1] = e
    for i in range(period, len(values)):
        e = values[i] * k + e * (1 - k)
        out[i] = e
    return out


def rsi(closes, period=14):
    """Wilder's RSI — None-padded list."""
    out = [None] * len(closes)
    if len(closes) <= period:
        return out
    gains = losses = 0.0
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        if d >= 0:
            gains += d
        else:
            losses -= d
    avg_g = gains / period
    avg_l = losses / period
    out[period] = 100.0 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l)
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        g = d if d > 0 else 0.0
        l = -d if d < 0 else 0.0
        avg_g = (avg_g * (period - 1) + g) / period
        avg_l = (avg_l * (period - 1) + l) / period
        out[i] = 100.0 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l)
    return out


def macd(closes, fast=12, slow=26, signal=9):
    """MACD line, signal line, histogram — None-padded."""
    ef, es = ema(closes, fast), ema(closes, slow)
    line = [None if (ef[i] is None or es[i] is None) else ef[i] - es[i]
            for i in range(len(closes))]
    valid = [v for v in line if v is not None]
    sig_valid = ema(valid, signal)
    sig = [None] * len(closes)
    j = 0
    for i in range(len(closes)):
        if line[i] is not None:
            sig[i] = sig_valid[j]
            j += 1
    hist = [None if (line[i] is None or sig[i] is None) else line[i] - sig[i]
            for i in range(len(closes))]
    return line, sig, hist


def true_ranges(highs, lows, closes):
    trs = []
    for i in range(len(closes)):
        if i == 0:
            trs.append(highs[i] - lows[i])
        else:
            trs.append(max(highs[i] - lows[i],
                           abs(highs[i] - closes[i - 1]),
                           abs(lows[i] - closes[i - 1])))
    return trs


def atr(highs, lows, closes, period=14):
    """Wilder's ATR — None-padded."""
    out = [None] * len(closes)
    trs = true_ranges(highs, lows, closes)
    if len(trs) <= period:
        return out
    a = sum(trs[1:period + 1]) / period
    out[period] = a
    for i in range(period + 1, len(trs)):
        a = (a * (period - 1) + trs[i]) / period
        out[i] = a
    return out


def bollinger(closes, period=20, ndev=2.0):
    """(upper, mid, lower) — None-padded."""
    n = len(closes)
    upper, mid, lower = [None] * n, [None] * n, [None] * n
    for i in range(period - 1, n):
        w = closes[i - period + 1:i + 1]
        m = sum(w) / period
        var = sum((x - m) ** 2 for x in w) / period
        sd = var ** 0.5
        mid[i] = m
        upper[i] = m + ndev * sd
        lower[i] = m - ndev * sd
    return upper, mid, lower


def last_valid(series):
    """List me last non-None value."""
    for v in reversed(series):
        if v is not None:
            return v
    return None


def resample_daily(points):
    """CoinGecko hourly [ts, price] points -> daily OHLCV.

    Returns (dates, opens, highs, lows, closes, vols).
    Volume points [ts, vol] — 24h rolling volume, din ka last lete hain.
    """
    days = {}
    for ts, price in points:
        d = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date()
        days.setdefault(d, []).append(price)
    vol_by_day = {}
    # volume points bhi pass ho sakte hain (optional)
    sorted_dates = sorted(days.keys())
    dates, opens, highs, lows, closes = [], [], [], [], []
    for d in sorted_dates:
        p = days[d]
        dates.append(d.isoformat())
        opens.append(p[0])
        highs.append(max(p))
        lows.append(min(p))
        closes.append(p[-1])
    return dates, opens, highs, lows, closes


def linreg_slope(values):
    """Simple linear regression slope (normalized by mean, % per step)."""
    n = len(values)
    if n < 2:
        return 0.0
    mx = (n - 1) / 2.0
    my = sum(values) / n
    if my == 0:
        return 0.0
    num = sum((i - mx) * (v - my) for i, v in enumerate(values))
    den = sum((i - mx) ** 2 for i in range(n))
    slope = num / den
    return slope / my * 100  # % change per step relative to mean
