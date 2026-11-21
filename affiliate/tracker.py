"""Post log in the 41-column layout from the research PDF (1 row = 1 link x 1 post x 1 day)."""
import csv
from datetime import date

from . import config

COLUMNS = [
    # content & system (7)
    "date", "link_id", "post_id", "platform", "workflow_mode", "content_type", "video_sec",
    # product & commission (10)
    "product_id", "shop_id", "category", "product_name", "price_listed", "price_net",
    "commission_type", "base_rate", "xtra_rate", "total_rate",
    # tracking & behaviour (12)
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "clicks", "unique_clicks",
    "views", "watch_time_sec", "orders_direct", "orders_indirect", "items_sold", "sales_net",
    # money & cost (7)
    "api_cost_thb", "commission_gross", "commission_net", "net_profit_thb",
    "order_status", "payout_status", "return_rate",
    # AI rules & context (5)
    "ai_label_on", "is_ai_content", "is_mission", "country", "notes",
]
STAT_FIELDS = {"clicks", "unique_clicks", "views", "watch_time_sec", "orders_direct", "orders_indirect",
               "items_sold", "sales_net", "commission_gross", "commission_net", "api_cost_thb",
               "order_status", "payout_status", "return_rate", "notes"}


def read() -> list[dict]:
    if not config.TRACKER.exists():
        return []
    with config.TRACKER.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write(rows: list[dict]) -> None:
    config.TRACKER.parent.mkdir(parents=True, exist_ok=True)
    with config.TRACKER.open("w", encoding="utf-8-sig", newline="") as f:  # BOM so Excel shows Thai
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def log_post(p: dict, platform: str, content_type: str, post_url: str = "", video_sec: float | str = "",
             day: str | None = None) -> None:
    extra = p.get("extra_rate")
    rows = read()
    rows.append({
        "date": day or date.today().isoformat(), "link_id": p["id"], "post_id": post_url,
        "platform": platform, "workflow_mode": "auto_bot", "content_type": content_type, "video_sec": video_sec,
        "product_id": p["id"], "category": p.get("category", ""), "product_name": p.get("name", ""),
        "price_listed": p.get("price", ""), "commission_type": "xtra" if extra else "base",
        "base_rate": config.BASE_RATE, "xtra_rate": extra if extra is not None else "",
        "total_rate": p.get("total_rate") or (config.BASE_RATE + extra if extra is not None else ""),
        "utm_source": platform, "utm_content": p.get("content", {}).get("angle", ""),
        "api_cost_thb": 0, "ai_label_on": 1 if platform == "shopee_video" else "",
        "is_ai_content": 1, "is_mission": 0, "country": "TH",
    })
    write(rows)


def set_stats(day: str, link_id: str, platform: str, values: dict) -> bool:
    rows = read()
    hit = False
    for r in rows:
        if r["date"] == day and r["link_id"] == link_id and r["platform"] == platform:
            r.update({k: v for k, v in values.items() if k in STAT_FIELDS})
            try:
                r["net_profit_thb"] = float(r.get("commission_net") or 0) - float(r.get("api_cost_thb") or 0)
            except ValueError:
                pass
            hit = True
    if hit:
        write(rows)
    return hit


def ensure_header() -> None:
    if not config.TRACKER.exists():
        write([])
