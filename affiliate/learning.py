"""Self-improvement loop: learn from posted results, keep a playbook, try new variants on purpose.

Files in data/learning/ (committed, so Claude Code can review what the team learned):
  playbook.md     style rules the team proved with numbers; injected into every content prompt
  lessons.jsonl   one lesson per line (self-review of clips, owner feedback, results); appended by `aff.py lesson`
  weights.json    which variants earn more, computed by `aff.py learn` from data/tracker/posts.csv
  insights.md     the same numbers as a readable table
  proposals.md    ideas that need code changes, for the owner to forward to Claude Code
Variants a post is tagged with: angle, style, theme, voice, category (see `variant_of`).
"""
import json
import random
from collections import defaultdict
from datetime import date, datetime

from . import config, tracker

DIR = config.DATA / "learning"
PLAYBOOK = DIR / "playbook.md"
LESSONS = DIR / "lessons.jsonl"
WEIGHTS = DIR / "weights.json"
INSIGHTS = DIR / "insights.md"
DIMENSIONS = ["angle", "style", "theme", "voice", "category"]
EXPLORE = 0.3          # share of choices that try something other than the current best
MIN_POSTS = 3          # a variant needs this many measured posts before it can be called better
PLAYBOOK_MAX_CHARS = 2500


def variant_of(row: dict) -> dict:
    """Read the variant tags stored in a tracker row (utm_content = angle, utm_campaign = style|theme|voice)."""
    style, theme, voice = (row.get("utm_campaign", "") + "||").split("|")[:3]
    return {"angle": row.get("utm_content", ""), "style": style, "theme": theme, "voice": voice,
            "category": row.get("category", "")}


def _num(row: dict, key: str) -> float:
    try:
        return float(row.get(key) or 0)
    except ValueError:
        return 0.0


def learn() -> dict:
    """Average result per variant. Score = commission per post, with clicks as a tie-breaker signal."""
    rows = [r for r in tracker.read() if r.get("clicks") or r.get("commission_net") or r.get("views")]
    stats: dict = {d: defaultdict(lambda: {"posts": 0, "commission": 0.0, "clicks": 0.0, "views": 0.0}) for d in DIMENSIONS}
    for r in rows:
        v = variant_of(r)
        for d in DIMENSIONS:
            if not v[d]:
                continue
            s = stats[d][v[d]]
            s["posts"] += 1
            s["commission"] += _num(r, "commission_net")
            s["clicks"] += _num(r, "clicks")
            s["views"] += _num(r, "views")
    weights = {"updated": datetime.now().isoformat(timespec="seconds"), "measured_posts": len(rows), "dimensions": {}}
    for d in DIMENSIONS:
        out = {}
        for name, s in stats[d].items():
            n = s["posts"]
            out[name] = {
                "posts": n,
                "commission_per_post": round(s["commission"] / n, 2),
                "clicks_per_post": round(s["clicks"] / n, 2),
                "views_per_post": round(s["views"] / n, 1),
                # smoothed score so one lucky post does not dominate
                "score": round((s["commission"] + 0.1 * s["clicks"]) / (n + 2), 3),
                "proven": n >= MIN_POSTS,
            }
        weights["dimensions"][d] = dict(sorted(out.items(), key=lambda kv: kv[1]["score"], reverse=True))
    DIR.mkdir(parents=True, exist_ok=True)
    WEIGHTS.write_text(json.dumps(weights, ensure_ascii=False, indent=2), encoding="utf-8")
    INSIGHTS.write_text(_insights_md(weights), encoding="utf-8")
    return weights


def _insights_md(w: dict) -> str:
    lines = [f"# ผลการเรียนรู้ ({w['updated']}) จากโพสต์ที่มียอดแล้ว {w['measured_posts']} โพสต์", "",
             f"ตัวแปรที่มีโพสต์ไม่ถึง {MIN_POSTS} โพสต์ยังสรุปไม่ได้ (proven = no)", ""]
    for d, items in w["dimensions"].items():
        lines += [f"## {d}", "", "| ตัวเลือก | โพสต์ | ค่าคอม/โพสต์ | คลิก/โพสต์ | วิว/โพสต์ | proven |", "|---|---|---|---|---|---|"]
        for name, s in items.items():
            lines.append(f"| {name} | {s['posts']} | {s['commission_per_post']} | {s['clicks_per_post']} | "
                         f"{s['views_per_post']} | {'yes' if s['proven'] else 'no'} |")
        lines.append("")
    return "\n".join(lines)


def load_weights() -> dict:
    try:
        return json.loads(WEIGHTS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"dimensions": {}}


def choose(dimension: str, options: list[str], rng: random.Random, weights: dict | None = None) -> str:
    """Mostly use what earns best, but keep trying others so the team keeps learning (epsilon-greedy)."""
    known = (weights or load_weights()).get("dimensions", {}).get(dimension, {})
    proven = [o for o in known if o in options and known[o]["proven"]]
    if proven and rng.random() > EXPLORE:
        return max(proven, key=lambda o: known[o]["score"])
    untried = [o for o in options if o not in known]
    return rng.choice(untried or options)


def add_lesson(text: str, tag: str = "general", evidence: str = "", source: str = "bot") -> dict:
    DIR.mkdir(parents=True, exist_ok=True)
    entry = {"date": date.today().isoformat(), "tag": tag, "source": source, "lesson": text.strip(), "evidence": evidence}
    with LESSONS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def prompt_notes() -> str:
    """What the content writer must know from past work: the playbook + the best-earning angles."""
    parts = []
    if PLAYBOOK.exists():
        text = PLAYBOOK.read_text(encoding="utf-8").strip()
        if text:
            parts.append(text[:PLAYBOOK_MAX_CHARS])
    angles = load_weights().get("dimensions", {}).get("angle", {})
    best = [f"{a} ({s['commission_per_post']} บาท/โพสต์ จาก {s['posts']} โพสต์)" for a, s in angles.items() if s["proven"]][:3]
    if best:
        parts.append("มุมขายที่ทำเงินดีที่สุดจากข้อมูลจริง: " + ", ".join(best) + " (ใช้เมื่อเหมาะกับสินค้า ไม่ต้องฝืน)")
    return "\n\n".join(parts)
