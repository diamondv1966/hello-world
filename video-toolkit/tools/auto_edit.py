"""Auto-edit a vertical talking-head clip from a style preset (+ optional reference profile and creative config).

python3 -I tools/auto_edit.py projects/<name> --preset clean-pastel [--config projects/<name>/config.json]
                              [--ref projects/<name>/ref/style_profile.json] [--plan-only]

project dir must contain src.mp4 (tools/new_project.sh makes it).
config.json (optional, written by Claude after analysis):
{
  "language": "th",
  "hook": {"lines": ["ร่างกายกำลัง", "เตือนคุณ!"]},          # big text 0–hook.dur s (accent on last line)
  "emphasis": ["ขาดน้ำ", "แมกนีเซียม"],                    # highlighted + pop sfx + zoom punch
  "cards": [{"at": "แมกนีเซียม", "dur": 1.8, "title": "แมกนีเซียมพบใน",
             "items": [["🥜","ถั่ว"],["🥑","อะโวคาโด"]], "note": "กินให้หลากหลาย"}],
  "broll": [{"at": "น้ำ", "file": "/abs/path.mp4", "dur": 1.5, "mode": "pip"}],   # mode pip | full
  "cta": {"text": "กดติดตาม ไม่พลาดตอนต่อไป", "sub": "ข้อไหนเป็นอยู่? คอมเมนต์บอกหน่อย"},
  "disclaimer": "ข้อมูลเบื้องต้น ไม่ใช่การวินิจฉัย",
  "skip": [[12.0, 13.4]],                                   # extra source spans to remove (retakes Claude found)
  "music": {"mood": "bright"}, "captions": {...}            # any preset key can be overridden here
}
"at" = first occurrence of that text in the transcript (or a number = source seconds).
Outputs in the project: words.json, plan.json, captions.ass, sfx_track.wav, music.wav, FINAL.mp4, qa.jpg, report.md
"""
import sys, os, json, math, copy, argparse, subprocess, functools
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vt_lib as L

ap = argparse.ArgumentParser()
ap.add_argument("project"); ap.add_argument("--preset", default="clean-pastel"); ap.add_argument("--config")
ap.add_argument("--ref"); ap.add_argument("--plan-only", action="store_true")
args = ap.parse_args()
P = os.path.abspath(args.project); SRC = f"{P}/src.mp4"
W, H, FPS = 1080, 1920, 30

def deep_update(a, b):
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(a.get(k), dict): deep_update(a[k], v)
        else: a[k] = v
    return a
pp = args.preset if args.preset.endswith(".json") else f"{L.ROOT}/presets/{args.preset}.json"
S = json.load(open(pp))
CFG = json.load(open(args.config)) if args.config else (json.load(open(f"{P}/config.json")) if os.path.exists(f"{P}/config.json") else {})
REF = json.load(open(args.ref)) if args.ref else None
if REF and REF.get("preset_overrides"): deep_update(S, REF["preset_overrides"])
deep_update(S, {k: v for k, v in CFG.items() if k in S})
LANG = CFG.get("language", "th")
info = L.probe(SRC)
report = [f"# Auto-edit report — {os.path.basename(P)}", f"preset: **{S['name']}**" + (f" + ref `{args.ref}`" if REF else ""), ""]

# ------------------------------------------------------------- 1. analysis (cached)
def cached(name, fn):
    f = f"{P}/{name}"
    if os.path.exists(f): return json.load(open(f))
    v = fn(); json.dump(v, open(f, "w"), ensure_ascii=False); return v
audio = L.load_audio16k(SRC)
words = cached("words.json", lambda: L.transcribe_words(audio, LANG))
sil = cached(f"silences_{S['cut']['max_gap']}.json", lambda: L.silences(SRC, -33, S["cut"]["max_gap"]))
faces = cached("faces.json", lambda: L.face_track(SRC))
src_col = cached("colour.json", lambda: L.colour_stats(SRC))

# ------------------------------------------------------------- 2. cut plan
dur = info["duration"]; pad = S["cut"]["pad"]
cuts = []  # (a, b, reason) source spans to remove
for a, b in sil:
    if a <= 0.05: cuts.append((0.0, max(0.0, b - pad), "เงียบช่วงต้นคลิป"))
    elif b >= dur - 0.05: cuts.append((min(dur, a + S["cut"]["end_pad"]), dur, "เงียบท้ายคลิป"))
    elif b - a >= S["cut"]["max_gap"]: cuts.append((a + pad, b - pad, f"ช่วงเงียบ {b-a:.2f} วิ"))
if S["cut"].get("remove_retakes") and len(words) > 8:
    norm = [w["w"].strip().lower() for w in words]; n = 4 if LANG != "th" else 5
    for i in range(len(words) - n):
        for j in range(i + n, min(len(words) - n, i + 40)):
            if norm[i:i + n] == norm[j:j + n] and words[j]["s"] - words[i + n - 1]["e"] < 6:
                cuts.append((words[i]["s"] - pad, words[j]["s"] - pad, f"พูดซ้ำ: “{''.join(norm[i:i+n]) if LANG=='th' else ' '.join(norm[i:i+n])}”")); break
for a, b in CFG.get("skip", []): cuts.append((a, b, "ตัดตาม config (คำผิด/ไม่จำเป็น)"))
cuts.sort(); merged = []
for a, b, r in cuts:
    if b - a <= 0.02: continue
    if merged and a <= merged[-1][1] + 0.02: merged[-1] = (merged[-1][0], max(b, merged[-1][1]), merged[-1][2] + " + " + r)
    else: merged.append((a, b, r))
keeps, t = [], 0.0
for a, b, _ in merged:
    if a - t > 0.08: keeps.append([t, a])
    t = max(t, b)
if dur - t > 0.08: keeps.append([t, dur])

def m(ts):  # source -> output time
    o = 0.0
    for a, b in keeps:
        if ts < a: return o
        if ts <= b: return o + ts - a
        o += b - a
    return o
TOTAL = sum(b - a for a, b in keeps)
def find_at(at):
    if isinstance(at, (int, float)): return float(at)
    text = "".join(w["w"] for w in words) if LANG == "th" else " ".join(w["w"] for w in words)
    k = text.find(at)
    if k < 0: return None
    pos = 0
    for w in words:
        pos += len(w["w"]) + (0 if LANG == "th" else 1)
        if pos > k: return w["s"]
    return None
emph = CFG.get("emphasis", [])
def is_kept(ts): return any(a <= ts <= b for a, b in keeps)

# sub-segments with zoom levels (alternate per segment, punch on emphasis words)
emph_times = []
if emph:
    joined = "".join(w["w"] for w in words) if LANG == "th" else " ".join(w["w"] for w in words)
    for e in emph:
        k = joined.find(e)
        while k >= 0:
            pos = 0
            for w in words:
                pos += len(w["w"]) + (0 if LANG == "th" else 1)
                if pos > k: emph_times.append(w["s"]); break
            k = joined.find(e, k + len(e))
subs = []
for idx, (a, b) in enumerate(keeps):
    pts = [a] + sorted(t for t in emph_times if a + 0.4 < t < b - 0.4) + [b]
    for j in range(len(pts) - 1):
        lv = S["zoom"]["levels"][idx % len(S["zoom"]["levels"])] + (S["zoom"]["emphasis_punch"] if j > 0 else 0)
        subs.append((pts[j], pts[j + 1], lv))
report += [f"ความยาวต้นฉบับ {dur:.1f} วิ → หลังตัด **{TOTAL:.1f} วิ** ({len(keeps)} ช่วง, {len(merged)} จุดตัด)"]
if TOTAL > S["cut"]["max_len"]: report.append(f"⚠️ ยาวเกิน {S['cut']['max_len']} วิ → เสนอเวอร์ชันสั้น (ให้ Claude เลือกช่วงตัดเพิ่มใน config.skip)")
report += ["", "## จุดตัด (เวลาต้นฉบับ)", "| ตัด | เหตุผล |", "|---|---|"] + [f"| {a:.2f}–{b:.2f} | {r} |" for a, b, r in merged]

# ------------------------------------------------------------- 3. framing (face aware)
vertical = info["w"] / info["h"] < 0.6
fx_all = [f[1] for f in faces if f[1] is not None]
crop = None
if not vertical:  # crop to 9:16 around median face x
    cw = int(info["h"] * 9 / 16) // 2 * 2; cx = np.median(fx_all) if fx_all else info["w"] / 2
    x0 = int(np.clip(cx - cw / 2, 0, info["w"] - cw)); crop = (cw, info["h"], x0, 0)
    report.append(f"ต้นฉบับแนวนอน → crop 9:16 ตามตำแหน่งหน้า (x={x0})")
SW, SH = 2160, 3840  # working scale for smooth zoompan
def face_for(a, b):
    fs = [f for f in faces if a - 0.25 <= f[0] <= b + 0.25 and f[1] is not None]
    if not fs: return None
    cx, cy, fh = np.median([f[1] for f in fs]), np.median([f[2] for f in fs]), np.median([f[3] for f in fs])
    if crop: cx -= crop[2]
    sx = SW / (crop[0] if crop else info["w"]); sy = SH / info["h"]
    return cx * sx, cy * sy, fh * sy
plan_segments = []
for a, b, lv in subs:
    f = face_for(a, b); z0 = lv; z1 = lv + (S["zoom"]["drift"] if S["zoom"]["mode"] != "static" else 0)
    plan_segments.append({"a": a, "b": b, "z0": round(z0, 3), "z1": round(z1, 3), "face": None if f is None else [round(v) for v in f]})
face_ok = sum(1 for s in plan_segments if s["face"]) / max(1, len(plan_segments))
report.append(f"ตรวจพบใบหน้าใน {face_ok*100:.0f}% ของช่วง → จัดเฟรมให้หน้าอยู่ที่ {S['zoom']['face_y']*100:.0f}% ของความสูง")

# ------------------------------------------------------------- 4. captions / text (ASS)
def ass_col(hexs, alpha=0):
    h = hexs.lstrip("#"); return f"&H{alpha:02X}{h[4:6]}{h[2:4]}{h[0:2]}".upper()
def ts(x): x = max(0, x); return f"{int(x//3600)}:{int(x%3600//60):02d}:{x%60:05.2f}"
C = S["captions"]; HK = S["hook"]
font = C["font"]; fontsdir = f"{L.A}/fonts"
border = 3 if C.get("box") else 1
styles = [
 f"Style: Cap,{font},{C['size']},{ass_col(C['color'])},{ass_col(C['color'])},{ass_col(C.get('box') or C['outline'])},{ass_col('#000000',0x80)},0,0,0,0,100,100,1,0,{border},{C['outline_w'] if not C.get('box') else 14},{C['shadow']},2,60,60,{H-C['y']},1",
 f"Style: Hook,KanitXB,{HK['size']},{ass_col(HK['color'])},{ass_col(HK['color'])},{ass_col(HK['outline'])},{ass_col('#000000',0x80)},0,0,0,0,100,100,1,0,1,8,5,8,60,60,{HK['y']},1",
 f"Style: HookA,KanitXB,{int(HK['size']*1.3)},{ass_col(HK['accent'])},{ass_col(HK['accent'])},{ass_col(HK['outline'])},{ass_col('#000000',0x80)},0,0,0,0,100,100,1,0,1,9,6,8,60,60,{HK['y']+int(HK['size']*1.25)},1",
 f"Style: CTA,KanitXB,78,{ass_col(S['cta']['color'])},{ass_col(S['cta']['color'])},{ass_col(S['cta']['box'])},{ass_col('#000000')},0,0,0,0,100,100,1,0,3,18,0,2,60,60,560,1",
 f"Style: Sub,KanitXB,60,{ass_col('#FFFFFF')},{ass_col('#FFFFFF')},{ass_col(HK['outline'])},{ass_col('#000000',0x80)},0,0,0,0,100,100,1,0,1,6,3,2,60,60,700,1",
 f"Style: Disc,KanitXB,34,{ass_col('#FFFFFF')},{ass_col('#FFFFFF')},{ass_col(HK['outline'])},{ass_col('#000000',0x80)},0,0,0,0,100,100,0,0,1,3,2,8,60,60,175,1",
]
ev = []
def add(st, a, b, txt, layer=0): ev.append(f"Dialogue: {layer},{ts(a)},{ts(b)},{st},,0,0,0,,{txt}")
esc = lambda s: s.replace("{", "(").replace("}", ")")
hook_lines = (CFG.get("hook") or {}).get("lines") or []
hook_end = HK["dur"] if hook_lines else 0.0
for i, line in enumerate(hook_lines):
    st = "HookA" if (i == len(hook_lines) - 1 and len(hook_lines) > 1) else "Hook"
    d = 0.25 * i
    add(st, d, hook_end, r"{\fad(120,150)\blur5\t(0,240,\blur0.5)\fscx72\fscy72\t(0,140,\fscx110\fscy110)\t(140,240,\fscx100\fscy100)}" + esc(line), 2)
# card intervals (output time) -> captions move to alt_y
CARDS = []
for c in CFG.get("cards", []):
    s0 = find_at(c["at"])
    if s0 is None or not is_kept(s0): report.append(f"⚠️ ไม่พบคำ “{c['at']}” สำหรับการ์ด"); continue
    o = m(s0); CARDS.append(dict(c, t0=o, t1=min(TOTAL, o + c.get("dur", 1.8))))
BROLL = []
for b_ in CFG.get("broll", []):
    s0 = find_at(b_["at"])
    if s0 is None or not os.path.exists(b_["file"]): report.append(f"⚠️ B-roll ข้าม: {b_}"); continue
    o = m(s0); BROLL.append(dict(b_, t0=o, t1=min(TOTAL, o + b_.get("dur", 1.5))))
busy = ([(max(0, TOTAL - 3.6), TOTAL)] if CFG.get("cta") else []) + [(c["t0"], c["t1"]) for c in CARDS] + [(b_["t0"], b_["t1"]) for b_ in BROLL if b_.get("mode", "pip") == "pip"]
# word list in output time
content_cuts = [(a_, b_) for a_, b_, r_ in merged if ("พูดซ้ำ" in r_ or "config" in r_)]
def dropped(ts): return any(a_ <= ts <= b_ for a_, b_ in content_cuts)
ow = [dict(w, os=m(w["s"]), oe=max(m(w["e"]), m(w["s"]) + 0.12)) for w in words if not dropped((w["s"] + w["e"]) / 2)]
PART = {"ค่ะ", "คะ", "ครับ", "นะ", "จ้ะ", "จ้า"}
if C.get("drop_particles"): ow = [w for w in ow if w["w"] not in PART]
chunks, cur = [], []
def flush():
    if cur: chunks.append(list(cur)); cur.clear()
for w in ow:
    clen = sum(len(x["w"]) for x in cur)
    if cur and (len(cur) >= C["max_words"] or clen + len(w["w"]) > C["max_chars"] or w["os"] - cur[-1]["oe"] > 0.6): flush()
    cur.append(w)
    if w["w"].rstrip()[-1:] in ".!?" or w["w"] in ("ค่ะ", "คะ", "ครับ", "นะคะ", "นะครับ"): flush()
flush()
sep = "" if LANG == "th" else " "
def emph_mask(ch):
    txt = sep.join(w["w"] for w in ch); mask = [False] * len(ch)
    for e in emph:
        k = txt.find(e)
        while k >= 0:
            pos = 0
            for i, w in enumerate(ch):
                st_, en_ = pos, pos + len(w["w"]); pos = en_ + len(sep)
                if st_ < k + len(e) and en_ > k: mask[i] = True
            k = txt.find(e, k + 1)
    return mask
for ci, ch in enumerate(chunks):
    a = max(ch[0]["os"], hook_end if ci == 0 and hook_lines else 0); nxt = chunks[ci + 1][0]["os"] if ci + 1 < len(chunks) else TOTAL
    b = min(nxt, ch[-1]["oe"] + 0.5)
    if b - a < 0.08: continue
    ypos = C["alt_y"] if any(a < x1 and b > x0 - 0.05 for x0, x1 in busy) else C["y"]
    pos = rf"\an2\pos(540,{ypos})"
    mask = emph_mask(ch)
    def col(i, active):
        if mask[i]: return ass_col(C["emphasis_color"])
        if active == i: return ass_col(C["highlight"])
        if C.get("past_color") and active is not None and i < active: return ass_col(C["past_color"])
        return ass_col(C["color"])
    def line(active):
        return "".join(r"{\c" + col(i, active) + "}" + esc(w["w"]) + (sep if i < len(ch) - 1 else "") for i, w in enumerate(ch))
    style = C["style"]
    if style == "karaoke":
        for i, w in enumerate(ch):
            s_ = a if i == 0 else max(a, w["os"]); e_ = b if i == len(ch) - 1 else max(s_ + 0.05, min(b, ch[i + 1]["os"]))
            intro = r"\fscx85\fscy85\t(0,110,\fscx100\fscy100)" if i == 0 else ""
            add("Cap", s_, e_, "{" + pos + intro + "}" + line(i), 1)
    elif style == "pop":
        add("Cap", a, b, "{" + pos + r"\fscx55\fscy55\t(0,90,\fscx112\fscy112)\t(90,160,\fscx100\fscy100)}" + line(len(ch) - 1 if any(mask) else None), 1)
    elif style == "phrase":
        add("Cap", a, b, "{" + pos + r"\fad(110,60)\move(540," + str(ypos + 18) + ",540," + str(ypos) + ",0,160)}" + line(None), 1)
if CFG.get("disclaimer"): add("Disc", hook_end, TOTAL, r"{\fad(300,0)\1a&H30&}" + esc(CFG["disclaimer"]), 0)
cta = CFG.get("cta")
if cta:
    c0 = max(hook_end, TOTAL - 3.6)
    add("CTA", c0 + 0.3, TOTAL, r"{\fscx60\fscy60\t(0,200,\fscx110\fscy110)\t(200,300,\fscx100\fscy100)\t(800,1100,\fscx106\fscy106)\t(1100,1400,\fscx100\fscy100)\t(1900,2200,\fscx106\fscy106)\t(2200,2500,\fscx100\fscy100)}" + esc(cta["text"]), 3)
    if cta.get("sub"): add("Sub", c0, TOTAL, r"{\fad(150,0)}" + esc(cta["sub"]), 3)
ass = "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\n" \
      "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n" \
      + "\n".join(styles) + "\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n" + "\n".join(ev) + "\n"
open(f"{P}/captions.ass", "w").write(ass)
# SRT for CapCut / platform upload
with open(f"{P}/captions.srt", "w") as fsrt:
    for i, ch in enumerate(chunks, 1):
        a, b = ch[0]["os"], ch[-1]["oe"] + 0.3
        f_ = lambda x: f"{int(x//3600):02d}:{int(x%3600//60):02d}:{int(x%60):02d},{int((x%1)*1000):03d}"
        fsrt.write(f"{i}\n{f_(a)} --> {f_(b)}\n{sep.join(w['w'] for w in ch)}\n\n")

plan = {"preset": S["name"], "total": TOTAL, "keeps": keeps, "cuts": merged, "segments": plan_segments,
        "cards": CARDS, "broll": BROLL, "chunks": len(chunks), "hook_end": hook_end}
json.dump(plan, open(f"{P}/plan.json", "w"), ensure_ascii=False, indent=1)
report += ["", f"คำบรรยาย {len(chunks)} ชุด (สไตล์ {C['style']}) · การ์ด {len(CARDS)} · B-roll {len(BROLL)}"]
if args.plan_only:
    open(f"{P}/report.md", "w").write("\n".join(report) + "\n"); print("\n".join(report)); sys.exit(0)

# ------------------------------------------------------------- 5. motion graphics (cards) via PIL pipe
gfx_needed = bool(CARDS)
if gfx_needed:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    EMO = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", 109)
    NAVY = (18, 42, 107); SKY = (125, 211, 252); PINK = (249, 168, 212); WHITE = (255, 255, 255)
    hx = lambda h: tuple(int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    ACC1, ACC2 = hx(S["hook"]["accent"]), hx(S["cta"]["box"])
    @functools.lru_cache(None)
    def fnt(sz): return ImageFont.truetype(f"{L.A}/fonts/KanitXB.ttf", sz, layout_engine=ImageFont.Layout.RAQM)
    @functools.lru_cache(None)
    def timg(s, sz, col):
        f = fnt(sz); bb = f.getbbox(s); im = Image.new("RGBA", (bb[2] - bb[0] + 4, bb[3] - bb[1] + 4))
        ImageDraw.Draw(im).text((2 - bb[0], 2 - bb[1]), s, font=f, fill=col); return im
    @functools.lru_cache(None)
    def emo(e, sz):
        g = Image.new("RGBA", (160, 140)); ImageDraw.Draw(g).text((0, 0), e, font=EMO, embedded_color=True)
        g = g.crop(g.getbbox()); s = sz / max(g.size); return g.resize((max(1, int(g.width * s)), max(1, int(g.height * s))), Image.LANCZOS)
    def ease_back(p): p = min(1, max(0, p)); c1 = 1.70158; return 1 + (c1 + 1) * (p - 1) ** 3 + c1 * (p - 1) ** 2
    def paste(dst, im, cx, cy, sc=1.0, al=1.0):
        if sc <= .01 or al <= .01: return
        if sc != 1: im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.BILINEAR)
        if al < 1: im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v: int(v * al)))
        dst.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))
    CW, CH = 760, 400
    @functools.lru_cache(None)
    def card_base(title):
        pad = 30; im = Image.new("RGBA", (CW + 2 * pad, CH + 2 * pad))
        sh = Image.new("RGBA", im.size); ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 14, pad + CW, pad + CH + 14), 40, fill=NAVY + (80,))
        im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(14))); d = ImageDraw.Draw(im)
        d.rounded_rectangle((pad, pad, pad + CW, pad + CH), 40, fill=ACC1 + (255,)); d.rounded_rectangle((pad + 6, pad + 6, pad + CW - 6, pad + CH - 6), 35, fill=WHITE + (255,))
        hdr = Image.new("RGBA", (CW - 12, 84)); hd = ImageDraw.Draw(hdr)
        for x in range(hdr.width):
            u = x / hdr.width; hd.line([(x, 0), (x, 84)], fill=tuple(int(SKY[i] * (1 - u) + ACC1[i] * u) for i in range(3)) + (255,))
        mk = Image.new("L", hdr.size, 0); ImageDraw.Draw(mk).rounded_rectangle((0, 0, hdr.width - 1, 120), 35, fill=255); hdr.putalpha(mk)
        im.alpha_composite(hdr, (pad + 6, pad + 6)); t = timg(title, 44, NAVY); im.alpha_composite(t, (pad + CW // 2 - t.width // 2, pad + 48 - t.height // 2))
        return im, pad
    def frame(t):
        fr = Image.new("RGBA", (W, H))
        for c in CARDS:
            if not (c["t0"] <= t <= c["t1"]): continue
            lt = t - c["t0"]; base, pad = card_base(c["title"]); cv = base.copy(); items = c.get("items", [])
            n = max(1, len(items)); colw = CW / n
            for i, it in enumerate(items):
                p = (lt - .18 - i * .09) / .32; x = pad + colw * (i + .5)
                paste(cv, emo(it[0], 112 if n <= 4 else 90), x, pad + 200 - 8 * math.sin(lt * 3 + i), ease_back(p), min(1, max(0, p * 3)))
                if len(it) > 1: paste(cv, timg(it[1], 30 if n <= 4 else 26, NAVY), x, pad + 305, 1, min(1, max(0, (lt - .35 - i * .09) / .2)))
            if c.get("note"): paste(cv, timg(c["note"], 28, (190, 60, 130)), pad + CW / 2, pad + 362, 1, min(1, max(0, (lt - .7) / .3)))
            pin = ease_back(lt / .35); pout = min(1, max(0, (t - (c["t1"] - .2)) / .2))
            paste(fr, cv, 540 + 120 * (1 - min(1, lt / .35)), 1215 + 40 * pout, .9 * (.9 + .1 * pin), min(1, lt / .15) * (1 - pout))
        return fr

# ------------------------------------------------------------- 6. render video
grade, gvals = L.grade_filter(src_col, REF.get("colour") if REF else None, S["grade"])
fc = []; inputs = ["-i", SRC]
for i, s in enumerate(plan_segments):
    a, b = s["a"], s["b"]; fr = max(1, round((b - a) * FPS))
    pre = f"[0:v]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS,fps={FPS}" + (f",crop={crop[0]}:{crop[1]}:{crop[2]}:0" if crop else "") + f",scale={SW}:{SH}:flags=lanczos"
    if s["face"]:
        FX, FY, _ = s["face"]; T = S["zoom"]["face_y"]
        xy = f"x='max(0,min(iw-iw/zoom,{FX}-iw/zoom/2))':y='max(0,min(ih-ih/zoom,{FY}-{T}*ih/zoom))'"
    else:
        xy = f"x='(iw-iw/zoom)/2':y='(ih-ih/zoom)*{S['zoom']['anchor']}'"
    fc.append(pre + f",zoompan=z='{s['z0']}+({s['z1']-s['z0']:.4f})*on/{fr}':{xy}:d=1:s={W}x{H}:fps={FPS},setsar=1[v{i}]")
    fc.append(f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.012,afade=t=out:st={max(0,b-a-0.015):.3f}:d=0.015[a{i}]")
n = len(plan_segments)
fc.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[cv][ca]")
fc.append(f"[cv]{grade},format=rgba[g0]"); last = "g0"; k = 1
for j, b_ in enumerate(BROLL):  # user-supplied b-roll
    is_img = b_["file"].lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
    inputs += (["-loop", "1", "-t", f"{TOTAL:.2f}"] if is_img else ["-stream_loop", "-1", "-t", f"{TOTAL:.2f}"]) + ["-i", b_["file"]]
    if b_.get("mode") == "full":
        fc.append(f"[{k}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setpts=PTS-STARTPTS+{b_['t0']:.3f}/TB,format=rgba[b{j}]")
        fc.append(f"[{last}][b{j}]overlay=0:0:enable='between(t,{b_['t0']:.3f},{b_['t1']:.3f})':eof_action=pass[o{j}]")
    else:
        mask = f"{P}/_mask.png"
        if not os.path.exists(mask):
            from PIL import Image, ImageDraw
            mk = Image.new("L", (720, 420), 0); ImageDraw.Draw(mk).rounded_rectangle((0, 0, 719, 419), 36, fill=255); mk.save(mask)
        inputs += ["-loop", "1", "-i", mask]
        fc.append(f"[{k}:v]scale=720:420:force_original_aspect_ratio=increase,crop=720:420,format=rgba[bb{j}];[{k+1}:v]format=gray,scale=720:420[mk{j}];[bb{j}][mk{j}]alphamerge,pad=736:436:8:8:color=white@0,setpts=PTS-STARTPTS+{b_['t0']:.3f}/TB[b{j}]")
        fc.append(f"[{last}][b{j}]overlay=172:1000:enable='between(t,{b_['t0']:.3f},{b_['t1']:.3f})':eof_action=pass:shortest=0[o{j}]"); k += 1
    last = f"o{j}"; k += 1
if gfx_needed:
    inputs += ["-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-framerate", str(FPS), "-i", "pipe:0"]
    fc.append(f"[{last}][{k}:v]overlay=0:0:eof_action=pass[gx]"); last = "gx"
fc.append(f"[{last}]ass={P}/captions.ass:fontsdir={L.A}/fonts,format=yuv420p[vo]")
VC = "afftdn=nf=-48,highpass=f=85,equalizer=f=220:t=q:w=1:g=1.5,equalizer=f=3200:t=q:w=1.2:g=2,equalizer=f=10000:t=h:w=0.7:g=1.5,deesser=i=0.35,acompressor=threshold=-22dB:ratio=3:attack=6:release=90:makeup=2,aresample=48000"
fc.append(f"[ca]{VC}[ao]")
cmd = ["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", "[vo]", "-map", "[ao]", "-t", f"{TOTAL:.3f}",
       "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-r", str(FPS), "-c:a", "pcm_s16le", f"{P}/_video_voice.mov"]
print(f"rendering {TOTAL:.1f}s · {n} segments · cards {len(CARDS)} · broll {len(BROLL)}", flush=True)
if gfx_needed:
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(int(TOTAL * FPS) + 3): pr.stdin.write(frame(i / FPS).tobytes())
    pr.stdin.close(); assert pr.wait() == 0, "ffmpeg failed"
else: L.run(cmd)

# ------------------------------------------------------------- 7. SFX + music + master
N = int((TOTAL + .3) * L.SR); SFX = np.zeros((N, 2)); cues = []
def put(rel, t, g, why):
    if not rel or g <= 0: return
    x = load(rel); i = int(round(max(0, t) * L.SR)); j = min(N, i + len(x)); SFX[i:j] += x[:j - i] * g; cues.append((t, rel, why))
load = functools.lru_cache(None)(L.load_sfx); X = S["sfx"]
if hook_lines: put("synth/whoosh", 0.0, .22, "เปิดคลิป"); put(X["hook"], .3, X["hook_level"], "Hook ขึ้น")
o = 0.0; last_w = -9
for a, b in keeps[:-1]:
    o += b - a
    if X.get("cut_whoosh") and o - last_w >= X["cut_min_gap"] and o > hook_end: put(X["cut_whoosh"], o - .18, X["cut_level"], "ทรานสิชันตรงจุดตัด"); last_w = o
for t in emph_times:
    if is_kept(t): put(X.get("emphasis"), m(t), X.get("emphasis_level", .3), "คำเน้น")
for c in CARDS: put("synth/whoosh", c["t0"] - .1, .12, "การ์ดเข้า"); put(X.get("card"), c["t0"] + .2, .3, "ไอเท็มบนการ์ด")
for b_ in BROLL: put("synth/whoosh", b_["t0"] - .12, .14, "B-roll เข้า")
if cta: put(X.get("cta"), max(hook_end, TOTAL - 3.6) + .3, .42, "ปุ่ม CTA")
L.write_wav(f"{P}/sfx_track.wav", SFX)
mus = None
if S["music"]["enabled"]:
    mus = f"{P}/music.wav"; L.write_wav(mus, L.make_music(TOTAL, S["music"]["bpm"], S["music"]["mood"], drop=hook_end or 0.0))
L.mix_master(f"{P}/_video_voice.mov", mus, f"{P}/sfx_track.wav", f"{P}/FINAL.mp4", music_vol=S["music"]["level"])
os.remove(f"{P}/_video_voice.mov")
with open(f"{P}/cue_sheet.tsv", "w") as f: f.write("time\tsound\tpurpose\n" + "".join(f"{t:.2f}\t{r}\t{w}\n" for t, r, w in sorted(cues)))

# ------------------------------------------------------------- 8. QA
ld = L.loudness(f"{P}/FINAL.mp4"); pr_ = L.probe(f"{P}/FINAL.mp4")
qts = [0.6] + [c["t0"] + 0.8 for c in CARDS[:3]] + [TOTAL * f for f in (.3, .5, .7)] + [TOTAL - 1.0]
qts = sorted(set(round(min(max(q, 0.1), TOTAL - .1), 2) for q in qts))[:8]
for i, q in enumerate(qts): L.run(["ffmpeg", "-v", "error", "-y", "-ss", str(q), "-i", f"{P}/FINAL.mp4", "-frames:v", "1", "-vf", "scale=270:-1", f"{P}/_q{i}.png"])
L.run(["ffmpeg", "-v", "error", "-y", *sum([["-i", f"{P}/_q{i}.png"] for i in range(len(qts))], []), "-filter_complex", f"hstack={len(qts)}", f"{P}/qa.jpg"])
for i in range(len(qts)): os.remove(f"{P}/_q{i}.png")
report += ["", "## ผลลัพธ์", f"- FINAL.mp4 · {pr_['w']}x{pr_['h']} · {pr_['duration']:.1f} วิ · {ld['lufs']} LUFS · peak {ld['peak']} dBFS",
           f"- เกรดสี: contrast {gvals['contrast']:.2f}, saturation {gvals['saturation']:.2f}, brightness {gvals['brightness']:+.3f}, warmth {gvals['warmth']:+.3f}",
           f"- เพลง: {'mood '+S['music']['mood']+' '+str(S['music']['bpm'])+' BPM' if mus else 'ไม่มี'} · SFX {len(cues)} จุด (cue_sheet.tsv)",
           f"- QA frames: qa.jpg (เวลา {', '.join(map(str, qts))})"]
open(f"{P}/report.md", "w").write("\n".join(report) + "\n"); print("\n".join(report))
