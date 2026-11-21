"""Pick today's products, make the media and write an approval packet for the Maus bots."""
import json
import math
from collections import Counter
from datetime import date, datetime, timedelta

from . import config, content, render, store


def expected_commission(p: dict) -> float:
    return store.commission_per_order(p)


def score(p: dict) -> float:
    s = expected_commission(p)
    if p.get("rating"):
        s *= max(0.5, (float(p["rating"]) - 3.5) / 1.5)
    if p.get("sold"):
        s *= 0.7 + min(math.log10(float(p["sold"]) + 1), 5) / 10
    if p.get("extra_rate") is None:
        s *= 0.6  # unverified commission ranks lower
    return round(s, 2)


def recently_posted(p: dict, channel: str, today: date) -> bool:
    last = p.get("posted", {}).get(channel)
    return bool(last) and date.fromisoformat(last) > today - timedelta(days=config.REPOST_AFTER_DAYS)


def select(today: date, count: int) -> list[dict]:
    pool = [p for p in store.load_all() if p["status"] == "ready" and not recently_posted(p, "shopee_video", today)]
    pool.sort(key=score, reverse=True)
    picked, per_cat = [], Counter()
    for p in pool:
        cat = p.get("category") or "อื่น ๆ"
        if per_cat[cat] >= config.MAX_PER_CATEGORY:
            continue
        picked.append(p)
        per_cat[cat] += 1
        if len(picked) == count:
            break
    if len(picked) < count:  # not enough variety: fill with the best of the rest
        rest = [p for p in pool if p not in picked]
        picked += rest[: count - len(picked)]
    return picked


def daily(day: date | None = None, count: int | None = None, render_media: bool = True) -> dict:
    day = day or date.today()
    count = count or config.ITEMS_PER_DAY
    out = config.OUT / day.isoformat()
    out.mkdir(parents=True, exist_ok=True)
    chosen = select(day, count)
    if not chosen:
        raise SystemExit("ไม่มีสินค้าที่พร้อม (status=ready). ให้ scout เติมรูป/ค่าคอม/จุดเด่นก่อน: python aff.py todo")

    items = []
    for n, p in enumerate(chosen, 1):
        print(f"[{n}/{len(chosen)}] {p['name'][:50]}")
        try:
            p = content.generate(p)
        except content.QuotaError as e:
            print(f"   ! {e} - stopping here; run again later to finish")
            break
        c = p["content"]
        if c["qc"] != "pass":
            print(f"   ! QC failed: {c['qc_problems']}")
            continue
        folder = out / f"{n:02d}_{p['id']}"
        folder.mkdir(exist_ok=True)
        tags = " ".join(c["hashtags"])
        (folder / "shopee_caption.txt").write_text(f"{c['shopee_caption']}\n{tags}\n", encoding="utf-8")
        (folder / "fb_post.txt").write_text(f"{c['fb_post']}\n\n{tags}\n", encoding="utf-8")
        (folder / "fb_first_comment.txt").write_text(c["fb_first_comment"].replace("{LINK}", p["url"]) + "\n",
                                                     encoding="utf-8")
        (folder / "link.txt").write_text(p["url"] + "\n", encoding="utf-8")
        sec = ""
        if render_media:
            imgs = store.image_files(p)
            try:
                sec = render.make_video(c, imgs, folder / "video.mp4")
                render.make_image(c, imgs[0], folder / "image.jpg")
            except Exception as e:  # noqa: BLE001 - one bad photo must not stop the day
                print(f"   ! render failed: {str(e)[:300]}")
                continue
            print(f"   video {sec}s + image ok")
        items.append({"no": n, "id": p["id"], "name": p["name"], "url": p["url"], "category": p.get("category"),
                      "price": p.get("price"), "extra_rate": p.get("extra_rate"),
                      "commission_thb": store.commission_per_order(p), "score": score(p),
                      "angle": c["angle"], "audience": c.get("audience", ""), "fb_format": c.get("fb_format"),
                      "fb_format_reason": c.get("fb_format_reason", ""), "voice": c["voice"], "video_sec": sec, "folder": folder.name})

    # schedule: every item goes to Shopee Video, the top N by score also to the Facebook Page
    by_score = sorted(items, key=lambda i: i["score"], reverse=True)
    fb_ids = {i["id"] for i in by_score[: config.FB_POSTS_PER_DAY]}
    for i, slot in zip(items, config.SHOPEE_SLOTS):
        i["shopee_time"] = slot
    fb_slots = iter(config.FB_SLOTS)
    fb_count = 0
    for i in items:
        i["facebook_time"] = i["facebook_type"] = None
        if i["id"] in fb_ids:
            i["facebook_time"] = next(fb_slots, None)
            i["facebook_type"] = i.get("fb_format") or ("image" if fb_count % 2 == 0 else "video")
            fb_count += 1
        i["approved"] = None
        i["posted"] = {}
    plan = {"date": day.isoformat(), "created": datetime.now().isoformat(timespec="seconds"), "items": items}
    (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    write_approval(out, plan)
    return plan


def write_approval(out, plan: dict) -> None:
    rows = [f"# ชุดอนุมัติประจำวัน {plan['date']}", "",
            "ตอบในแอป Maus ว่า `อนุมัติทั้งหมด` หรือ `อนุมัติ 1,2,5` หรือ `ไม่อนุมัติ 3 เพราะ ...`", "",
            "| # | สินค้า | ค่าคอม/ออเดอร์ | กลุ่มลูกค้า | มุมขาย | Shopee Video | Facebook |", "|---|---|---|---|---|---|---|"]
    for i in plan["items"]:
        extra = (f"฿{i['commission_thb']:.0f} ({i['extra_rate']}%)" if i["extra_rate"] is not None
                 else f"~฿{i['commission_thb']:.0f} (ยังไม่ยืนยัน)")
        fb = f"{i['facebook_time']} ({i['facebook_type']})" if i["facebook_time"] else "-"
        rows.append(f"| {i['no']} | {i['name'][:38]} | {extra} | {i.get('audience', '')[:40]} | {i['angle']} | "
                    f"{i['shopee_time']} | {fb} |")
    fb_notes = [f"- #{i['no']} {i['facebook_type']}: {i.get('fb_format_reason', '')}" for i in plan["items"] if i["facebook_time"]]
    if fb_notes:
        rows += ["", "เหตุผลที่เลือกรูปแบบโพสต์ Facebook", *fb_notes]
    rows += ["", "แต่ละโฟลเดอร์มี video.mp4, image.jpg, shopee_caption.txt, fb_post.txt, fb_first_comment.txt, link.txt"]
    (out / "APPROVAL.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
