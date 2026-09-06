"""AI Result Videos — successful trade ka Instagram/YouTube reel (FREE, no paid API).

Kaise banata hai:
  1. matplotlib se 1080x1920 (9:16 reel format) slides render karta hai
  2. gTTS (Google free TTS) se Hinglish voiceover generate karta hai
  3. ffmpeg (system ya imageio-ffmpeg) se sab jodke MP4 banata hai

Ye "AI video" hai: script hamare engine ka, voice AI TTS ki, visuals AI-generated.
Instagram/YouTube pe seedha post karne ke liye ready.
"""
import os
import re
import shutil
import subprocess
import tempfile
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import analyzer  # noqa: E402
import config  # noqa: E402
from indicators import resample_daily  # noqa: E402

try:
    from gtts import gTTS
    HAS_GTTS = True
except ImportError:
    HAS_GTTS = False

# theme (charts.py jaisa)
BG = "#0d1117"
FG = "#e6edf3"
GREEN = "#26a641"
RED = "#f85149"
BLUE = "#58a6ff"
ORANGE = "#d29922"
GRAY = "#8b949e"
GOLD = "#e3b341"

W, H = 10.8, 19.2  # inches @100dpi = 1080x1920


def _ffmpeg():
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _ffprobe():
    return shutil.which("ffprobe")


def _base():
    fig = plt.figure(figsize=(W, H), dpi=100)
    fig.patch.set_facecolor(BG)
    return fig


def _txt(fig, x, y, s, size, color=FG, weight="bold", ha="center"):
    fig.text(x, y, s, fontsize=size, color=color, fontweight=weight, ha=ha)


def _slide_win(sig, path):
    """Slide 1 — TRADE SUCCESSFUL announcement."""
    fig = _base()
    pnl = (sig.get("result_pct") or sig.get("pnl_pct") or 0)
    side = sig.get("side", "LONG")
    kind = sig.get("kind", "SPOT")
    lev = f" {sig['lev']}x" if sig.get("lev") else ""
    tag = f" {side}{lev}" if kind == "FUTURES" else ""

    _txt(fig, 0.5, 0.87, "✓ TRADE SUCCESSFUL", 52, GREEN)
    _txt(fig, 0.5, 0.78, "─" * 22, 30, GRAY, "normal")
    _txt(fig, 0.5, 0.68, sig["sym"], 110, FG)
    _txt(fig, 0.5, 0.60, f"/USDT  {tag.strip()}", 40, GRAY, "normal")
    _txt(fig, 0.5, 0.46, f"+{pnl:.1f}%", 150, GREEN)
    _txt(fig, 0.5, 0.38, "PROFIT BOOKED  ★", 44, GOLD)
    _txt(fig, 0.5, 0.28, f"Entry: {analyzer.fmt_price(sig['entry'])}", 36, FG, "normal")
    _txt(fig, 0.5, 0.23, f"Target 2 Hit: {analyzer.fmt_price(sig['t2'])}", 36, GREEN, "normal")
    _txt(fig, 0.5, 0.18, f"Stop-loss tha: {analyzer.fmt_price(sig['sl'])}", 32, GRAY, "normal")
    _txt(fig, 0.5, 0.10, "CryptoBhai AI Signals", 30, BLUE)
    _txt(fig, 0.5, 0.06, time.strftime("%d %b %Y"), 24, GRAY, "normal")
    fig.savefig(path, facecolor=BG)
    plt.close(fig)


def _slide_chart(sig, path):
    """Slide 2 — price move + levels recap."""
    fig = _base()
    _txt(fig, 0.5, 0.92, "KAISE CHALA TRADE?", 52, FG)
    prices = []
    try:
        hist = analyzer.fetch_history(sig["id"], 90)
        pts = (hist or {}).get("prices") or []
        since = [(d, p) for d, p in pts if d / 1000 >= sig["epoch"] - 86400]
        prices = [p for _, p in since] if len(since) > 3 else \
            [p for _, p in pts][-30:]
    except Exception:
        prices = []
    ax = fig.add_axes([0.12, 0.50, 0.76, 0.32])
    ax.set_facecolor(BG)
    for sp in ax.spines.values():
        sp.set_color("#21262d")
    ax.tick_params(colors=GRAY, labelsize=12)
    ax.grid(True, color="#21262d", lw=0.6, alpha=0.7)
    if prices:
        n = len(prices)
        entry = sig["entry"]
        col = GREEN if prices[-1] >= entry else RED
        ax.axhline(entry, color=BLUE, ls=":", lw=2)
        ax.axhline(sig["t2"], color=GREEN, ls="--", lw=1.5, alpha=0.8)
        ax.axhline(sig["sl"], color=RED, ls="--", lw=1.5, alpha=0.8)
        ax.plot(range(n), prices, color=FG, lw=3)
        ax.scatter([n - 1], [prices[-1]], color=col, s=140, zorder=6)
        ax.text(0, entry, f" Entry {analyzer.fmt_price(entry)}", color=BLUE, fontsize=14)
        ax.text(0, sig["t2"], f" TP2 {analyzer.fmt_price(sig['t2'])}", color=GREEN, fontsize=14)
        ax.text(0, sig["sl"], f" SL {analyzer.fmt_price(sig['sl'])}", color=RED, fontsize=14)
        ymin, ymax = min(min(prices), sig["sl"]), max(max(prices), sig["t2"])
        pad = (ymax - ymin) * 0.12
        ax.set_ylim(ymin - pad, ymax + pad)
    _txt(fig, 0.5, 0.40, "PLAN FOLLOW KIYA = PROFIT MILA", 40, GOLD)
    _txt(fig, 0.5, 0.33, "✓  Fixed entry zone", 34, FG, "normal")
    _txt(fig, 0.5, 0.28, "✓  Target 1 pe SL safety me shift", 34, FG, "normal")
    _txt(fig, 0.5, 0.23, "✓  Bina emotion ke target 2 tak hold", 34, FG, "normal")
    _txt(fig, 0.5, 0.14, "⚠️ Educational only — not financial advice", 26, GRAY, "normal")
    _txt(fig, 0.5, 0.10, "CryptoBhai AI Signals", 30, BLUE)
    fig.savefig(path, facecolor=BG)
    plt.close(fig)


def _slide_cta(sig, path, channel_link):
    """Slide 3 — Join CTA."""
    fig = _base()
    _txt(fig, 0.5, 0.87, "aise DAILY SIGNALS", 50, FG)
    _txt(fig, 0.5, 0.81, "chahiye?", 50, FG)
    _txt(fig, 0.5, 0.68, "★", 130, GOLD)
    _txt(fig, 0.5, 0.55, "FREE daily market", 44, FG, "normal")
    _txt(fig, 0.5, 0.50, "updates + signals", 44, FG, "normal")
    _txt(fig, 0.5, 0.40, "JOIN KARO", 72, GOLD)
    _txt(fig, 0.5, 0.32, channel_link, 40, BLUE)
    _txt(fig, 0.5, 0.22, "•  Spot + Futures setups", 34, GRAY, "normal")
    _txt(fig, 0.5, 0.17, "•  Charts + Entry/Target/SL", 34, GRAY, "normal")
    _txt(fig, 0.5, 0.12, "•  Live target-hit alerts", 34, GRAY, "normal")
    _txt(fig, 0.5, 0.05, "CryptoBhai AI Signals", 28, BLUE)
    fig.savefig(path, facecolor=BG)
    plt.close(fig)


def _narrate(text, out):
    if not HAS_GTTS:
        return False
    try:
        gTTS(text=text, lang="hi", slow=False).save(out)
        return os.path.getsize(out) > 500
    except Exception:
        return False


def _audio_dur(ff, path, fallback=5.0):
    """ffmpeg -i se duration nikalo (ffprobe optional hai)."""
    try:
        r = subprocess.run([ff, "-i", path], capture_output=True, text=True,
                           timeout=30)
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", r.stderr)
        if m:
            h, mi, s = m.groups()
            return int(h) * 3600 + int(mi) * 60 + float(s) + 0.6
    except Exception:
        pass
    return fallback


def _run(cmd):
    try:
        subprocess.run(cmd, capture_output=True, timeout=120, check=True)
        return True
    except Exception:
        return False


def video_caption(sig):
    """Instagram/YouTube ke liye ready caption + hashtags."""
    pnl = (sig.get("result_pct") or sig.get("pnl_pct") or 0)
    side = sig.get("side", "LONG")
    kind = sig.get("kind", "SPOT")
    lev = f" {sig['lev']}x" if sig.get("lev") else ""
    tag = f" ({side}{lev})" if kind == "FUTURES" else ""
    state_channel = ""
    try:
        import storage
        state_channel = storage.get_state().get("channel_id") or ""
    except Exception:
        pass
    link = state_channel if state_channel.startswith("@") else "@coraporatetrader"
    return (f"🚀 {sig['sym']}{tag} trade SUCCESSFUL — +{pnl:.1f}% profit! 🔥\n"
            f"Entry se seedha Target 2 — plan pe chala to profit mila ✅\n\n"
            f"Aise FREE daily crypto signals ke liye Telegram pe join karo "
            f"👉 {link}\n\n"
            f"#crypto #bitcoin #cryptotrading #futures #trading #{sig['sym']} "
            f"#cryptoindia #altcoins #technicalanalysis #shorts #reels #viral")


def make_result_video(sig):
    """Successful trade ka reel banao. Returns (path|None, caption)."""
    ff = _ffmpeg()
    if not ff:
        return None, video_caption(sig)

    out_dir = os.path.join(config.REPORTS_DIR, "videos")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(
        out_dir, f"RESULT_{sig['sym']}_{time.strftime('%Y%m%d_%H%M')}.mp4")

    channel = ""
    try:
        import storage
        channel = storage.get_state().get("channel_id") or ""
    except Exception:
        pass
    link = ("t.me/" + channel[1:]) if channel.startswith("@") else "t.me/corporapetrader"
    pnl = (sig.get("result_pct") or sig.get("pnl_pct") or 0)

    tmp = tempfile.mkdtemp(prefix="cbvid_")
    try:
        # 1) slides
        s1 = os.path.join(tmp, "s1.png")
        s2 = os.path.join(tmp, "s2.png")
        s3 = os.path.join(tmp, "s3.png")
        _slide_win(sig, s1)
        _slide_chart(sig, s2)
        _slide_cta(sig, s3, link)

        # 2) narration
        texts = [
            f"{sig['sym']} ka trade successful! "
            f"Entry se {pnl:.0f} percent profit book hua. Party!",
            f"Entry thi {analyzer.fmt_price(sig['entry'])} pe, "
            f"target do {analyzer.fmt_price(sig['t2'])} pe hit hua. "
            f"Stop loss {analyzer.fmt_price(sig['sl'])} pe tha. "
            f"Plan follow kiya, profit mila.",
            f"Aise daily crypto signals ke liye, Telegram channel "
            f"Crypto Bhai VIP join karo. Link hai bio me. Jai hind!",
        ]
        audios = []
        for i, t in enumerate(texts, 1):
            ap = os.path.join(tmp, f"a{i}.mp3")
            if _narrate(t, ap):
                audios.append(ap)
            else:
                audios.append(None)

        # 3) segments
        segs = []
        for i, (sp, ap) in enumerate(zip([s1, s2, s3], audios), 1):
            seg = os.path.join(tmp, f"seg{i}.mp4")
            cmd = [ff, "-y", "-loop", "1", "-i", sp]
            if ap:
                cmd += ["-i", ap, "-c:a", "aac", "-shortest"]
            else:
                cmd += ["-t", "5"]
            cmd += ["-c:v", "libx264", "-tune", "stillimage",
                    "-pix_fmt", "yuv420p", "-r", "24", seg]
            if not _run(cmd):
                return None, video_caption(sig)
            if ap:
                # audio khatam hone tak hi slide chale (min 4s)
                d = max(4.0, _audio_dur(ff, ap))
                seg_fix = os.path.join(tmp, f"seg{i}f.mp4")
                if _run([ff, "-y", "-i", seg, "-t", f"{d:.1f}",
                         "-c", "copy", seg_fix]):
                    seg = seg_fix
            segs.append(seg)

        # 4) concat
        lst = os.path.join(tmp, "list.txt")
        with open(lst, "w") as f:
            for s in segs:
                f.write(f"file '{s}'\n")
        if not _run([ff, "-y", "-f", "concat", "-safe", "0", "-i", lst,
                     "-c", "copy", "-movflags", "+faststart", out_path]):
            return None, video_caption(sig)

        if os.path.getsize(out_path) < 50000:
            return None, video_caption(sig)
        return out_path, video_caption(sig)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
