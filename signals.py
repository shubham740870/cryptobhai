"""Signal tracker — SPOT + FUTURES, LONG + SHORT sab ka lifecycle record.

signals.json format:
{
  "list": [ {key, sym, name, id, kind, side, mode, ts, epoch, entry, t1, t2, sl,
             risk_pct, score, lev, status, hit_t1, hit_t2, hit_sl,
             last_price, pnl_pct, result_pct, closed_ts} ],
  "posted": {"SYM_KIND": epoch}
}
Status: OPEN | T1_HIT | CLOSED_TP2 | CLOSED_SL | CLOSED_TIME
"""
import time

import analyzer
import storage

TTL_SIGNAL_DAYS = 30           # 30 din baad time-exit
COOLDOWN = {"SPOT": 6 * 86400, "FUTURES": 3 * 86400}


def _load():
    return storage.load_json("signals.json", {"list": [], "posted": {}})


def _save(d):
    storage.save_json("signals.json", d)


def record_setups(setups, kind="SPOT"):
    """Naye setups record karo (dedupe: same coin+kind open/cooldown me nahi).

    Returns (new_signals, all_open_of_kind)
    """
    d = _load()
    now = time.time()
    new = []
    for a in setups:
        tag = f"{a['symbol']}_{kind}"
        side = a.get("side", "LONG")
        already = any(s["sym"] == a["symbol"] and s.get("kind", "SPOT") == kind
                      and s.get("side", "LONG") == side
                      and s["status"] in ("OPEN", "T1_HIT") for s in d["list"])
        if already:
            continue
        if now - d["posted"].get(tag, 0) < COOLDOWN.get(kind, 6 * 86400):
            continue
        last_change = time.strftime("%Y-%m-%d %H:%M", time.gmtime(now - 300))
        sig = {
            "key": f"{tag}_{int(now)}",
            "last_change": last_change,  # ~last 5-min candle (scanner cadence)
            "sym": a["symbol"], "name": a["name"], "id": a["id"],
            "kind": kind, "side": side, "mode": a.get("mode", "aggressive"),
            "ts": time.strftime("%Y-%m-%d %H:%M IST"), "epoch": now,
            "entry": a["price"],                    # signal waqt ki price
            "entry_lo": a["entry"][0], "entry_hi": a["entry"][1],
            "t1": a["t1"], "t2": a["t2"], "sl": a["sl"],
            "risk_pct": a.get("risk_pct"), "score": a.get("score"),
            "lev": a.get("lev"), "liq": a.get("liq"),
            "confidence": a.get("confidence"),
            "status": "OPEN", "hit_t1": False, "hit_t2": False, "hit_sl": False,
            "last_price": a["price"], "pnl_pct": 0.0,
            "result_pct": None, "closed_ts": None,
        }
        d["list"].append(sig)
        d["posted"][tag] = now
        new.append(sig)
    # cleanup: 60 din purane closed hatao
    cutoff = now - 60 * 86400
    d["list"] = [s for s in d["list"]
                 if s["status"] in ("OPEN", "T1_HIT")
                 or (s.get("closed_ts") or now) > cutoff]
    d["posted"] = {k: t for k, t in d["posted"].items() if now - t < 30 * 86400}
    _save(d)
    open_sigs = [s for s in d["list"] if s["status"] in ("OPEN", "T1_HIT")]
    return new, open_sigs


def get_signals(kind=None):
    sigs = _load()["list"]
    if kind:
        sigs = [s for s in sigs if s.get("kind", "SPOT") == kind]
    return sigs


def check_signals(mode="aggressive"):
    """Open signals live data se update (LONG aur SHORT dono directions).

    Returns (updates, open_signals)
    """
    d = _load()
    now = time.time()
    updates = []
    markets = analyzer.fetch_markets(mode)
    by_id = {c["id"]: c for c in markets}
    changed = False

    for s in d["list"]:
        if s["status"] not in ("OPEN", "T1_HIT"):
            continue
        coin = by_id.get(s["id"])
        price = coin["current_price"] if coin else s["last_price"]
        side = s.get("side", "LONG")
        entry = s["entry"]

        s["last_price"] = price
        pnl = ((price - entry) if side == "LONG" else (entry - price)) / entry * 100
        s["pnl_pct"] = pnl

        # signal date ke baad ka high/low (intraday hits ke liye)
        try:
            hist = analyzer.fetch_history(s["id"], 90)
            pts = hist.get("prices") or []
            since = [pt[1] for pt in pts if pt and pt[0] / 1000 >= s["epoch"] - 86400]
            hi_since = max(since) if since else price
            lo_since = min(since) if since else price
        except Exception:
            hi_since, lo_since = price, price

        def _result(target):
            return ((target - entry) if side == "LONG"
                    else (entry - target)) / entry * 100

        if side == "LONG":
            hit_t1 = hi_since >= s["t1"]
            hit_tp2 = hi_since >= s["t2"]
            hit_sl = lo_since <= s["sl"]
        else:
            hit_t1 = lo_since <= s["t1"]
            hit_tp2 = lo_since <= s["t2"]
            hit_sl = hi_since >= s["sl"]

        if not s["hit_t1"] and hit_t1:
            s["hit_t1"] = True
            if s["status"] == "OPEN":
                s["status"] = "T1_HIT"
            updates.append({"sig": s, "event": "T1_HIT",
                            "pnl_pct": _result(s["t1"])})
            changed = True
        if hit_tp2:
            s["status"] = "CLOSED_TP2"
            s["hit_t2"] = True
            s["result_pct"] = _result(s["t2"])
            s["closed_ts"] = now
            updates.append({"sig": s, "event": "CLOSED_TP2", "pnl_pct": s["result_pct"]})
            changed = True
        elif hit_sl and not s["hit_t1"]:
            s["status"] = "CLOSED_SL"
            s["hit_sl"] = True
            s["result_pct"] = _result(s["sl"])
            s["closed_ts"] = now
            updates.append({"sig": s, "event": "CLOSED_SL", "pnl_pct": s["result_pct"]})
            changed = True
        elif now - s["epoch"] > TTL_SIGNAL_DAYS * 86400:
            s["status"] = "CLOSED_TIME"
            s["result_pct"] = pnl
            s["closed_ts"] = now
            updates.append({"sig": s, "event": "CLOSED_TIME", "pnl_pct": pnl})
            changed = True

    if changed:
        _save(d)
    open_sigs = [s for s in d["list"] if s["status"] in ("OPEN", "T1_HIT")]
    return updates, open_sigs


def performance_summary(kind=None):
    """(sigs, open, closed, wins) — kind filter optional."""
    sigs = sorted(get_signals(kind), key=lambda s: s["epoch"], reverse=True)
    closed = [s for s in sigs if s["status"].startswith("CLOSED")]
    wins = [s for s in closed if (s.get("result_pct") or 0) > 0]
    open_sigs = [s for s in sigs if s["status"] in ("OPEN", "T1_HIT")]
    return sigs, open_sigs, closed, wins

def record_signals(res, kind="SPOT"):
    """Analyzed dicts (weekly/daily picks) ko spot signals me record karo.

    purana naam — agent.py/bot.py ab bhi yahi call karte hain. Analyzed dict
    (verdict/price/risk_pct) ko spot setup me badal ke record_setups ko dete hain.
    """
    if isinstance(res, dict):
        items = list(res.get("buys") or []) + list(res.get("sells") or [])
    else:
        items = list(res or [])
    setups = []
    for a in items:
        if not isinstance(a, dict):
            continue
        v = (a.get("verdict") or "").upper()
        if "BUY" in v:
            side = "LONG"
        elif "SELL" in v:
            side = "SHORT"
        else:
            continue
        px = a.get("price") or 0
        if px <= 0:
            continue
        risk = a.get("risk_pct") or 4.0
        rp = risk / 100.0
        if side == "LONG":
            sl = px * (1 - rp)
            t1 = px * (1 + rp * 1.5)
            t2 = px * (1 + rp * 2.5)
        else:
            sl = px * (1 + rp)
            t1 = px * (1 - rp * 1.5)
            t2 = px * (1 - rp * 2.5)
        setups.append(dict(a, side=side, entry=(px * 0.99, px * 1.01),
                           sl=sl, t1=t1, t2=t2, rr=1.5, lev=1, liq=0,
                           risk_pct=risk, confidence="MEDIUM",
                           verdict=a.get("verdict")))
    if not setups:
        return [], []
    return record_setups([dict(s, kind=kind) for s in setups], kind=kind)
