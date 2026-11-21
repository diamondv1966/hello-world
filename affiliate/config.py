"""Settings for the Shopee affiliate pipeline. Change numbers here, not in the code."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PRODUCTS = DATA / "products"          # one JSON per product (committed)
INBOX = DATA / "inbox"                # scout bot drops .txt files here
INBOX_DONE = INBOX / "done"
TRACKER = DATA / "tracker" / "posts.csv"
MEDIA = ROOT / "media"                # downloaded product images (not committed)
OUT = ROOT / "out"                    # daily packets: videos, images, captions (not committed)
PROMPT = ROOT / "prompts" / "content_prompt.md"

# --- Product selection -------------------------------------------------------
MIN_EXTRA_COMM = 8.0      # % ; products whose Extra Comm is known and lower are skipped
BASE_RATE = 2.0           # % Shopee TH base commission (direct order)
BASE_CAP_THB = 225        # base commission cap per order
ITEMS_PER_DAY = 5         # Shopee Video clips per day: start at 5, raise to 10 after 3 clean days
FB_POSTS_PER_DAY = 4      # Facebook Page posts per day (a new page that posts 10/day looks like spam)
MAX_PER_CATEGORY = 3      # keep the daily mix varied
REPOST_AFTER_DAYS = 14    # do not reuse a product on the same channel sooner than this

# Posting times (the publisher bot adds a random 0-12 minute delay to each)
SHOPEE_SLOTS = ["08:40", "10:10", "11:35", "12:20", "13:40", "16:45", "18:10", "19:35", "20:40", "21:35"]
FB_SLOTS = ["12:05", "18:30", "20:05", "21:10"]

# --- Content -----------------------------------------------------------------
GEMINI_MODEL_DEFAULT = "gemini-2.5-flash"
VOICES = {"female": "th-TH-PremwadeeNeural", "male": "th-TH-NiwatNeural"}
TTS_RATE = "+10%"         # short-form voices run a little fast
MIN_VIDEO_SEC = 16.0      # Shopee Video: keep clips at least 15 seconds
TITLE_ROW_MAX = 16        # characters per row in the title box / image headline
FONT_FILE = ROOT / "assets" / "fonts" / "Kanit-Bold.ttf"   # SIL OFL, bundled
FONT = "Kanit" if FONT_FILE.exists() else ("Leelawadee UI" if sys.platform == "win32" else "Loma")
MUSIC_DIR = ROOT / "assets" / "music"   # optional: put royalty-free tracks here (see README)
MUSIC_VOLUME = 0.12


def load_env() -> None:
    """Read KEY=VALUE lines from .env (never committed) into the environment."""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
