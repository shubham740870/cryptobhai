"""JSON persistence — chats, portfolio, watchlist, settings + disk cache."""
import glob
import json
import os
import threading
import time

import config

_lock = threading.Lock()


def _path(name):
    return os.path.join(config.DATA_DIR, name)


def load_json(name, default):
    try:
        with open(_path(name), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(name, data):
    with _lock:
        tmp = _path(name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, _path(name))


# ---------- chats ----------
def get_chats():
    return load_json("chats.json", {})


def register_chat(chat_id, info):
    chats = get_chats()
    chats[str(chat_id)] = dict(info, joined=time.time())
    save_json("chats.json", chats)


def all_chat_ids():
    return list(get_chats().keys())


# ---------- per-chat user data (portfolio / watchlist / settings) ----------
def _udata(chat_id):
    return load_json(f"user_{chat_id}.json", {"portfolio": {}, "watchlist": [],
                                              "mode": None})


def save_udata(chat_id, data):
    save_json(f"user_{chat_id}.json", data)


def get_portfolio(chat_id):
    return _udata(chat_id)["portfolio"]


def add_holding(chat_id, symbol, qty, buy_price, coin_id, name):
    d = _udata(chat_id)
    d["portfolio"][symbol.upper()] = {"qty": qty, "buy": buy_price,
                                      "id": coin_id, "name": name,
                                      "added": time.time()}
    save_udata(chat_id, d)


def remove_holding(chat_id, symbol):
    d = _udata(chat_id)
    s = symbol.upper()
    if s in d["portfolio"]:
        del d["portfolio"][s]
        save_udata(chat_id, d)
        return True
    return False


def get_watchlist(chat_id):
    return _udata(chat_id)["watchlist"]


def watch(chat_id, symbol, coin_id, name):
    d = _udata(chat_id)
    s = symbol.upper()
    if not any(w["symbol"] == s for w in d["watchlist"]):
        d["watchlist"].append({"symbol": s, "id": coin_id, "name": name})
        save_udata(chat_id, d)
        return True
    return False


def unwatch(chat_id, symbol):
    d = _udata(chat_id)
    s = symbol.upper()
    before = len(d["watchlist"])
    d["watchlist"] = [w for w in d["watchlist"] if w["symbol"] != s]
    save_udata(chat_id, d)
    return len(d["watchlist"]) < before


def get_mode(chat_id):
    return _udata(chat_id).get("mode")


def set_mode(chat_id, mode):
    d = _udata(chat_id)
    d["mode"] = mode
    save_udata(chat_id, d)


# ---------- scheduler state ----------
def get_state():
    return load_json("state.json", {})


def set_state(key, value):
    state = get_state()
    state[key] = value
    save_json("state.json", state)


# ---------- disk cache (TTL) ----------
def cache_get(key, ttl):
    path = os.path.join(config.CACHE_DIR, key + ".json")
    try:
        if time.time() - os.path.getmtime(path) < ttl:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return None


def cache_set(key, data):
    try:
        path = os.path.join(config.CACHE_DIR, key + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except OSError:
        pass


def cache_cleanup(max_age_hours=48):
    cutoff = time.time() - max_age_hours * 3600
    for p in glob.glob(os.path.join(config.CACHE_DIR, "*.json")):
        try:
            if os.path.getmtime(p) < cutoff:
                os.remove(p)
        except OSError:
            pass
