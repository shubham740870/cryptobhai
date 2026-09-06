"""Config — .env file se ya environment variables se settings."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")
CACHE_DIR = os.path.join(DATA_DIR, "cache")


def _load_env():
    """Simple .env parser (python-dotenv ki zaroorat nahi)."""
    path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


_load_env()

# ---- Telegram ----
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()

# ---- Channel (paid community) ----
# Channel ID (-100...) ya @username — /setchannel command se bhi set ho sakta hai
CHANNEL_ID = os.environ.get("CHANNEL_ID", "").strip()
# Comma-separated admin Telegram user IDs (invite links banane ke liye)
ADMIN_IDS = [x.strip() for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]
# Tumhari personal chat (videos/content yahan bhi aayenge IG/YT ke liye)
CHAT_ID = os.environ.get("CHAT_ID", "").strip()

# ---- CoinGecko (optional demo key = higher rate limit, free me milti hai) ----
COINGECKO_KEY = os.environ.get("COINGECKO_KEY", "").strip()

# ---- Schedule (IST) ----
DAILY_HOUR_IST = int(os.environ.get("DAILY_HOUR_IST", "9"))    # roz subah 9 baje
WEEKLY_DAY_ISO = int(os.environ.get("WEEKLY_DAY_ISO", "1"))    # 1 = Monday
WEEKLY_HOUR_IST = int(os.environ.get("WEEKLY_HOUR_IST", "9"))

# ---- Analysis tuning ----
DEEP_DIVE_COUNT = {"safe": 8, "balanced": 12, "aggressive": 15}

RISK_CONFIG = {
    # mcap floor (USD) aur universe size per risk mode
    "safe":       {"mcap_floor": 5_000_000_000,  "pages": 1, "per_page": 30,
                   "buy_min": 62, "strong_buy": 74},
    "balanced":   {"mcap_floor": 100_000_000,    "pages": 1, "per_page": 100,
                   "buy_min": 58, "strong_buy": 70},
    "aggressive": {"mcap_floor": 10_000_000,     "pages": 2, "per_page": 250,
                   "buy_min": 55, "strong_buy": 68},
}

# Stablecoins / wrapped tokens jo analysis me nahi chahiye
STABLES = {"usdt", "usdc", "dai", "fdusd", "usde", "tusd", "usds", "pyusd",
           "usd1", "usdg", "frax", "lusd", "gusd", "usdp", "eurt", "usdy",
           "busd", "crvusd", "usdx", "usdb", "rlusd", "usdtb", "usd0"}
WRAPPED = {"wbtc", "weth", "wbnb", "wmatic", "steth", "wsteth", "reth",
           "cbeth", "cbbtc", "cbbtc", "rseth", "weeth", "ezeth", "meth",
           "oseth", "frxeth", "sfrxeth", "sweth", "swell", "jitosol",
           "msol", "bnsol", "jupsol", "lstsol", "wbeth", "wstusr", "lbtc",
           "solvbtc", "clbtc", "stbtc", "tbtc", "hbtc", "renbtc", "sbtc"}

DEFAULT_MODE = "aggressive"

for _d in (DATA_DIR, REPORTS_DIR, CACHE_DIR):
    os.makedirs(_d, exist_ok=True)
