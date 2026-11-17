"""QA visuals: audio_diagnostics + contact_sheet (owner 07-ffmpeg-render-engineer).

Pillow + numpy only. Reads <project_dir>/pipeline_manifest.json.
"""
import json, os, shutil, subprocess, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLKIT = os.path.abspath(os.path.join(_HERE, "..", ".."))
FONT = os.path.join(_TOOLKIT, "assets", "fonts", "KanitRegular.ttf")
QA_COPY_DIR = os.path.join(_TOOLKIT, "artifacts", "qa")
SR = 16000
GAP = 24

RED, BLUE, GREEN = (230, 30, 40), (30, 90, 230), (30, 170, 70)
CUT_COL = {"silence": (170, 170, 170), "head": (90, 90, 90), "tail": (90, 90, 90),
           "retake": (240, 140, 30), "skip": (140, 70, 190)}


def _font(size):
    try:
        return ImageFont.truetype(FONT, size, layout_engine=ImageFont.Layout.RAQM)
    except Exception:
        return ImageFont.load_default()


def _load(project_dir):
    with open(os.path.join(project_dir, "pipeline_manifest.json"), encoding="utf-8") as f:
        return json.load(f)


def _save_manifest(project_dir, m):
    with open(os.path.join(project_dir, "pipeline_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=1)


def _publish(out_png):
    os.makedirs(QA_COPY_DIR, exist_ok=True)
    dst = os.path.join(QA_COPY_DIR, os.path.basename(out_png))
    if os.path.abspath(dst) != os.path.abspath(out_png):
        shutil.copyfile(out_png, dst)
    return dst


def _load_audio(project_dir, m):
    p = os.path.join(project_dir, "audio16k.f32")
    if os.path.exists(p):
        return np.fromfile(p, dtype="<f4")
    src = os.path.join(project_dir, "src.mp4")
    if not os.path.exists(src):
        src = (m.get("src") or {}).get("path") or src
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-vn", "-ac", "1", "-ar", str(SR),
                        "-f", "f32le", "-"], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError("cannot decode source audio: " + r.stderr.decode(errors="ignore")[:200])
    return np.frombuffer(r.stdout, dtype="<f4").copy()


def _spans(x):
    return [(float(a), float(b)) for a, b in (x or []) if b > a]


def _sum_spans(sp):
    return sum(b - a for a, b in sp)


# ---------------------------------------------------------------- audio diagnostics
def audio_diagnostics(project_dir, out_png):
    m = _load(project_dir)
    y = _load_audio(project_dir, m)
    dur = len(y) / SR
    src_dur = float((m.get("src") or {}).get("duration") or dur)
    T = max(dur, src_dur, 1e-3)
    asr = m.get("asr") or {}
    cov = asr.get("coverage") or {}
    words = asr.get("words") or []
    cuts = m.get("cuts") or []
    keeps = m.get("keeps") or []
    qa = m.get("qa") or {}

    W, H = 2000, 900
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    f_h, f_s, f_t = _font(26), _font(18), _font(16)
    L, R = 120, W - 30
    pw = R - L
    X = lambda t: L + (t / T) * pw

    unc = _spans(cov.get("uncovered_spans"))
    unc_s = qa.get("asr_uncovered_s", _sum_spans(unc))
    out_dur = qa.get("duration") or _sum_spans([(a, b) for a, b in keeps])
    parts = [f"project: {m.get('project', os.path.basename(os.path.abspath(project_dir)))}",
             f"src {T:.1f}s", f"words {len(words)}", f"uncovered {unc_s:.1f}s",
             f"cuts {len(cuts)}", f"out {out_dur:.1f}s"]
    if "lufs" in qa:
        parts.append(f"LUFS {qa['lufs']:.1f}")
    if "peak" in qa:
        parts.append(f"peak {qa['peak']:.1f} dBTP")
    d.text((L, 14), "   |   ".join(parts), fill=(20, 20, 20), font=f_h)

    tracks = {"wave": (70, 330), "rms": (350, 580), "cov": (600, 740), "cuts": (760, 840)}
    names = {"wave": "waveform", "rms": "RMS dBFS", "cov": "ASR coverage", "cuts": "cuts / keeps"}
    for k, (y0, y1) in tracks.items():
        d.rectangle([L, y0, R, y1], outline=(200, 200, 200), fill=(250, 250, 252))
        d.text((8, (y0 + y1) // 2 - 10), names[k], fill=(60, 60, 60), font=f_s)

    # Track 1: min/max envelope per pixel column
    y0, y1 = tracks["wave"]
    mid, amp = (y0 + y1) / 2, (y1 - y0) / 2 - 4
    d.line([L, mid, R, mid], fill=(225, 225, 225))
    if len(y):
        edges = np.linspace(0, len(y), pw + 1).astype(int)
        for i in range(pw):
            seg = y[edges[i]:max(edges[i + 1], edges[i] + 1)]
            if len(seg) == 0:
                continue
            lo, hi = float(seg.min()), float(seg.max())
            d.line([L + i, mid - hi * amp, L + i, mid - lo * amp + 1], fill=(40, 90, 170))

    # Track 2: RMS 50 ms
    y0, y1 = tracks["rms"]
    fr = int(0.05 * SR)
    n = len(y) // fr
    if n > 0:
        rms = np.sqrt(np.mean(y[:n * fr].reshape(n, fr).astype(np.float64) ** 2, axis=1) + 1e-12)
        db = np.clip(20 * np.log10(rms), -80, 0)
    else:
        db = np.array([])
    DY = lambda v: y1 - (v + 80) / 80 * (y1 - y0)
    for v in (-60, -45, -35, -20):
        col = (230, 60, 60) if v == -35 else ((240, 150, 40) if v == -45 else (225, 225, 225))
        d.line([L, DY(v), R, DY(v)], fill=col, width=2 if v in (-35, -45) else 1)
        d.text((L + 4, DY(v) - 18), f"{v}" + (" speech" if v == -35 else ""), fill=(90, 90, 90), font=f_t)
    if len(db) > 1:
        pts = [(X(i * 0.05), DY(float(v))) for i, v in enumerate(db)]
        # decimate to ~2 pts/px
        step = max(1, len(pts) // (pw * 2))
        d.line(pts[::step], fill=(30, 120, 60), width=2)

    # Track 3: coverage bands (4 lanes)
    y0, y1 = tracks["cov"]
    lane = (y1 - y0) / 4
    lanes = [("speech", _spans(cov.get("speech_spans")), (205, 205, 205), 0.6),
             ("words", _spans(cov.get("transcribed_spans")) or
              [(w["s"], w["e"]) for w in words if w["e"] > w["s"]], (60, 180, 90), 0.6),
             ("re-run", _spans(cov.get("rerun_spans")), (245, 205, 40), 0.6),
             ("UNCOVERED", unc, (225, 20, 30), 1.0)]
    for li, (nm, sp, col, hf) in enumerate(lanes):
        ly = y0 + li * lane
        d.text((L + 4, ly + 1), nm, fill=(120, 120, 120), font=f_t)
        for a, b in sp:
            xa, xb = X(a), max(X(b), X(a) + 1)
            if nm == "UNCOVERED":
                d.rectangle([xa, y0 + 2, xb, y1 - 2], fill=(225, 20, 30))      # red full-height
            else:
                d.rectangle([xa, ly + 12, xb, ly + lane - 2], fill=col)
    for w in words:
        xs = X(w["s"])
        d.line([xs, y1 - 14, xs, y1 - 2], fill=(20, 80, 40), width=1)

    # Track 4: cuts + keeps
    y0, y1 = tracks["cuts"]
    ym = (y0 + y1) / 2
    for a, b in keeps:
        d.rectangle([X(a), y0 + 4, max(X(b), X(a) + 1), ym - 2], fill=(60, 110, 230))
    for c in cuts:
        col = CUT_COL.get(c.get("kind"), (120, 120, 120))
        d.rectangle([X(c["a"]), ym + 2, max(X(c["b"]), X(c["a"]) + 2), y1 - 4], fill=col)
    lx = L + 260
    for k, col in list(CUT_COL.items()) + [("keep", (60, 110, 230))]:
        d.rectangle([lx, 874, lx + 14, 888], fill=col)
        d.text((lx + 18, 870), k, fill=(60, 60, 60), font=f_t)
        lx += 120

    # dashed boundaries across all tracks
    top, bot = 66, 842
    for c in cuts:
        for t in (c["a"], c["b"]):
            xx = X(t)
            for yy in range(top, bot, 10):
                d.line([xx, yy, xx, yy + 5], fill=(150, 90, 90))
    # time axis ticks every 5 s
    t = 0.0
    while t <= T + 1e-6:
        xx = X(t)
        d.line([xx, tracks["cuts"][1] + 2, xx, tracks["cuts"][1] + 10], fill=(60, 60, 60))
        d.text((xx - 10, tracks["cuts"][1] + 12), f"{t:g}", fill=(60, 60, 60), font=f_t)
        t += 5
    d.text((R - 40, 874), "sec", fill=(90, 90, 90), font=f_t)

    os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
    img.save(out_png)
    _publish(out_png)
    return out_png


# ---------------------------------------------------------------- contact sheet
def _inter(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def _inflate(b, g):
    return [b[0] - g, b[1] - g, b[2] + 2 * g, b[3] + 2 * g]


def _active(items, t):
    return [x for x in items or [] if x.get("t0", 0) <= t < x.get("t1", 0)]


def _face_at(segs, t):
    for s in segs or []:
        if s["oa"] <= t < s["ob"] or (t >= s["ob"] and s is segs[-1] and t <= s["ob"] + 1e-6):
            return s.get("face_out")
    return None


def _pick_times(m, n, out_dur):
    segs, cards, caps = m.get("segments") or [], m.get("cards") or [], m.get("captions") or []
    cand = []
    z = sorted(segs, key=lambda s: -max(s.get("z0", 1), s.get("z1", 1)))
    if z:
        s = z[0]
        cand.append((s["oa"] + s["ob"]) / 2)
    cand += [c["t0"] + 0.6 for c in cards]
    if caps:
        k = min(len(caps), max(2, n // 2))
        idx = np.unique(np.linspace(0, len(caps) - 1, k).round().astype(int))
        cand += [(caps[i]["t0"] + caps[i]["t1"]) / 2 for i in idx]
    cand.append(0.05)
    # remaining strong zoom mids to fill
    cand += [(s["oa"] + s["ob"]) / 2 for s in z[1:]]
    out = []
    for t in cand:
        t = float(min(max(t, 0.0), max(out_dur - 0.1, 0.0)))
        if all(abs(t - u) >= 0.3 for u in out):
            out.append(t)
        if len(out) >= n:
            break
    return sorted(out)


def _grab(final, t, tmp):
    p = os.path.join(tmp, f"f_{t:.3f}.png")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", final, "-frames:v", "1", p],
                   check=True)
    return Image.open(p).convert("RGB")


def contact_sheet(project_dir, out_png, n=8):
    m = _load(project_dir)
    final = os.path.join(project_dir, "FINAL.mp4")
    pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", final],
                        capture_output=True, text=True)
    out_dur = float(pr.stdout.strip() or 0)
    times = _pick_times(m, n, out_dur)
    segs, cards, caps = m.get("segments") or [], m.get("cards") or [], m.get("captions") or []

    TW, TH, COLS, TOP, LBL = 360, 640, 4, 70, 34
    rows = max(1, -(-len(times) // COLS))
    sheet = Image.new("RGB", (COLS * TW, TOP + rows * (TH + LBL)), "white")
    sd = ImageDraw.Draw(sheet)
    f_h, f_l = _font(28), _font(22)
    tiles, total = [], 0
    seen = set()
    with tempfile.TemporaryDirectory() as tmp:
        for i, t in enumerate(times):
            fr = _grab(final, t, tmp)
            if fr.size != (1080, 1920):
                fr = fr.resize((1080, 1920))
            dr = ImageDraw.Draw(fr)
            face = _face_at(segs, t)
            ac, ap = _active(cards, t), _active(caps, t)
            if face:
                dr.rectangle([face[0], face[1], face[0] + face[2], face[1] + face[3]], outline=RED, width=12)
            for c in ac:
                b = c["bbox"]
                dr.rectangle([b[0], b[1], b[0] + b[2], b[1] + b[3]], outline=BLUE, width=12)
            for c in ap:
                b = c["bbox"]
                dr.rectangle([b[0], b[1], b[0] + b[2], b[1] + b[3]], outline=GREEN, width=12)
            reasons = []
            for c in ac:
                ci = cards.index(c)
                cut = c.get("mode") in ("broll_full", "broll_pip") and c["bbox"][2] >= 1000 and c["bbox"][3] >= 1800  # full-frame cut-away
                cut_away = c.get("mode") == "broll_full"
                if face and not cut_away and _inter(face, c["bbox"]) and ("face", ci) not in seen:
                    seen.add(("face", ci)); reasons.append("face-card")
                if cut: continue
                for p in ap:
                    k_ = ("sub", ci, caps.index(p))
                    if _inter(p["bbox"], _inflate(c["bbox"], GAP)) and k_ not in seen:
                        seen.add(k_); reasons.append("sub-card")
            total += len(reasons)
            status = "COLLISION" if reasons else "OK"
            tile = fr.resize((TW, TH), Image.LANCZOS)
            x, y = (i % COLS) * TW, TOP + (i // COLS) * (TH + LBL)
            sheet.paste(tile, (x, y + LBL))
            col = (200, 20, 30) if reasons else (20, 130, 50)
            sd.text((x + 6, y + 3), f"t={t:.2f}s  {status}", fill=col, font=f_l)
            tiles.append({"t": round(t, 3), "status": status, "reasons": reasons,
                          "face": face, "cards": [c["bbox"] for c in ac], "captions": [c["bbox"] for c in ap]})
    sd.text((8, 10), f"contact sheet  |  collisions: {total}  |  face=red card=blue caption=green  |  "
                     f"{len(times)} frames", fill=(20, 20, 20), font=f_h)
    os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
    sheet.save(out_png)
    dst = _publish(out_png)

    qa = m.setdefault("qa", {})
    qa["collision_count"] = total
    imgs = [p for p in qa.get("images", []) if os.path.basename(p) != os.path.basename(out_png)]
    imgs.append(os.path.abspath(out_png))
    qa["images"] = imgs
    _save_manifest(project_dir, m)
    return {"collision_count": total, "tiles": tiles, "png": os.path.abspath(out_png), "copy": dst}
