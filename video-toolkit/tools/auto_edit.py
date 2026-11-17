"""Auto-edit a vertical talking-head clip from a style preset (+ optional reference profile and creative config).

python3 -I tools/auto_edit.py projects/<name> [--preset thai-clear|path.json] [--config projects/<name>/config.json]
                              [--ref projects/<name>/ref/style_profile.json] [--plan-only] [--approved]

project dir must contain src.mp4 (tools/new_project.sh makes it).
Settings layering: preset (default = user_settings.default_preset) <- user_settings.knobs <- ref preset_overrides <- config.json.
automation_level (user_settings, or config "automation_level"): 1 auto, 2 creative-assisted (uses config.json),
3 = write plan + manifest + report and STOP unless --approved.
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
Outputs in the project: asr.json, face_track.json, pipeline_manifest.json, plan.json, captions.ass, captions.srt,
sfx_track.wav, music.wav, FINAL.mp4, qa.jpg, artifacts/qa/*.png, report.md
"""
import sys, os, json, math, copy, argparse, subprocess, functools, hashlib, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vt_lib as L
from vt import asr as vasr, dedup, face, layout, qa_visual

T_START = time.time()
ap = argparse.ArgumentParser()
ap.add_argument("project"); ap.add_argument("--preset", default=None); ap.add_argument("--config")
ap.add_argument("--ref"); ap.add_argument("--plan-only", action="store_true")
ap.add_argument("--approved", action="store_true", help="automation_level 3: plan approved by the user -> render")
args = ap.parse_args()
P = os.path.abspath(args.project); SRC = f"{P}/src.mp4"
W, H, FPS = 1080, 1920, 30
SW, SH = 2160, 3840  # working scale for smooth zoompan

def deep_update(a, b):
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(a.get(k), dict): deep_update(a[k], v)
        else: a[k] = v
    return a

# ------------------------------------------------------------- 0. settings layering
US = json.load(open(f"{L.ROOT}/presets/user_settings.json"))
preset_arg = args.preset or US.get("default_preset", "thai-clear")
if preset_arg.endswith(".json") or "/" in preset_arg:
    pp = preset_arg if os.path.isabs(preset_arg) or os.path.exists(preset_arg) else f"{L.ROOT}/{preset_arg}"
else: pp = f"{L.ROOT}/presets/{preset_arg}.json"
S = json.load(open(pp))
K = US.get("knobs", {})
if "1_cut_max_gap" in K: S["cut"]["max_gap"] = K["1_cut_max_gap"]
if "7_max_len_s" in K: S["cut"]["max_len"] = K["7_max_len_s"]
if "2_zoom" in K: deep_update(S["zoom"], K["2_zoom"])
if "3_captions" in K: deep_update(S["captions"], K["3_captions"])
if "5_music" in K: deep_update(S["music"], K["5_music"])
SFX_ON, SFX_VOL = True, 0.45
if "4_sfx" in K:
    k4 = K["4_sfx"]; SFX_ON = bool(k4.get("enabled", True)); SFX_VOL = k4.get("level", SFX_VOL)
    if k4.get("cut_whoosh") is False: S["sfx"]["cut_whoosh"] = None
CFG = json.load(open(args.config)) if args.config else (json.load(open(f"{P}/config.json")) if os.path.exists(f"{P}/config.json") else {})
REF = json.load(open(args.ref)) if args.ref else None
if REF and REF.get("preset_overrides"): deep_update(S, REF["preset_overrides"])
deep_update(S, {k: v for k, v in CFG.items() if k in S})
LANG = CFG.get("language", US.get("language", "th"))
LEVEL = int(CFG.get("automation_level", US.get("automation_level", 2)))
info = L.probe(SRC)
SRC_W, SRC_H, dur = info["w"], info["h"], info["duration"]
report = [f"# Auto-edit report — {os.path.basename(P)}", f"preset: **{S['name']}** · automation level {LEVEL}" + (f" + ref `{args.ref}`" if REF else ""), ""]

# ------------------------------------------------------------- manifest
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""): h.update(blk)
    return h.hexdigest()
M = {"version": 1, "project": os.path.basename(P),
     "src": {"path": SRC, "sha256": sha256(SRC), "duration": dur, "w": SRC_W, "h": SRC_H, "fps": info["fps"]},
     "settings": {"preset": S["name"], "automation_level": LEVEL, "language": LANG, "resolved": S},
     "asr": {}, "cuts": [], "keeps": [], "segments": [], "captions": [], "cards": [], "broll": [], "qa": {}, "outputs": {}}
def save_manifest(): json.dump(M, open(f"{P}/pipeline_manifest.json", "w"), ensure_ascii=False, indent=1)
save_manifest()

# ------------------------------------------------------------- 1. analysis (cached)
def cached(name, fn):
    f = f"{P}/{name}"
    if os.path.exists(f): return json.load(open(f))
    v = fn(); json.dump(v, open(f, "w"), ensure_ascii=False); return v
audio = L.load_audio16k(SRC)
ASR = cached("asr.json", lambda: vasr.transcribe(audio, LANG))
max_gap, pad, end_pad = S["cut"]["max_gap"], S["cut"]["pad"], S["cut"]["end_pad"]
sil = cached(f"silences_{max_gap}.json", lambda: L.silences(SRC, -33, max_gap))
words, segments = ASR["words"], ASR["segments"]
OVR = CFG.get("transcript_overrides") or []
if OVR:  # corrected Thai text replaces mis-heard Whisper words (times spread by character length)
    import re
    from pythainlp.tokenize import word_tokenize
    def toks_of(text):
        out = []
        for t in word_tokenize(text, engine="newmm", keep_whitespace=False):
            if not t.strip(): continue
            out += [x for x in re.findall(r"\d+(?:[./]\d+)?|\D+", t) if x.strip()] if re.search(r"\d", t) and not t.isdigit() else [t]
        return [t for t in out if t.strip()]
    words = [dict(w) for w in words]; bounds = []
    for o_ in sorted(OVR, key=lambda o: o["s"]):
        inside = [w for w in words if o_["s"] <= (w["s"] + w["e"]) / 2 <= o_["e"]]
        a_, b_ = (inside[0]["s"], inside[-1]["e"]) if inside else (o_["s"], o_["e"])
        words = [w for w in words if not any(w is x for x in inside)]
        tk = toks_of(o_["text"]); tot = sum(len(t) for t in tk) or 1; cum = 0; new_w = []
        voiced, t_ = [], a_  # spread characters over voiced time only (silences inside the span are skipped)
        for sa, sb in sorted(sil):
            if sb <= a_ or sa >= b_: continue
            if sa > t_: voiced.append((t_, min(sa, b_)))
            t_ = max(t_, sb)
        if t_ < b_: voiced.append((t_, b_))
        if not voiced: voiced = [(a_, b_)]
        V = sum(y - x for x, y in voiced)
        def at_v(f):
            r = f * V
            for x, y in voiced:
                if r <= y - x + 1e-9: return x + r
                r -= y - x
            return voiced[-1][1]
        for t in tk:
            new_w.append({"w": t, "s": round(at_v(cum / tot), 3), "e": round(at_v((cum + len(t)) / tot), 3)}); cum += len(t)
        words += new_w; bounds.append(b_)
    words.sort(key=lambda w: w["s"])
    THAI_FINAL = ("นะคะ", "นะครับ", "ค่ะ", "คะ", "ครับ"); segments, i0 = [], 0
    for i, w in enumerate(words):
        last = i == len(words) - 1; t = w["w"]
        brk = last or words[i + 1]["s"] - w["e"] > 0.45 or any(abs(w["e"] - bb) < 1e-3 for bb in bounds) \
            or (t.endswith((".", "!", "?")) and not re.fullmatch(r"\d+[.]?", t)) or (LANG == "th" and t in THAI_FINAL)
        if brk:
            sg = words[i0:i + 1]; segments.append({"text": ("" if LANG == "th" else " ").join(x["w"] for x in sg), "s": sg[0]["s"], "e": sg[-1]["e"], "i0": i0, "i1": i + 1}); i0 = i + 1
    ASR = dict(ASR, words=words, segments=segments, overridden=True, overrides=OVR)
M["asr"] = ASR; save_manifest()
ftrack = cached("face_track.json", lambda: face.track(SRC))
src_col = cached("colour.json", lambda: L.colour_stats(SRC))

# ------------------------------------------------------------- 2. cut plan
retakes = dedup.find_retakes(segments, words, LANG) if (S["cut"].get("remove_retakes") and len(words) > 8) else []
merged, keeps = dedup.plan_cuts(dur, sil, retakes, CFG.get("skip", []), max_gap, pad, end_pad)
M["cuts"], M["keeps"] = merged, keeps; save_manifest()

def m(ts):  # source -> output time
    o = 0.0
    for a, b in keeps:
        if ts < a: return o
        if ts <= b: return o + ts - a
        o += b - a
    return o
TOTAL = sum(b - a for a, b in keeps)
def jtext(): return "".join(w["w"] for w in words) if LANG == "th" else " ".join(w["w"] for w in words)
def word_at_char(k):
    pos = 0
    for w in words:
        pos += len(w["w"]) + (0 if LANG == "th" else 1)
        if pos > k: return w["s"]
    return None
def find_at(at):
    if isinstance(at, (int, float)): return float(at)
    k = jtext().find(at)
    return None if k < 0 else word_at_char(k)
emph = CFG.get("emphasis", [])
def is_kept(ts): return any(a <= ts <= b for a, b in keeps)

emph_times = []
if emph:
    joined = jtext()
    for e in emph:
        k = joined.find(e)
        while k >= 0:
            t_ = word_at_char(k)
            if t_ is not None: emph_times.append(t_)
            k = joined.find(e, k + len(e))
subs = []  # (a, b, zoom level) source spans
for idx, (a, b) in enumerate(keeps):
    pts = [a] + sorted(t for t in emph_times if a + 0.4 < t < b - 0.4) + [b]
    for j in range(len(pts) - 1):
        lv = S["zoom"]["levels"][idx % len(S["zoom"]["levels"])] + (S["zoom"]["emphasis_punch"] if j > 0 else 0)
        subs.append((pts[j], pts[j + 1], lv))
n_retake = sum(1 for c in merged if c["kind"] == "retake")
report += [f"ความยาวต้นฉบับ {dur:.1f} วิ → หลังตัด **{TOTAL:.1f} วิ** ({len(keeps)} ช่วง, {len(merged)} จุดตัด, พูดซ้ำที่ตัด {n_retake})"]
if TOTAL > S["cut"]["max_len"]: report.append(f"⚠️ ยาวเกิน {S['cut']['max_len']} วิ → เสนอเวอร์ชันสั้น (ให้ Claude เลือกช่วงตัดเพิ่มใน config.skip)")
report += ["", "## จุดตัด (เวลาต้นฉบับ)", "| ตัด | ชนิด | เหตุผล |", "|---|---|---|"] + [f"| {c['a']:.2f}–{c['b']:.2f} | {c['kind']} | {c['reason']} |" for c in merged]

# ------------------------------------------------------------- 3. framing (face aware; windows in source px == render geometry)
FACE_Y = S["zoom"]["face_y"]
real_boxes = [p for p in ftrack if p["box"]]
def face_for(a, b):
    bs = [p["box"] for p in real_boxes if a - 0.25 <= p["t"] <= b + 0.25]
    if bs: return [float(np.median([x[i] for x in bs])) for i in range(4)]
    if not real_boxes: return None
    mid = (a + b) / 2; return list(min(real_boxes, key=lambda p: abs(p["t"] - mid))["box"])
def fit(win, strip):  # shift window inside the pre-crop strip
    x = min(max(win[0], strip[0]), strip[0] + strip[2] - win[2]); y = min(max(win[1], strip[1]), strip[1] + strip[3] - win[3])
    return [x, y, win[2], win[3]]
plan_segments, oc = [], 0.0
for a, b, lv in subs:
    fb = face_for(a, b); z0 = lv; z1 = lv + (S["zoom"]["drift"] if S["zoom"]["mode"] != "static" else 0)
    w1 = face.window_for(fb, SRC_W, SRC_H, 1.0, FACE_Y)
    strip = [int(round(w1[0])), int(round(w1[1])), int(round(w1[2])), int(round(w1[3]))]
    win0 = fit(face.window_for(fb, SRC_W, SRC_H, z0, FACE_Y), strip); win1 = fit(face.window_for(fb, SRC_W, SRC_H, z1, FACE_Y), strip)
    trk = [{"t": (a + b) / 2, "box": fb}] if fb and not any(a <= p["t"] <= b and p["box"] for p in ftrack) else ftrack
    fo = face.segment_face_out(trk, a, b, win0, win1)
    plan_segments.append({"a": a, "b": b, "oa": oc, "ob": oc + (b - a), "z0": round(z0, 3), "z1": round(z1, 3),
                          "crop0": [round(v, 2) for v in win0], "crop1": [round(v, 2) for v in win1], "strip": strip,
                          "face_out": None if fo is None else [round(v, 1) for v in fo]})
    oc += b - a
M["segments"] = plan_segments; save_manifest()
face_ok = sum(1 for s in plan_segments if s["face_out"]) / max(1, len(plan_segments))
report.append(f"ตรวจพบใบหน้าใน {face_ok*100:.0f}% ของช่วง → จัดเฟรมให้หน้าอยู่ที่ {FACE_Y*100:.0f}% ของความสูง" + ("" if SRC_W / SRC_H < 0.6 else " (ต้นฉบับแนวนอน → crop 9:16 ตามใบหน้า)"))
faces_out = [{"t0": s["oa"], "t1": s["ob"], "bbox": s["face_out"]} for s in plan_segments if s["face_out"]]

# ------------------------------------------------------------- 4. captions / cards / layout
def ass_col(hexs, alpha=0):
    h = hexs.lstrip("#"); return f"&H{alpha:02X}{h[4:6]}{h[2:4]}{h[0:2]}".upper()
def ts(x): x = max(0, x); return f"{int(x//3600)}:{int(x%3600//60):02d}:{x%60:05.2f}"
C = S["captions"]; HK = S["hook"]
font = C["font"]; fontsdir = f"{L.A}/fonts"; FONT_PATH = f"{fontsdir}/{font}.ttf"
border = 3 if C.get("box") else 1
styles = [
 f"Style: Cap,{font},{C['size']},{ass_col(C['color'])},{ass_col(C['color'])},{ass_col(C.get('box') or C['outline'])},{ass_col('#000000',0x80)},0,0,0,0,100,100,0,0,{border},{C['outline_w'] if not C.get('box') else 14},{C['shadow']},2,60,60,{H-C['y']},1",
 f"Style: Hook,KanitXB,{HK['size']},{ass_col(HK['color'])},{ass_col(HK['color'])},{ass_col(HK['outline'])},{ass_col('#000000',0x80)},0,0,0,0,100,100,0,0,1,8,5,8,60,60,{HK['y']},1",
 f"Style: HookA,KanitXB,{int(HK['size']*1.3)},{ass_col(HK['accent'])},{ass_col(HK['accent'])},{ass_col(HK['outline'])},{ass_col('#000000',0x80)},0,0,0,0,100,100,0,0,1,9,6,8,60,60,{HK['y']+int(HK['size']*1.25)},1",
 f"Style: CTA,KanitXB,78,{ass_col(S['cta']['color'])},{ass_col(S['cta']['color'])},{ass_col(S['cta']['box'])},{ass_col('#000000')},0,0,0,0,100,100,0,0,3,18,0,2,60,60,560,1",
 f"Style: Sub,KanitXB,60,{ass_col('#FFFFFF')},{ass_col('#FFFFFF')},{ass_col(HK['outline'])},{ass_col('#000000',0x80)},0,0,0,0,100,100,0,0,1,6,3,2,60,60,700,1",
 f"Style: Disc,KanitXB,28,{ass_col('#FFFFFF')},{ass_col('#FFFFFF')},{ass_col(HK['outline'])},{ass_col('#000000',0x80)},0,0,0,0,100,100,0,0,1,3,2,8,60,60,175,1",
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

# words in output time; only words inside retake/skip cuts are dropped (silence cuts snap)
content_cuts = [(c["a"], c["b"]) for c in merged if c["kind"] in ("retake", "skip")]
def dropped(ts_): return any(a_ <= ts_ <= b_ for a_, b_ in content_cuts)
ow = [dict(w, os=m(w["s"]), oe=max(m(w["e"]), m(w["s"]) + 0.12)) for w in words if not dropped((w["s"] + w["e"]) / 2)]
if LANG == "th":  # numbers need a space after them in Thai captions ("4 ผมร่วง")
    import re as _re
    for w in ow:
        if _re.fullmatch(r"\d+(?:[./]\d+)?", w["w"]): w["w"] += " "
PART = {"ค่ะ", "คะ", "ครับ", "นะ", "จ้ะ", "จ้า"}
if C.get("drop_particles"): ow = [w for w in ow if w["w"] not in PART]
chunks, cur = [], []
def flush():
    if cur: chunks.append(list(cur)); cur.clear()
for w in ow:
    clen = sum(len(x["w"]) for x in cur)
    if cur and (len(cur) >= C["max_words"] or clen + len(w["w"]) > C["max_chars"] or w["os"] - cur[-1]["oe"] > 0.6): flush()
    cur.append(w)
    if (w["w"].rstrip()[-1:] in ".!?" and not w["w"].rstrip()[:-1].isdigit()) or w["w"] in ("ค่ะ", "คะ", "ครับ", "นะคะ", "นะครับ"): flush()
flush()
sep = "" if LANG == "th" else " "
START_BAD = ("ค่ะ", "คะ", "ครับ", "นะคะ", "นะครับ")
_c2 = []
for ch in chunks:  # never start a chunk with a sentence particle
    if _c2 and ch[0]["w"].strip() in START_BAD:
        k_ = 0
        while k_ < len(ch) and ch[k_]["w"].strip() in START_BAD: k_ += 1
        _c2[-1] += ch[:k_]; ch = ch[k_:]
        if not ch: continue
    _c2.append(ch)
chunks = _c2
def cdur(ch): return ch[-1]["oe"] - ch[0]["os"]
def ctext(ch): return sep.join(w["w"] for w in ch)
i_ = 0
while i_ < len(chunks):  # merge tiny single-word chunks (<0.6 s)
    ch = chunks[i_]
    if len(ch) == 1 and cdur(ch) < 0.6:
        if i_ > 0 and len(ctext(chunks[i_ - 1]) + ctext(ch)) <= C["max_chars"] + 6: chunks[i_ - 1] += ch; del chunks[i_]; continue
        if i_ + 1 < len(chunks) and len(ctext(ch) + ctext(chunks[i_ + 1])) <= C["max_chars"] + 6: chunks[i_ + 1] = ch + chunks[i_ + 1]; del chunks[i_]; continue
    i_ += 1
if LANG == "th":  # space after repetition mark ๆ when more Thai follows
    for ch in chunks:
        for w, nx in zip(ch, ch[1:]):
            if w["w"].endswith("ๆ"): w["w"] = w["w"].rstrip() + " "
CAPS = []  # manifest captions (output time), chunk index in "ci"
for ci, ch in enumerate(chunks):
    a = max(ch[0]["os"], hook_end if ci == 0 and hook_lines else 0); nxt = chunks[ci + 1][0]["os"] if ci + 1 < len(chunks) else TOTAL
    b = min(nxt, ch[-1]["oe"] + 0.5)
    if b - a < 0.08: continue
    text = sep.join(w["w"] for w in ch)
    CAPS.append({"t0": round(a, 3), "t1": round(b, 3), "text": text, "ci": ci, "y": C["y"],
                 "bbox": layout.text_bbox(text, FONT_PATH, C["size"], bottom_y=C["y"], outline=C["outline_w"])})

cta = CFG.get("cta")
CTA_T0 = max(hook_end, TOTAL - 3.6)
# ONE stable caption bottom y for the whole clip: below the lowest padded face box, clamped to [preset y, 1385]
if CAPS:
    typ = max(CAPS, key=lambda c: len(c["text"]))["text"]
    cap_h = layout.text_bbox(typ, FONT_PATH, C["size"], bottom_y=C["y"], outline=C["outline_w"])[3]
    face_bot = max([s_["face_out"][1] + s_["face_out"][3] for s_ in plan_segments if s_["face_out"]] or [0])
    CAP_Y = int(min(max(face_bot + 24 + cap_h, C["y"]), 1360))
    for c in CAPS:
        c["y"] = CAP_Y; c["bbox"] = layout.text_bbox(c["text"], FONT_PATH, C["size"], bottom_y=CAP_Y, outline=C["outline_w"])
else: CAP_Y = C["y"]
def place_cascade(t0, t1, sizes):
    for wh in sizes:
        pl = layout.place_card(t0, t1, wh, faces_out, CAPS, safe={"top": 140})
        if pl["mode"] != "broll_full": return pl
    return pl
CARDS = []  # drawn cards: dict(c, t0, t1, bbox, mode, scale)
for c in CFG.get("cards", []):
    s0 = find_at(c["at"])
    if s0 is None or not is_kept(s0): report.append(f"⚠️ ไม่พบคำ “{c['at']}” สำหรับการ์ด"); continue
    o = m(s0); t0, t1 = o, min(TOTAL, o + c.get("dur", 1.8))
    pl = place_cascade(t0, t1, [(760, 400), (684, 360), (570, 300)])
    if pl["mode"] == "broll_full": pl = {"bbox": [122, 540, 836, 440], "mode": "broll_full", "scale": 1.1}  # actual card rect (x1.1 at y=760)
    CARDS.append(dict(c, t0=t0, t1=t1, bbox=pl["bbox"], mode=pl["mode"], scale=pl["scale"]))
BROLL = []
for b_ in CFG.get("broll", []):
    s0 = find_at(b_["at"])
    if s0 is None or not os.path.exists(b_["file"]): report.append(f"⚠️ B-roll ข้าม: {b_}"); continue
    o = m(s0); t0, t1 = o, min(TOTAL, o + b_.get("dur", 1.5))
    if b_.get("mode", "pip") == "full": bbox, mode = [0, 0, W, H], "broll_full"
    else:
        pl = place_cascade(t0, t1, [(736, 436), (552, 327), (442, 262)])
        bbox, mode = pl["bbox"], ("broll_full" if pl["mode"] == "broll_full" else "broll_pip")
    BROLL.append(dict(b_, t0=t0, t1=t1, bbox=bbox, mode=mode))
obstacles = [dict(c, mode="card") for c in CARDS] + [b_ for b_ in BROLL if b_["mode"] == "broll_pip"]  # cut-away card rects count too
CAPS = layout.resolve_captions(CAPS, obstacles, faces_out)
def _ov(a, b): return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]
soft = sum(1 for c in CAPS for f in faces_out if f["t0"] < c["t1"] and c["t0"] < f["t1"] and _ov(c["bbox"], f["bbox"]))
cut_hits = sum(1 for c in CAPS for k_ in CARDS if k_["mode"] == "broll_full" and k_["t0"] < c["t1"] and c["t0"] < k_["t1"] and _ov(layout._grow(c["bbox"], 24), k_["bbox"]))
M["captions"] = [{k: v for k, v in c.items() if k != "ci"} for c in CAPS]
M["cards"] = [{"t0": round(c["t0"], 3), "t1": round(c["t1"], 3), "bbox": c["bbox"], "mode": c["mode"], "scale": c["scale"], "title": c.get("title")} for c in CARDS] + \
             [{"t0": round(b_["t0"], 3), "t1": round(b_["t1"], 3), "bbox": b_["bbox"], "mode": b_["mode"], "file": b_["file"]} for b_ in BROLL]
M["broll"] = [{"t0": b_["t0"], "t1": b_["t1"], "file": b_["file"], "mode": b_["mode"], "bbox": b_["bbox"]} for b_ in BROLL]
save_manifest()

# ---- overlays (hook / CTA / disclaimer) with bboxes, for QA
def top_bbox(text, size, top_y, outline=8, grow=0):
    b = layout.text_bbox(text, f"{fontsdir}/KanitXB.ttf", size, bottom_y=0, outline=outline)
    h = b[3] + int(0.25 * size)
    return [b[0] - grow, int(top_y) - grow, b[2] + 2 * grow, h + 2 * grow]
OVERLAYS = []
for i, line in enumerate(hook_lines):
    last_l = i == len(hook_lines) - 1 and len(hook_lines) > 1
    OVERLAYS.append({"kind": "hook", "t0": 0.25 * i, "t1": hook_end, "text": line,
                     "bbox": top_bbox(line, int(HK["size"] * 1.3) if last_l else HK["size"], HK["y"] + (int(HK["size"] * 1.25) if last_l else 0), 9 if last_l else 8)})
CTA_SIZE, CTA_Y, SUB_Y = 78, 340, 250
if cta:
    cface = [f["bbox"] for f in faces_out if f["t1"] > CTA_T0 and f["t0"] < TOTAL]
    mk = lambda sz: top_bbox(cta["text"], sz, CTA_Y, 18, grow=int(0.06 * sz))
    if any(layout._inter(mk(CTA_SIZE), fb_) for fb_ in cface): CTA_SIZE = 64
    OVERLAYS.append({"kind": "cta", "t0": CTA_T0 + 0.3, "t1": TOTAL, "text": cta["text"], "bbox": mk(CTA_SIZE)})
    if cta.get("sub"): OVERLAYS.append({"kind": "cta_sub", "t0": CTA_T0, "t1": TOTAL, "text": cta["sub"], "bbox": top_bbox(cta["sub"], 60, SUB_Y, 6)})
if CFG.get("disclaimer"):
    OVERLAYS.append({"kind": "disclaimer", "t0": hook_end, "t1": TOTAL, "text": CFG["disclaimer"],
                     "bbox": layout.text_bbox(CFG["disclaimer"], f"{fontsdir}/KanitXB.ttf", 28, bottom_y=1428, outline=3)})
for o_ in OVERLAYS: o_["t0"] = round(o_["t0"], 3); o_["t1"] = round(o_["t1"], 3)
M["overlays"] = OVERLAYS; save_manifest()

cap_by_ci = {c["ci"]: c for c in CAPS}
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
    cp = cap_by_ci.get(ci)
    if not cp: continue
    a, b = cp["t0"], cp["t1"]; ypos = int(cp["y"])
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
if CFG.get("disclaimer"): add("Disc", hook_end, TOTAL, r"{\an2\pos(540,1428)\fad(300,0)\1a&H30&}" + esc(CFG["disclaimer"]), 0)
if cta:
    add("CTA", CTA_T0 + 0.3, TOTAL, r"{\an8\pos(540," + str(CTA_Y) + r")\fs" + str(CTA_SIZE) + r"\fscx60\fscy60\t(0,200,\fscx110\fscy110)\t(200,300,\fscx100\fscy100)\t(800,1100,\fscx106\fscy106)\t(1100,1400,\fscx100\fscy100)\t(1900,2200,\fscx106\fscy106)\t(2200,2500,\fscx100\fscy100)}" + esc(cta["text"]), 3)
    if cta.get("sub"): add("Sub", CTA_T0, TOTAL, r"{\an8\pos(540," + str(SUB_Y) + r")\fad(150,0)}" + esc(cta["sub"]), 3)
ass = "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\n" \
      "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n" \
      + "\n".join(styles) + "\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n" + "\n".join(ev) + "\n"
open(f"{P}/captions.ass", "w").write(ass)
with open(f"{P}/captions.srt", "w") as fsrt:  # SRT for CapCut / platform upload
    for i, ch in enumerate(chunks, 1):
        a, b = ch[0]["os"], ch[-1]["oe"] + 0.3
        if i < len(chunks): b = min(b, chunks[i][0]["os"] - 0.02)
        b = max(b, a + 0.05)
        f_ = lambda x: f"{int(x//3600):02d}:{int(x%3600//60):02d}:{int(x%60):02d},{int((x%1)*1000):03d}"
        fsrt.write(f"{i}\n{f_(a)} --> {f_(b)}\n{sep.join(w['w'] for w in ch)}\n\n")

plan = {"preset": S["name"], "total": TOTAL, "keeps": keeps, "cuts": merged, "segments": plan_segments,
        "cards": M["cards"], "broll": M["broll"], "chunks": len(chunks), "hook_end": hook_end}
json.dump(plan, open(f"{P}/plan.json", "w"), ensure_ascii=False, indent=1)
pre_qa = layout.count_collisions(M)
M["qa"] = {"collision_count": pre_qa["collision_count"], "face_card_overlaps": pre_qa["face_card_overlaps"],
           "sub_card_overlaps": pre_qa["sub_card_overlaps"], "duration": TOTAL,
           "caption_face_soft_overlaps": soft, "caption_cutaway_overlaps": cut_hits, "caption_y": CAP_Y,
           "asr_uncovered_s": round(sum(b - a for a, b in ASR.get("coverage", {}).get("uncovered_spans", [])), 2)}
save_manifest()
mode_n = {k: sum(1 for c in M["cards"] if c["mode"] == k) for k in ("card", "card_small", "broll_pip", "broll_full")}
report += [f"คำเน้นที่พบ {len(emph_times)} จุด: " + ", ".join(f"{e}×{jtext().count(e)}" for e in emph)]
report += ["", f"คำบรรยาย {len(CAPS)} ชุด (สไตล์ {C['style']}) · การ์ด {len(CARDS)} · B-roll {len(BROLL)} · วางการ์ด {mode_n} · collision (แผน) {pre_qa['collision_count']}"]
if args.plan_only or (LEVEL == 3 and not args.approved):
    if LEVEL == 3 and not args.plan_only: report.append("⏸ automation_level 3: รอผู้ใช้อนุมัติแผน → รันซ้ำพร้อม --approved")
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
    BACKDROP = Image.new("RGBA", (W, H), NAVY + (204,))  # #122A6B @ 80%
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
            pin = ease_back(lt / .35); pout = min(1, max(0, (t - (c["t1"] - .2)) / .2)); al = min(1, lt / .15) * (1 - pout)
            if c["mode"] == "broll_full":  # cut-away: navy 80% backdrop + card x1.1 at y=760
                paste(fr, BACKDROP, W / 2, H / 2, 1, al)
                paste(fr, cv, 540, 760 + 40 * pout, 1.1 * (.9 + .1 * pin), al)
            else:
                bx, by, bw, bh = c["bbox"]
                paste(fr, cv, bx + bw / 2 + 120 * (1 - min(1, lt / .35)), by + bh / 2 + 40 * pout, (bw / CW) * (.9 + .1 * pin), al)
        return fr

# ------------------------------------------------------------- 6. render video
grade, gvals = L.grade_filter(src_col, REF.get("colour") if REF else None, S["grade"])
fc = []; inputs = ["-i", SRC]
for i, s in enumerate(plan_segments):
    a, b = s["a"], s["b"]; fr = max(1, round((b - a) * FPS)); den = max(1, fr - 1)
    sx, sy, sw, sh = s["strip"]; kx, ky = SW / sw, SH / sh
    c0, c1 = s["crop0"], s["crop1"]
    z0, z1 = sw / c0[2], sw / c1[2]  # exact windows at both ends: zoom = strip_w / window_w
    xe = f"({(c0[0]-sx)*kx:.3f}+({(c1[0]-c0[0])*kx:.3f})*on/{den})"; ye = f"({(c0[1]-sy)*ky:.3f}+({(c1[1]-c0[1])*ky:.3f})*on/{den})"
    pre = f"[0:v]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS,fps={FPS},crop={sw}:{sh}:{sx}:{sy},scale={SW}:{SH}:flags=lanczos"
    fc.append(pre + f",zoompan=z='{z0:.5f}+({z1-z0:.5f})*on/{den}':x='{xe}':y='{ye}':d=1:s={W}x{H}:fps={FPS},setsar=1[v{i}]")
    fc.append(f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.012,afade=t=out:st={max(0,b-a-0.015):.3f}:d=0.015[a{i}]")
n = len(plan_segments)
fc.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[cv][ca]")
fc.append(f"[cv]{grade},format=rgba[g0]"); last = "g0"; k = 1
for j, b_ in enumerate(BROLL):  # user-supplied b-roll
    is_img = b_["file"].lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
    inputs += (["-loop", "1", "-t", f"{TOTAL:.2f}"] if is_img else ["-stream_loop", "-1", "-t", f"{TOTAL:.2f}"]) + ["-i", b_["file"]]
    if b_["mode"] == "broll_full":
        fc.append(f"[{k}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setpts=PTS-STARTPTS+{b_['t0']:.3f}/TB,format=rgba[b{j}]")
        fc.append(f"[{last}][b{j}]overlay=0:0:enable='between(t,{b_['t0']:.3f},{b_['t1']:.3f})':eof_action=pass[o{j}]")
    else:
        bx, by, bw, bh = b_["bbox"]; iw, ih = bw - 16, bh - 16
        mask = f"{P}/_mask_{iw}x{ih}.png"
        if not os.path.exists(mask):
            from PIL import Image, ImageDraw
            mk = Image.new("L", (iw, ih), 0); ImageDraw.Draw(mk).rounded_rectangle((0, 0, iw - 1, ih - 1), 36, fill=255); mk.save(mask)
        inputs += ["-loop", "1", "-i", mask]
        fc.append(f"[{k}:v]scale={iw}:{ih}:force_original_aspect_ratio=increase,crop={iw}:{ih},format=rgba[bb{j}];[{k+1}:v]format=gray,scale={iw}:{ih}[mk{j}];[bb{j}][mk{j}]alphamerge,pad={bw}:{bh}:8:8:color=white@0,setpts=PTS-STARTPTS+{b_['t0']:.3f}/TB[b{j}]")
        fc.append(f"[{last}][b{j}]overlay={bx}:{by}:enable='between(t,{b_['t0']:.3f},{b_['t1']:.3f})':eof_action=pass:shortest=0[o{j}]"); k += 1
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
T_RENDER = time.time()
if gfx_needed:
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for i in range(int(TOTAL * FPS) + 3): pr.stdin.write(frame(i / FPS).tobytes())
    except BrokenPipeError: pass
    try: pr.stdin.close()
    except BrokenPipeError: pass
    assert pr.wait() == 0, "ffmpeg failed"
else: L.run(cmd)
render_s = time.time() - T_RENDER

# ------------------------------------------------------------- 7. SFX + music + master
N = int((TOTAL + .3) * L.SR); SFX = np.zeros((N, 2)); cues = []
def put(rel, t, g, why):
    if not SFX_ON or not rel or g <= 0: return
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
if cta: put(X.get("cta"), CTA_T0 + .3, .42, "ปุ่ม CTA")
sfx_wav = None
if SFX_ON: L.write_wav(f"{P}/sfx_track.wav", SFX); sfx_wav = f"{P}/sfx_track.wav"
mus = None
if S["music"]["enabled"]:
    mus = f"{P}/music.wav"; L.write_wav(mus, L.make_music(TOTAL, S["music"]["bpm"], S["music"]["mood"], drop=hook_end or 0.0))
L.mix_master(f"{P}/_video_voice.mov", mus, sfx_wav, f"{P}/FINAL.mp4", music_vol=S["music"]["level"], sfx_vol=SFX_VOL)
os.remove(f"{P}/_video_voice.mov")
with open(f"{P}/cue_sheet.tsv", "w") as f: f.write("time\tsound\tpurpose\n" + "".join(f"{t:.2f}\t{r}\t{w}\n" for t, r, w in sorted(cues)))

# ------------------------------------------------------------- 8. QA
ld = L.loudness(f"{P}/FINAL.mp4"); pr_ = L.probe(f"{P}/FINAL.mp4")
qts = [0.6] + [c["t0"] + 0.8 for c in CARDS[:3]] + [TOTAL * f for f in (.3, .5, .7)] + [TOTAL - 1.0]
qts = sorted(set(round(min(max(q, 0.1), TOTAL - .1), 2) for q in qts))[:8]
for i, q in enumerate(qts): L.run(["ffmpeg", "-v", "error", "-y", "-ss", str(q), "-i", f"{P}/FINAL.mp4", "-frames:v", "1", "-vf", "scale=270:-1", f"{P}/_q{i}.png"])
L.run(["ffmpeg", "-v", "error", "-y", *sum([["-i", f"{P}/_q{i}.png"] for i in range(len(qts))], []), "-filter_complex", f"hstack={len(qts)}", f"{P}/qa.jpg"])
for i in range(len(qts)): os.remove(f"{P}/_q{i}.png")
col_ = layout.count_collisions(M)
ovc = qa_visual.overlay_collisions(M)
col_["collision_count"] += len(ovc); col_["details"] = col_["details"] + ovc
M["qa"].update({"collision_count": col_["collision_count"], "face_card_overlaps": col_["face_card_overlaps"], "sub_card_overlaps": col_["sub_card_overlaps"],
                "overlay_collisions": len(ovc), "collision_details": col_["details"], "lufs": ld["lufs"], "peak": ld["peak"], "duration": pr_["duration"], "render_s": round(render_s, 1)})
M["outputs"] = {"final": f"{P}/FINAL.mp4", "captions_ass": f"{P}/captions.ass", "captions_srt": f"{P}/captions.srt", "cue_sheet": f"{P}/cue_sheet.tsv", "qa_strip": f"{P}/qa.jpg"}
save_manifest()
qdir = f"{P}/artifacts/qa"; os.makedirs(qdir, exist_ok=True)
qa_visual.audio_diagnostics(P, f"{qdir}/audio_diagnostics.png")
cs = qa_visual.contact_sheet(P, f"{qdir}/contact_sheet.png")
M = json.load(open(f"{P}/pipeline_manifest.json"))  # qa_visual wrote images + its own collision_count
vis_n = cs["collision_count"]; qa_ = M["qa"]
qa_["collision_count_layout"] = col_["collision_count"]; qa_["collision_count_visual"] = vis_n
qa_["collision_count"] = max(col_["collision_count"], vis_n)
M["outputs"]["qa_images"] = [f"{qdir}/audio_diagnostics.png", f"{qdir}/contact_sheet.png"]
save_manifest()
report += ["", "## ผลลัพธ์", f"- FINAL.mp4 · {pr_['w']}x{pr_['h']} · {pr_['duration']:.1f} วิ · {ld['lufs']} LUFS · peak {ld['peak']} dBFS",
           f"- เกรดสี: contrast {gvals['contrast']:.2f}, saturation {gvals['saturation']:.2f}, brightness {gvals['brightness']:+.3f}, warmth {gvals['warmth']:+.3f}",
           f"- เพลง: {'mood '+S['music']['mood']+' '+str(S['music']['bpm'])+' BPM' if mus else 'ไม่มี'} · SFX {len(cues)} จุด (cue_sheet.tsv)",
           f"- QA frames: qa.jpg (เวลา {', '.join(map(str, qts))}) · artifacts/qa/contact_sheet.png · artifacts/qa/audio_diagnostics.png",
           f"- collision_count {qa_['collision_count']} (layout {col_['collision_count']} / visual {vis_n}) · ASR ไม่ครอบคลุม {qa_.get('asr_uncovered_s', 0)} วิ · render {render_s:.0f} วิ"]
open(f"{P}/report.md", "w").write("\n".join(report) + "\n"); print("\n".join(report))
print(f"QA: duration {pr_['duration']:.1f}s LUFS {ld['lufs']} peak {ld['peak']} collisions {qa_['collision_count']} "
      f"(layout {col_['collision_count']}/visual {vis_n}) uncovered {qa_.get('asr_uncovered_s', 0)}s retakes {n_retake} total {time.time()-T_START:.0f}s")
