"""TRAIL-COP v16.3 (user-requested) — har-tick trade monitor.

Har track-tick (5-min cron, loop me 60s) pe har OPEN trade ka audit:
- SL_MODIFY      : T1 ke baad SL->entry (breakeven lock); +1.2R ke baad profit-trail
- EMERGENCY_CLOSE: -0.8R fast-slide zone = SL-hit se PEHLE clean exit signal
- TP_MODIFY      : +2R momentum me TP2 ko 15% aage

Har alert PURANE trade-message ka reference deta hai:
Telegram reply-to link (agar msg_id captured) + text reference fallback.
"""
import time

import storage


def evaluate(s):
    """Open signal ka audit -> [(action, level, reason)] (ya [])."""
    if s["status"] not in ("OPEN", "T1_HIT"):
        return []
    rd = abs(s["entry"] - s["sl"])
    if not rd:
        return []
    side = 1 if s.get("side", "LONG") == "LONG" else -1
    px = s.get("last_price") or s["entry"]
    r = side * (px - s["entry"]) / rd
    now = time.time()
    best = max(s.get("cop_best_r", r), r)
    s["cop_best_r"] = best
    s["cop_prev_px"] = px
    fired = s.get("cop_fired") or {}
    recs = []

    def fire(key, ttl_h, action, level, why):
        if now - fired.get(key, 0) < ttl_h * 3600:
            return
        fired[key] = now
        recs.append((action, level, why))

    # 1) T1 ke baad: SL entry pe (breakeven lock — trade risk-free)
    if s.get("hit_t1") and abs(s["sl"] - s["entry"]) / rd > 0.02:
        s["sl"] = s["entry"]
        fire("be", 9999, "SL_MODIFY", s["entry"],
             "\U0001f512 T1 hit chuka — SL ab ENTRY pe shift (trade risk-FREE)")
    # 2) Profit-trail: +1.2R dekha tha, ab 0.4R tak gira — lock karo
    if best >= 1.2 and r <= 0.4 and r > -0.2:
        new_sl = s["entry"] + side * 0.4 * rd
        fire("trail", 6, "SL_MODIFY", new_sl,
             f"\U0001f4c8 +{best:.1f}R tha, ab {r:+.2f}R — profit-lock trail, "
             f"naya SL {new_sl:.6g}")
    # 3) Emergency: -0.8R zone = SL-hit se pehle clean-exit
    if -0.95 <= r <= -0.80 and not s.get("hit_t1"):
        fire("emg", 4, "EMERGENCY_CLOSE", px,
             "\U0001f6a8 fast-slide -0.8R zone — SL-hit se PEHLE exit karo "
             "(slippage bachao)")
    # 4) TP-extend: 2R+ strong momentum
    if r >= 2.0:
        t2n = s["t2"] * (1.15 if side == 1 else 0.85)
        fire("tpx", 24, "TP_MODIFY", t2n,
             f"\U0001f680 +{r:.1f}R momentum — TP2 aage {t2n:.6g} pe shift karo")
    s["cop_fired"] = fired
    return recs


def _ref_line(s):
    mid = s.get("msg_id")
    if mid:
        # public channel username pe link; numeric-fallback text ref bhi
        return ("\n\u21a9\ufe0f <b>Ref:</b> ye usi trade ka update hai — "
                f"{s['sym']} {s.get('side', 'LONG')} @ {s.get('ts', '')} "
                f"(msg #{mid})")
    return ("\n\u21a9\ufe0f <b>Ref:</b> trade card \u2014 "
            f"{s['sym']} {s.get('side', 'LONG')} @ {s.get('ts', '')} "
            f"({s.get('kind', 'SPOT')})")


def publish(bot, s, recs):
    emo = {"SL_MODIFY": "\U0001f6e1\ufe0f", "EMERGENCY_CLOSE": "\U0001f6a8",
           "TP_MODIFY": "\U0001f3af"}
    for action, level, why in recs:
        e = emo.get(action, "\u26a1")
        txt = (f"{e} <b>TRAIL-COP: {action}</b>\n"
               f"<b>{s['sym']}</b> {s.get('side', 'LONG')} "
               f"({s.get('kind', 'SPOT')})\n"
               f"{why}\n"
               + ("\U0001f449 Market pe turant ACTION lo \u2014 position "
                  "close karo" if action == "EMERGENCY_CLOSE"
                  else "\U0001f449 Trading app me level update karo")
               + _ref_line(s))
        kw = {}
        mid = s.get("msg_id")
        cid = bot.channel_id() or "-1004480785880"
        if mid:
            kw["reply_to_message_id"] = mid
        resp = bot._api("sendMessage", data=dict(
            chat_id=cid, text=txt, parse_mode="HTML", **kw))
        if not (resp and resp.get("ok")) and kw:
            kw.pop("reply_to_message_id", None)
            bot._api("sendMessage", data=dict(
                chat_id=cid, text=txt, parse_mode="HTML", **kw))
        for admin in storage.get_state().get("admins", []):
            try:
                bot.send(admin, txt)
            except Exception:
                pass


def step(bot, open_sigs):
    """Track-tick: sabhi open trades ka audit + persist + alerts."""
    import signals as _sg
    for s in open_sigs:
        try:
            recs = evaluate(s)
            if recs:
                _sg.persist_cop(s)
                publish(bot, s, recs)
        except Exception:
            continue
