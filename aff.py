"""Shopee affiliate pipeline - command line.

  python aff.py doctor                 check ffmpeg, voice, Gemini key, font
  python aff.py import                 merge data/inbox/*.txt into data/products/
  python aff.py todo                   products the scout bot still has to fill in
  python aff.py daily                  pick today's products, write copy, render, write out/<date>/APPROVAL.md
  python aff.py approve all|1,2,5      record the owner's approval for today's packet
  python aff.py posted 3 shopee_video [post_url]    mark item 3 posted (also: facebook)
  python aff.py stat <product_id> <platform> clicks=12 orders_direct=1 commission_net=35 [--date D]
  python aff.py report                 summary -> out/REPORT.md
"""
import argparse
import json
import shutil
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Thai in the Windows console

from affiliate import config, content, planner, store, tracker  # noqa: E402


def plan_path(day: str) -> Path:
    return config.OUT / day / "plan.json"


def load_plan(day: str) -> dict:
    p = plan_path(day)
    if not p.exists():
        sys.exit(f"no packet for {day}; run: python aff.py daily")
    return json.loads(p.read_text(encoding="utf-8"))


def save_plan(plan: dict) -> None:
    plan_path(plan["date"]).write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")


def cmd_doctor(_):
    ok = True
    for tool in ("ffmpeg", "ffprobe"):
        found = shutil.which(tool)
        print(f"{'OK ' if found else 'MISSING'} {tool}")
        ok &= bool(found)
    try:
        import edge_tts  # noqa: F401
        print("OK  edge-tts (เสียงพากย์ฟรี)")
    except ImportError:
        print("MISSING edge-tts  -> pip install edge-tts   (ไม่มีก็ได้ คลิปจะไม่มีเสียง)")
    try:
        import pythainlp  # noqa: F401
        print("OK  pythainlp (ตัดคำไทยสำหรับซับ)")
    except ImportError:
        print("MISSING pythainlp -> pip install pythainlp   (ไม่มีก็ได้ แต่ซับจะตัดคำไม่สวย)")
    print(f"{'OK ' if config.FONT_FILE.exists() else 'MISSING'} font {config.FONT}")
    key = bool(__import__("os").environ.get("GEMINI_API_KEY"))
    print(f"{'OK ' if key else 'MISSING'} GEMINI_API_KEY in .env")
    ok &= key
    if shutil.which("ffmpeg"):
        r = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True)
        has_subs = " subtitles " in r.stdout
        print(f"{'OK ' if has_subs else 'MISSING'} ffmpeg subtitles filter (libass)")
        ok &= has_subs
    counts = Counter(p["status"] for p in store.load_all())
    print(f"products: {dict(counts)}")
    sys.exit(0 if ok else 1)


def cmd_import(_):
    done = store.import_inbox()
    print(f"imported {len(done)}")


def cmd_todo(_):
    rows = [p for p in store.load_all() if p["status"] == "needs_info"]
    rows.sort(key=planner.score, reverse=True)
    print(f"{len(rows)} products need info (best first). Fill via data/inbox/*.txt then: python aff.py import")
    for p in rows:
        print(f"- {p['url']}  | {p['name'][:45]} | ขาด: {', '.join(store.missing_info(p))}")


def cmd_generate(a):
    items = [store.load(a.id)] if a.id else [p for p in store.load_all() if p["status"] == "ready"]
    for p in items[: a.limit]:
        p = content.generate(p, force=a.force)
        c = p["content"]
        print(f"{p['id']}: {c['qc']} {c['qc_problems'] or ''}")


def cmd_daily(a):
    day = date.fromisoformat(a.date) if a.date else None
    plan = planner.daily(day, a.count, render_media=not a.no_render)
    print(f"\n{len(plan['items'])} items ready -> {config.OUT / plan['date'] / 'APPROVAL.md'}")


def cmd_approve(a):
    plan = load_plan(a.date or date.today().isoformat())
    wanted = None if a.items == "all" else {int(x) for x in a.items.split(",")}
    for i in plan["items"]:
        if wanted is None or i["no"] in wanted:
            i["approved"] = True
        elif a.reject_others:
            i["approved"] = False
    save_plan(plan)
    print("approved:", [i["no"] for i in plan["items"] if i["approved"]])


def cmd_posted(a):
    day = a.date or date.today().isoformat()
    plan = load_plan(day)
    item = next((i for i in plan["items"] if i["no"] == a.no), None)
    if not item:
        sys.exit(f"no item {a.no}")
    if not item.get("approved"):
        sys.exit(f"item {a.no} is not approved - refusing to log a post")
    item["posted"][a.platform] = a.url or True
    save_plan(plan)
    p = store.load(item["id"])
    p.setdefault("posted", {})[a.platform] = day
    store.save(p)
    ctype = "video" if a.platform == "shopee_video" else (item.get("facebook_type") or "image")
    tracker.log_post(p, a.platform, ctype, a.url or "", item.get("video_sec", ""), day)
    print(f"logged item {a.no} on {a.platform}")


def cmd_stat(a):
    values = dict(kv.split("=", 1) for kv in a.values)
    day = a.date or date.today().isoformat()
    print("updated" if tracker.set_stats(day, a.id, a.platform, values) else "row not found")


def cmd_report(_):
    products = store.load_all()
    rows = tracker.read()
    num = lambda r, k: float(r.get(k) or 0)  # noqa: E731
    by_day = Counter(r["date"] for r in rows)
    clicks = sum(num(r, "clicks") for r in rows)
    orders = sum(num(r, "orders_direct") + num(r, "orders_indirect") for r in rows)
    comm = sum(num(r, "commission_net") for r in rows)
    lines = ["# รายงาน Shopee Affiliate", "",
             f"- สินค้า: {dict(Counter(p['status'] for p in products))}",
             f"- โพสต์ทั้งหมด: {len(rows)} | ล่าสุด: {dict(sorted(by_day.items())[-7:])}",
             f"- คลิก {clicks:.0f} | ออเดอร์ {orders:.0f} | ค่าคอมสุทธิ {comm:.2f} บาท",
             f"- Conversion {orders / clicks * 100:.2f}% | EPC {comm / clicks:.2f} บาท/คลิก" if clicks else "- ยังไม่มีข้อมูลคลิก",
             "", "## ค่าคอมสูงสุดตามสินค้า", ""]
    per = Counter()
    for r in rows:
        per[r["product_name"][:40]] += num(r, "commission_net")
    lines += [f"- {name}: {v:.2f} บาท" for name, v in per.most_common(10)]
    config.OUT.mkdir(exist_ok=True)
    (config.OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main():
    config.load_env()
    tracker.ensure_header()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor").set_defaults(f=cmd_doctor)
    sub.add_parser("import").set_defaults(f=cmd_import)
    sub.add_parser("todo").set_defaults(f=cmd_todo)
    g = sub.add_parser("generate")
    g.add_argument("--id")
    g.add_argument("--limit", type=int, default=10)
    g.add_argument("--force", action="store_true")
    g.set_defaults(f=cmd_generate)
    d = sub.add_parser("daily")
    d.add_argument("--date")
    d.add_argument("--count", type=int)
    d.add_argument("--no-render", action="store_true")
    d.set_defaults(f=cmd_daily)
    ap_ = sub.add_parser("approve")
    ap_.add_argument("items", help="all or 1,2,5")
    ap_.add_argument("--date")
    ap_.add_argument("--reject-others", action="store_true")
    ap_.set_defaults(f=cmd_approve)
    po = sub.add_parser("posted")
    po.add_argument("no", type=int)
    po.add_argument("platform", choices=["shopee_video", "facebook"])
    po.add_argument("url", nargs="?")
    po.add_argument("--date")
    po.set_defaults(f=cmd_posted)
    st = sub.add_parser("stat")
    st.add_argument("id")
    st.add_argument("platform", choices=["shopee_video", "facebook"])
    st.add_argument("values", nargs="+")
    st.add_argument("--date")
    st.set_defaults(f=cmd_stat)
    sub.add_parser("report").set_defaults(f=cmd_report)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
