"""Copy generation with Gemini (free tier) plus an automatic quality check."""
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime

from . import config, learning, store
from .captions import visible_len

ANGLES = ["problem_solution", "value_deal", "style_pick", "gift_idea", "how_it_works", "seasonal"]
S = {"type": "STRING"}
SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "angle": {"type": "STRING", "enum": ANGLES},
        "audience": S,
        "fb_format": {"type": "STRING", "enum": ["video", "image"]},
        "fb_format_reason": S,
        "voice": {"type": "STRING", "enum": ["female", "male"]},
        "video": {
            "type": "OBJECT",
            "properties": {
                "title": S,
                "lines": {
                    "type": "ARRAY",
                    "items": {"type": "OBJECT", "properties": {"say": S}, "required": ["say"]},
                },
            },
            "required": ["title", "lines"],
        },
        "keywords": {"type": "ARRAY", "items": S},
        "broll_prompts": {"type": "ARRAY", "items": S},
        "image_headline": S,
        "shopee_caption": S,
        "fb_post": S,
        "fb_first_comment": S,
        "hashtags": {"type": "ARRAY", "items": S},
        "facts_used": {"type": "ARRAY", "items": S},
    },
    "required": ["angle", "audience", "fb_format", "fb_format_reason", "voice", "video", "keywords", "image_headline", "shopee_caption", "fb_post",
                 "fb_first_comment", "hashtags", "facts_used"],
}

# Phrases that make the copy dishonest (first-hand use claims) or break platform rules.
BANNED = ["ตรงปก", "ลองใช้", "ใช้มา", "ได้ของมา", "ของมาถึง", "สั่งมา", "ซื้อมา", "ผมใช้", "ฉันใช้", "เราใช้",
          "ส่วนตัวใช้", "ถูกที่สุด", "รีบซื้อ", "รีบสั่ง", "การันตี", "หายขาด", "รักษาโรค", "อันดับ 1", "อันดับ1",
          "ใครกำลัง", "เคยไหม", "เบื่อไหม", "วันนี้มาแนะนำ"]
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")


class QuotaError(RuntimeError):
    pass


def product_facts(p: dict) -> str:
    keep = ["name", "category", "price", "rating", "sold", "shop_name", "features", "reviews", "notes"]
    facts = {k: p[k] for k in keep if p.get(k) not in (None, "", [])}
    month = datetime.now().month
    facts["เดือนปัจจุบัน"] = month
    return json.dumps(facts, ensure_ascii=False, indent=2)


def build_prompt(p: dict, feedback: list[str] | None = None) -> str:
    fb = ""
    if feedback:
        fb = "\n## รอบก่อนไม่ผ่านการตรวจ แก้ให้ครบทุกข้อ\n" + "\n".join(f"- {x}" for x in feedback)
    tpl = config.PROMPT.read_text(encoding="utf-8")
    notes = learning.prompt_notes()
    notes = f"\n## บทเรียนจากงานที่ผ่านมา (ทำตาม เว้นแต่ขัดกับกฎความจริง)\n{notes}\n" if notes else ""
    return tpl.replace("{{product}}", product_facts(p)).replace("{{feedback}}", fb).replace("{{learning}}", notes)


def gemini(prompt: str) -> dict:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set (put it in .env)")
    model = os.environ.get("GEMINI_MODEL", config.GEMINI_MODEL_DEFAULT)
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": SCHEMA, "temperature": 0.95},
    }).encode()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    for attempt in range(3):
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "x-goog-api-key": key})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read())
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise QuotaError("Gemini free quota used up for now") from e
            if e.code >= 500 and attempt < 2:
                time.sleep(10 * (attempt + 1))
                continue
            raise RuntimeError(f"Gemini HTTP {e.code}: {e.read()[:300]!r}") from e
    raise RuntimeError("Gemini failed")


def _rows(text: str) -> list[str]:
    return [r.strip() for r in text.replace("\\n", "\n").split("\n") if r.strip()]


def qc(p: dict, c: dict) -> list[str]:
    """Rule checks. Returns a list of problems (empty = pass)."""
    problems = []
    name = p.get("name", "")
    lines = c.get("video", {}).get("lines", [])
    texts = {
        "video": c.get("video", {}).get("title", "") + " " + " ".join(l.get("say", "") for l in lines),
        "image_headline": c.get("image_headline", ""),
        "shopee_caption": c.get("shopee_caption", ""),
        "fb_post": c.get("fb_post", ""),
        "fb_first_comment": c.get("fb_first_comment", ""),
    }
    for field, text in texts.items():
        for word in BANNED:
            if word in text and word not in name:
                problems.append(f'{field} มีคำต้องห้าม "{word}"')
        for amount in re.findall(r"(\d[\d,]*)\s*(?:บาท|฿)", text):
            if field != "fb_post" or abs(float(amount.replace(",", "")) - float(p.get("price", 0))) > 0.5:
                problems.append(f"{field} พูดถึงราคา {amount} บาท (ห้ามบอกราคา)")
    if not 4 <= len(lines) <= 7:
        problems.append(f"video.lines ต้องมี 4-6 บรรทัด (ได้ {len(lines)})")
    spoken = sum(visible_len(l.get("say", "")) for l in lines)
    if not 150 <= spoken <= 280:
        problems.append(f"บทพูดรวม {spoken} ตัวอักษร ต้องอยู่ระหว่าง 160-260 (ต่ำกว่านี้คลิปจะสั้นกว่า 15 วินาที) ให้เพิ่มประโยคเล่าเรื่องหรือรายละเอียดจริง")
    for i, l in enumerate(lines):
        say = l.get("say", "")
        if EMOJI.search(say):
            problems.append(f"บรรทัด {i + 1} มี emoji")
        if visible_len(say) > 60:
            problems.append(f"say บรรทัด {i + 1} ยาวเกิน 60 ตัวอักษร ให้แบ่งเป็น 2 บรรทัด")
    for field, text in (("video.title", c.get("video", {}).get("title", "")),
                        ("image_headline", c.get("image_headline", ""))):
        rows = _rows(text)
        if not rows or len(rows) > 2 or any(visible_len(r) > config.TITLE_ROW_MAX for r in rows) or EMOJI.search(text):
            problems.append(f"{field} ต้องมี 1-2 แถว แถวละไม่เกิน 16 ตัวอักษร คั่นแถวด้วย \\n ไม่มี emoji")
    spoken_all = " ".join(l.get("say", "") for l in lines)
    for k in c.get("keywords", []):
        if k not in spoken_all:
            problems.append(f'keyword "{k}" ต้องเป็นคำที่อยู่ใน say')
    if re.search(r"https?://|shopee\.co", texts["fb_post"]):
        problems.append("fb_post ห้ามมีลิงก์")
    if "{LINK}" not in texts["fb_first_comment"]:
        problems.append("fb_first_comment ต้องมี {LINK}")
    if "Affiliate" not in texts["fb_first_comment"]:
        problems.append('fb_first_comment ต้องลงท้ายด้วย "(ลิงก์ Affiliate)"')
    if len(c.get("shopee_caption", "")) > 150:
        problems.append("shopee_caption ยาวเกิน 120 ตัวอักษร")
    if len(EMOJI.findall(texts["fb_post"])) > 3:
        problems.append("fb_post ใช้ emoji เกิน 2 ตัว")
    if not 3 <= len(c.get("hashtags", [])) <= 8:
        problems.append("hashtags ต้องมี 4-6 อัน")
    return problems


def generate(p: dict, force: bool = False) -> dict:
    """Generate copy, check it, retry once with the problems as feedback. Saves into the product."""
    if p.get("content") and p["content"].get("qc") == "pass" and not force:
        return p
    feedback = None
    for attempt in range(3):
        c = gemini(build_prompt(p, feedback))
        c["hashtags"] = [h if h.startswith("#") else f"#{h}" for h in c.get("hashtags", [])][:6]
        problems = qc(p, c)
        c["qc"] = "pass" if not problems else "fail"
        c["qc_problems"] = problems
        c["generated_at"] = datetime.now().isoformat(timespec="seconds")
        if not problems:
            break
        feedback = problems
    p["content"] = c
    store.save(p)
    return p
