"""Product records and the inbox importer.

A product lives in data/products/<id>.json. The scout bot writes .txt files into
data/inbox/ (format: data/inbox/TEMPLATE.txt); `python aff.py import` merges them.
"""
import hashlib
import json
import re
import shutil
import subprocess
import urllib.request
from datetime import date
from pathlib import Path

from . import config

# Labels accepted in inbox files -> product field
SCALAR_LABELS = {
    "ชื่อ": "name",
    "ลิงก์": "url",
    "ราคา": "price",
    "หมวด": "category",
    "ค่าคอมรวม": "total_rate",
    "ค่าคอมพิเศษ": "extra_rate",
    "ExtraComm": "extra_rate",
    "เรตติ้ง": "rating",
    "ขายแล้ว": "sold",
    "ร้าน": "shop_name",
    "หมายเหตุ": "notes",
}
LIST_LABELS = {"รีวิว": "reviews", "จุดเด่น": "features", "รูป": "images"}
NUMERIC = {"price", "total_rate", "extra_rate", "rating", "sold"}
MIN_IMAGE_SIDE = 500  # px; smaller photos look blurry at 880 px in the clip


def product_id(url: str) -> str:
    """Stable id from the affiliate link."""
    m = re.search(r"s\.shopee\.co\.th/([A-Za-z0-9]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"i\.(\d+)\.(\d+)", url) or re.search(r"product/(\d+)/(\d+)", url)
    if m:
        return f"{m.group(1)}_{m.group(2)}"
    return hashlib.sha1(url.encode()).hexdigest()[:10]


def parse_number(raw: str) -> float | None:
    raw = raw.lower().replace(",", "").replace("฿", "").replace("%", "").strip()
    mult = 1
    if raw.endswith("k"):
        raw, mult = raw[:-1], 1000
    elif raw.endswith("พัน"):
        raw, mult = raw[:-3], 1000
    elif raw.endswith("หมื่น"):
        raw, mult = raw[:-5], 10000
    m = re.search(r"\d+(\.\d+)?", raw)
    return float(m.group()) * mult if m else None


def path_for(pid: str) -> Path:
    return config.PRODUCTS / f"{pid}.json"


def load(pid: str) -> dict:
    return json.loads(path_for(pid).read_text(encoding="utf-8"))


def load_all() -> list[dict]:
    if not config.PRODUCTS.exists():
        return []
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(config.PRODUCTS.glob("*.json"))]


def save(p: dict) -> None:
    config.PRODUCTS.mkdir(parents=True, exist_ok=True)
    p["status"] = status_of(p)
    path_for(p["id"]).write_text(json.dumps(p, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def image_files(p: dict) -> list[Path]:
    folder = config.MEDIA / p["id"]
    if not folder.exists():
        return []
    return sorted(f for f in folder.iterdir() if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})


def commission_per_order(p: dict) -> float:
    """Baht earned on one direct order: base rate (capped) + Extra Comm, on the listed price."""
    price = float(p.get("price") or 0)
    base = min(price * config.BASE_RATE / 100, config.BASE_CAP_THB)
    extra = p.get("extra_rate")
    extra = config.EXTRA_UNKNOWN if extra is None else extra
    return round(base + price * extra / 100, 2)


def clip_files(p: dict) -> list[Path]:
    """Optional AI/stock B-roll for this product: media/<id>/clips/*.mp4"""
    folder = config.MEDIA / p["id"] / "clips"
    return sorted(folder.glob("*.mp4")) if folder.exists() else []


def status_of(p: dict) -> str:
    """skip = Extra Comm known and below the minimum; needs_info = scout must fill data; ready."""
    if p.get("skip_reason"):
        return "skip"
    if p.get("extra_rate") is not None and commission_per_order(p) < config.MIN_COMMISSION_THB:
        return "skip"
    missing = missing_info(p)
    return "needs_info" if missing else "ready"


def missing_info(p: dict) -> list[str]:
    out = []
    if not image_files(p):
        out.append("รูป")
    if p.get("extra_rate") is None:
        out.append("ค่าคอมพิเศษ")
    if not p.get("features"):
        out.append("จุดเด่น")
    return out


def parse_block(block: str) -> dict:
    raw: dict = {}
    current_list = None
    for line in block.splitlines():
        line = line.strip()
        if not line:
            continue
        label, sep, rest = line.partition(":")
        if not sep:
            label, sep, rest = line.partition("：")
        label = label.strip()
        if sep and label in LIST_LABELS:
            current_list = LIST_LABELS[label]
            raw.setdefault(current_list, [])
            if rest.strip():
                raw[current_list].append(rest.strip())
        elif sep and label in SCALAR_LABELS:
            current_list = None
            raw[SCALAR_LABELS[label]] = rest.strip()
        elif current_list:
            raw[current_list].append(line.lstrip("-•* ").strip())
    for key in NUMERIC & raw.keys():
        raw[key] = parse_number(raw[key])
    return raw


def full_size_url(src: str) -> str:
    """Shopee CDN thumbnails end in _tn; the same path without it is the full-size photo."""
    return re.sub(r"_tn(?=$|[?#])", "", src.strip())


def image_size(path: Path) -> tuple[int, int] | None:
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
        w, h = (int(x) for x in r.stdout.strip().split(",")[:2])
        return w, h
    except Exception:  # noqa: BLE001 - unreadable file or ffprobe missing
        return None


def fetch_image(src: str, dest: Path) -> bool:
    src = full_size_url(src)
    try:
        if src.startswith("http"):
            req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            if len(data) < 2000:
                return False
            dest.write_bytes(data)
        else:
            shutil.copyfile(Path(src).expanduser(), dest)
    except Exception as e:  # noqa: BLE001 - report and continue with other images
        print(f"   ! image failed: {src[:80]} ({e})")
        return False
    size = image_size(dest)
    if size and min(size) < MIN_IMAGE_SIDE:
        dest.unlink()
        print(f"   ! image too small {size[0]}x{size[1]}, skipped: {src[:80]}")
        return False
    if size and min(size) < 600:
        print(f"   ~ image is small ({size[0]}x{size[1]}); a larger one would look sharper")
    return True


def merge(raw: dict) -> dict:
    """Create or update a product from parsed inbox fields. Only provided fields change."""
    if not raw.get("url"):
        raise ValueError("missing ลิงก์")
    pid = product_id(raw["url"])
    p = load(pid) if path_for(pid).exists() else {"id": pid, "added": date.today().isoformat(), "posted": {}}
    images = raw.pop("images", [])
    for key, value in raw.items():
        if value not in (None, "", []):
            p[key] = value
    if not p.get("name") or not p.get("price"):
        raise ValueError(f"{pid}: needs ชื่อ and ราคา")
    if images:
        folder = config.MEDIA / pid
        folder.mkdir(parents=True, exist_ok=True)
        start = len(image_files(p))
        for i, src in enumerate(images[:6]):
            ext = ".png" if src.lower().split("?")[0].endswith(".png") else ".jpg"
            fetch_image(src, folder / f"img_{start + i + 1:02d}{ext}")  # zero-padded keeps the scout's order
    if raw.keys() & {"features", "reviews", "name", "price"}:
        p.pop("content", None)  # facts changed: regenerate the copy
    save(p)
    return p


def import_inbox() -> list[dict]:
    config.INBOX_DONE.mkdir(parents=True, exist_ok=True)
    done = []
    for f in sorted(config.INBOX.glob("*.txt")):
        if f.name.upper().startswith("TEMPLATE"):
            continue
        ok = True
        for block in re.split(r"^\s*---+\s*$", f.read_text(encoding="utf-8-sig"), flags=re.M):
            if not block.strip():
                continue
            try:
                p = merge(parse_block(block))
                done.append(p)
                print(f" + {p['id']}  {p['name'][:40]}  -> {p['status']}")
            except Exception as e:  # noqa: BLE001
                ok = False
                print(f" ! {f.name}: {e}")
        if ok:
            f.replace(config.INBOX_DONE / f.name)
    return done
