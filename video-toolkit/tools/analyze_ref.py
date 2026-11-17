"""Analyze a reference video's editing style and derive preset overrides.

python3 -I tools/analyze_ref.py <ref.mp4> <out_dir> [--lang th]
Writes <out_dir>/style_profile.json, style_report.md, ref_sheet.jpg (2 fps contact sheet for visual review).
Measures: cut rate / shot length, speaking pace & pauses, caption position/size/words/colours (OCR),
face size & zoom-punch frequency, colour grade, loudness and music-bed presence.
"""
import sys, os, re, json, subprocess, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vt_lib as L

ref, out = sys.argv[1], sys.argv[2]; lang = sys.argv[sys.argv.index("--lang") + 1] if "--lang" in sys.argv else "th"
os.makedirs(out, exist_ok=True)
info = L.probe(ref); D = info["duration"]; prof = {"file": os.path.basename(ref), "duration": round(D, 2), "size": [info["w"], info["h"]]}

# 1. cuts (scene changes)
out_ = subprocess.run(["ffmpeg", "-v", "error", "-i", ref, "-vf", "scale=270:-2,select='gte(scene,0)',metadata=print:file=-", "-an", "-f", "null", "-"], capture_output=True, text=True).stdout
pts = [float(x) for x in re.findall(r"pts_time:([\d.]+)", out_)]; sc = [float(x) for x in re.findall(r"scene_score=([\d.]+)", out_)]
sc = np.array(sc[:len(pts)]); thr = max(0.08, float(np.median(sc)) * 8) if len(sc) else 1
cuts = []  # local peaks above adaptive threshold = hard cuts / punch-in jump cuts
for i in range(1, len(sc) - 1):
    if sc[i] > thr and sc[i] >= sc[i - 1] and sc[i] >= sc[i + 1] and (not cuts or pts[i] - cuts[-1] > 0.25): cuts.append(pts[i])
shots = np.diff([0] + cuts + [D])
prof["cuts"] = {"count": len(cuts), "per_min": round(len(cuts) / D * 60, 1), "avg_shot": round(float(shots.mean()), 2), "median_shot": round(float(np.median(shots)), 2)}

# 2. speech pace + pauses
audio = L.load_audio16k(ref)
words = L.transcribe_words(audio, lang)
gaps = [b["s"] - a["e"] for a, b in zip(words, words[1:]) if b["s"] - a["e"] > 0.05]
wpm = len(words) / max(1e-6, (words[-1]["e"] - words[0]["s"]) / 60) if len(words) > 1 else 0
prof["speech"] = {"words": len(words), "wpm": round(wpm), "median_pause": round(float(np.median(gaps)), 2) if gaps else 0,
                  "p90_pause": round(float(np.percentile(gaps, 90)), 2) if gaps else 0, "text": "".join(w["w"] for w in words)[:400]}
json.dump(words, open(f"{out}/ref_words.json", "w"), ensure_ascii=False)

# 3. audio: loudness + music bed (energy that never drops to silence between words)
prof["loudness"] = L.loudness(ref)
sil = L.silences(ref, -45, 0.12); sil_frac = sum(b - a for a, b in sil) / D
gap_db = []
for a, b in zip(words, words[1:]):
    if b["s"] - a["e"] > 0.25:
        seg = audio[int((a["e"] + .05) * 16000):int((b["s"] - .05) * 16000)]
        if len(seg): gap_db.append(20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9))
bed = float(np.median(gap_db)) if gap_db else -90
prof["music"] = {"bed_db_in_pauses": round(bed, 1), "silence_fraction": round(sil_frac, 3), "likely_music": bool(bed > -42 and sil_frac < 0.05)}

# 4. visuals: colour, faces/zoom, captions (OCR)
prof["colour"] = L.colour_stats(ref)
faces = L.face_track(ref, 0.25)
fh = np.array([f[3] / info["h"] for f in faces if f[3]])
zoom_events = int(np.sum(np.abs(np.diff(fh)) / np.maximum(fh[:-1], 1e-6) > 0.15)) if len(fh) > 2 else 0  # jumps only (not drift/lean)
prof["framing"] = {"face_found": round(len(fh) / max(1, len(faces)), 2), "face_height_frac": round(float(np.median(fh)), 3) if len(fh) else None,
                   "face_size_range": [round(float(np.percentile(fh, 15)), 3), round(float(np.percentile(fh, 85)), 3)] if len(fh) else None,  # p15–p85: ignores leaning in/out
                   "zoom_punches_per_min": round(zoom_events / D * 60, 1),
                   "face_y_frac": round(float(np.median([f[2] / info["h"] for f in faces if f[2]])), 3) if len(fh) else None}
try:
    import pytesseract
    from PIL import Image
    caps = []; texts = []; cols = collections.Counter()
    for t in np.arange(0.25, D - 0.1, 0.5):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", ref, "-frames:v", "1", "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        if not raw: continue
        img = np.frombuffer(raw, np.uint8).reshape(1920, 1080, 3)
        d = pytesseract.image_to_data(Image.fromarray(img), lang="tha+eng", config="--psm 11", output_type=pytesseract.Output.DICT)
        boxes = [(d["left"][i], d["top"][i], d["width"][i], d["height"][i], d["text"][i]) for i in range(len(d["text"]))
                 if len(d["text"][i].strip()) >= 2 and float(d["conf"][i]) > 60 and d["height"][i] > 30]
        bands = []  # group into text lines; captions = the band with the largest text area
        for bx in sorted(boxes, key=lambda q: q[1] + q[3] / 2):
            yc = bx[1] + bx[3] / 2
            if bands and abs(yc - bands[-1]["y"]) < max(40, bx[3] * 0.6): bands[-1]["b"].append(bx); bands[-1]["y"] = np.mean([q[1] + q[3] / 2 for q in bands[-1]["b"]])
            else: bands.append({"y": yc, "b": [bx]})
        if not bands: texts.append(""); continue
        boxes = max(bands, key=lambda bd: sum(q[2] * q[3] for q in bd["b"]))["b"]
        ys = [y + h / 2 for _, y, _, h, _ in boxes]; hs = [h for *_, h, _ in boxes]
        band_text = "".join(b[4] for b in boxes) if lang == "th" else " ".join(b[4] for b in boxes)
        if lang == "th":  # Thai has no spaces: OCR boxes != words -> count real words
            from pythainlp.tokenize import word_tokenize as _wt
            nwords = len([w for w in _wt(band_text, engine="newmm", keep_whitespace=False) if w.strip()])
        else: nwords = len(boxes)
        caps.append((float(np.median(ys)), float(np.percentile(hs, 30)), nwords))
        texts.append(band_text)
        for x, y, w, h, _ in boxes:  # bright/saturated text pixels -> colour palette
            px = img[y:y + h, x:x + w].reshape(-1, 3).astype(int)
            lum = px @ [0.3, 0.6, 0.1]; px = px[lum > np.percentile(lum, 70)]
            for p in (px // 32 * 32 + 16)[:: max(1, len(px) // 200)]: cols[tuple(p)] += 1
    import difflib as _dl
    changes = sum(1 for a, b in zip(texts, texts[1:]) if b and _dl.SequenceMatcher(None, a, b).ratio() < 0.6)  # real text change, not OCR noise
    top = [("#%02X%02X%02X" % c) for c, _ in cols.most_common(6)]
    prof["captions"] = {"frames_with_text": round(len(caps) / max(1, len(texts)), 2),
                        "y_center": round(float(np.median([c[0] for c in caps]))) if caps else None,
                        "text_height_px": round(float(np.median([c[1] for c in caps]))) if caps else None,
                        "words_on_screen": round(float(np.median([c[2] for c in caps])), 1) if caps else None,
                        "changes_per_sec": round(changes / D, 2), "colours": top}
except Exception as e:
    prof["captions"] = {"error": str(e)}

# 5. contact sheet for Claude's visual review (fonts, highlight style, b-roll, graphics)
L.run(["ffmpeg", "-v", "error", "-y", "-i", ref, "-vf", "fps=2,scale=135:-1,tile=10x6", "-frames:v", "1", f"{out}/ref_sheet.jpg"])

# 6. derive preset overrides
ov = {"cut": {}, "zoom": {}, "captions": {}, "music": {}}
mp = prof["speech"]["median_pause"]
ov["cut"]["max_gap"] = round(float(np.clip(mp * 1.2 if mp else 0.25, 0.15, 0.35)), 2)
zp = prof["framing"]["zoom_punches_per_min"]
if prof["framing"]["face_size_range"]:
    lo, hi = prof["framing"]["face_size_range"]; ov["zoom"]["levels"] = [1.0, round(float(np.clip(hi / max(lo, 1e-3), 1.03, 1.25)), 2)]
ov["zoom"]["mode"] = "alternate" if zp >= 6 or prof["cuts"]["per_min"] >= 10 else "slow"
if prof["framing"]["face_y_frac"]: ov["zoom"]["face_y"] = float(np.clip(prof["framing"]["face_y_frac"], 0.3, 0.5))
c = prof.get("captions", {})
if c.get("y_center"):
    ov["captions"]["y"] = int(np.clip(c["y_center"] + c["text_height_px"] * 0.6, 900, 1440))
    if lang == "th":  # real Thai ink height (upper/lower marks) -> font size via Pillow metrics
        from vt import layout as _lay
        ov["captions"]["size"] = int(np.clip(_lay.thai_font_size_for_height(c["text_height_px"], f"{L.A}/fonts/KanitXB.ttf", probe="กาบ"), 40, 130))  # OCR word boxes ≈ base-glyph height
    else:
        ov["captions"]["size"] = int(np.clip(c["text_height_px"] * 2.0, 50, 130))
    wos = c["words_on_screen"] or 3
    ov["captions"]["max_words"] = int(np.clip(round(wos), 1, 7))
    ov["captions"]["style"] = "pop" if wos <= 2.2 and c["changes_per_sec"] >= 1.0 else ("karaoke" if wos <= 5 else "phrase")
    cs = c.get("colours") or []
    if cs: ov["captions"]["color"] = cs[0]
    sat = [h for h in cs[1:] if max(int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)) - min(int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)) > 80]
    if sat: ov["captions"]["highlight"] = sat[0]
elif c.get("frames_with_text", 1) < 0.15: ov["captions"]["style"] = "none"
ov["music"]["enabled"] = prof["music"]["likely_music"] or prof["music"]["bed_db_in_pauses"] > -50
prof["preset_overrides"] = ov
_zr = (ov["zoom"].get("levels") or [1, 1])[1]
prof["suggested_base_preset"] = ("bold-hormozi" if ov["captions"].get("style") == "pop" or (prof["cuts"]["per_min"] >= 30 and _zr >= 1.15) else
                                 "minimal-aesthetic" if ov["captions"].get("size", 80) < 60 else
                                 "calm-abdaal" if prof["colour"]["saturation"] < 0.18 else "thai-clear")
json.dump(prof, open(f"{out}/style_profile.json", "w"), ensure_ascii=False, indent=1)

R = [f"# Reference style — {prof['file']}", f"- ยาว {D:.1f} วิ · {info['w']}x{info['h']}",
     f"- จังหวะตัด: {prof['cuts']['count']} คัต ({prof['cuts']['per_min']}/นาที) · shot เฉลี่ย {prof['cuts']['avg_shot']} วิ",
     f"- พูด {prof['speech']['wpm']} คำ/นาที · pause กลาง {prof['speech']['median_pause']} วิ (p90 {prof['speech']['p90_pause']})",
     f"- ซูม: หน้าสูง {prof['framing']['face_height_frac']} ของเฟรม, ช่วง {prof['framing']['face_size_range']}, punch {zp}/นาที",
     f"- แคปชั่น: {json.dumps(prof.get('captions'), ensure_ascii=False)}",
     f"- สี: {prof['colour']}", f"- เสียง: {prof['loudness']} · music bed {prof['music']}",
     f"- preset ใกล้สุด: **{prof['suggested_base_preset']}**", f"- overrides: `{json.dumps(ov, ensure_ascii=False)}`",
     "", "ดู ref_sheet.jpg เพื่อยืนยันฟอนต์/ลูกเล่น/B-roll ด้วยตา แล้วปรับ config.json"]
open(f"{out}/style_report.md", "w").write("\n".join(R) + "\n"); print("\n".join(R))
