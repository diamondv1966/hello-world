"""Shared helpers for the video toolkit: word-level transcription (Thai aware), silences,
face tracking, colour stats, original music + SFX synthesis, mixing/mastering."""
import os, re, json, math, wave, subprocess, functools
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = f"{ROOT}/assets"
SR = 48000

def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)

def probe(path):
    j = json.loads(run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path]).stdout)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    num, den = v.get("r_frame_rate", "30/1").split("/")
    return {"duration": float(j["format"]["duration"]), "w": int(v["width"]), "h": int(v["height"]),
            "fps": float(num) / float(den or 1), "has_audio": any(s["codec_type"] == "audio" for s in j["streams"])}

# ---------------------------------------------------------------- audio / silences
def load_audio16k(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)

def silences(path, noise_db=-33, min_dur=0.2):
    err = subprocess.run(["ffmpeg", "-i", path, "-af", f"silencedetect=noise={noise_db}dB:d={min_dur}", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    out, start = [], None
    for line in err.splitlines():
        m = re.search(r"silence_start: ([\d.]+)", line)
        if m: start = float(m.group(1))
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m and start is not None: out.append((start, float(m.group(1)))); start = None
    if start is not None: out.append((start, probe(path)["duration"]))
    return out

def loudness(path):
    err = subprocess.run(["ffmpeg", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    s = err[err.rfind("Summary"):]
    g = lambda k: float(re.search(k + r":\s+(-?[\d.]+)", s).group(1)) if re.search(k + r":\s+(-?[\d.]+)", s) else None
    return {"lufs": g("I"), "lra": g("LRA"), "peak": g("Peak")}

# ---------------------------------------------------------------- transcription
@functools.lru_cache(None)
def _model():
    from faster_whisper import WhisperModel
    return WhisperModel(f"{A}/model", device="cpu", compute_type="int8")

def _tokens(audio, lang, offset=0.0):
    segs, _ = _model().transcribe(audio, language=lang, beam_size=5, word_timestamps=True,
                                  condition_on_previous_text=False, vad_filter=True)
    toks = []
    for s in segs:
        for w in (s.words or []):
            toks.append((w.word, offset + w.start, offset + w.end))
    return toks

def transcribe_words(audio16k, lang="th"):
    """Return list of words [{'w','s','e'}] (Thai words via pythainlp), robust to skipped spans."""
    toks = _tokens(audio16k, lang)
    # coverage fallback: re-transcribe energetic spans (>2s) that got no tokens
    dur = len(audio16k) / 16000; hop = 0.5
    rms = np.array([np.sqrt(np.mean(audio16k[int(i * 16000):int((i + hop) * 16000)] ** 2) + 1e-12) for i in np.arange(0, dur, hop)])
    speechy = 20 * np.log10(rms) > -38
    covered = np.zeros_like(speechy)
    for _, s, e in toks: covered[int(s / hop):int(e / hop) + 1] = True
    i = 0
    while i < len(speechy):
        if speechy[i] and not covered[i]:
            j = i
            while j < len(speechy) and speechy[j] and not covered[j]: j += 1
            if (j - i) * hop >= 2.0:
                a, b = max(0, i * hop - 0.3), min(dur, j * hop + 0.3)
                toks += _tokens(audio16k[int(a * 16000):int(b * 16000)], lang, offset=a)
            i = j
        else: i += 1
    toks.sort(key=lambda t: t[1])
    if lang != "th":
        return [{"w": t.strip(), "s": round(s, 3), "e": round(e, 3)} for t, s, e in toks if t.strip()]
    # Thai: tokens are sub-word pieces -> char timeline -> pythainlp words
    from pythainlp.tokenize import word_tokenize
    chars, times = [], []
    for t, s, e in toks:
        t = t.replace(" ", "")
        n = max(1, len(t))
        for k, ch in enumerate(t):
            chars.append(ch); times.append((s + (e - s) * k / n, s + (e - s) * (k + 1) / n))
    text = "".join(chars); words, pos = [], 0
    for w in word_tokenize(text, engine="newmm", keep_whitespace=False):
        k = text.find(w, pos)
        if k < 0: continue
        s, e = times[k][0], times[k + len(w) - 1][1]; pos = k + len(w)
        if w.strip(): words.append({"w": w, "s": round(s, 3), "e": round(e, 3)})
    return words

# ---------------------------------------------------------------- face tracking
def face_track(path, step=0.5):
    """Median face box per sample time: list of (t, cx, cy, fh) in source-pixel units (None if no face)."""
    import cv2
    cas = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    cap = cv2.VideoCapture(path); fps = cap.get(cv2.CAP_PROP_FPS) or 30; n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out = []; t = 0.0
    while t * fps < n:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps)); ok, fr = cap.read()
        if not ok: break
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        f = cas.detectMultiScale(g, 1.1, 5, minSize=(int(g.shape[1] * 0.12),) * 2)
        if len(f):
            x, y, w, h = max(f, key=lambda r: r[2] * r[3]); out.append((t, x + w / 2, y + h / 2, h))
        else: out.append((t, None, None, None))
        t += step
    return out

# ---------------------------------------------------------------- colour stats
def colour_stats(path, n=24):
    d = probe(path)["duration"]; vals = []
    for t in np.linspace(0.5, max(0.6, d - 0.5), n):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1", "-vf", "scale=64:-2",
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        if raw: vals.append(np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(float))
    px = np.concatenate(vals) / 255.0
    mx, mn = px.max(1), px.min(1); sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    luma = px @ [0.2126, 0.7152, 0.0722]
    return {"brightness": round(float(luma.mean()), 3), "contrast": round(float(luma.std()), 3),
            "saturation": round(float(sat.mean()), 3), "warmth": round(float((px[:, 0] - px[:, 2]).mean()), 3)}

def grade_filter(src_stats, target=None, base=None):
    """FFmpeg filter string. With target stats (from a reference) -> match brightness/contrast/sat/warmth."""
    g = dict(contrast=1.06, saturation=1.08, brightness=0.0, warmth=0.0, vignette=True, sharpen=0.5, desaturate=False)
    if base: g.update(base)
    if target:
        g["brightness"] = float(np.clip(target["brightness"] - src_stats["brightness"], -0.12, 0.12))
        g["contrast"] = float(np.clip(target["contrast"] / max(src_stats["contrast"], 1e-3), 0.85, 1.3))
        g["saturation"] = float(np.clip(target["saturation"] / max(src_stats["saturation"], 1e-3), 0.0, 1.6))
        g["warmth"] = float(np.clip(target["warmth"] - src_stats["warmth"], -0.08, 0.08))
    f = f"eq=contrast={g['contrast']:.3f}:saturation={0 if g['desaturate'] else g['saturation']:.3f}:brightness={g['brightness']:.3f}"
    w = g["warmth"]
    f += f",colorbalance=rs={w*0.6:.3f}:rm={w*0.5:.3f}:bs={-w*0.6:.3f}:bm={-w*0.5:.3f}"
    if g.get("vignette"): f += ",vignette=angle=PI/7"
    if g.get("sharpen"): f += f",unsharp=5:5:{g['sharpen']}"
    return f, g

# ---------------------------------------------------------------- audio synthesis
rng = np.random.default_rng(7)
def _lp(x, fc):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR); return np.fft.irfft(X / np.sqrt(1 + (f / fc) ** 4), len(x))
def _hp(x, fc):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR); r = (f / fc) ** 2; return np.fft.irfft(X * r / np.sqrt(1 + r ** 2), len(x))
def _env(n, a, d): t = np.arange(n) / SR; return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / d)
def mf(n): return 440 * 2 ** ((n - 69) / 12)
def _st(x, p=0.0): a = (p + 1) * np.pi / 4; return np.stack([x * np.cos(a), x * np.sin(a)], 1)
def _ir(sec, seed):
    r = np.random.default_rng(seed); n = int(sec * SR); t = np.arange(n) / SR
    ir = _lp(r.standard_normal(n) * np.exp(-t / (sec / 6.5)), 6000); ir[:int(.012 * SR)] = 0; return ir / np.sqrt(np.sum(ir ** 2))
def _conv(x, ir):
    n = len(x) + len(ir) - 1; L = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, L) * np.fft.rfft(ir, L), L)[:len(x)]
def verb(st, wet=0.25):
    irl, irr = _ir(2.0, 1), _ir(2.0, 2)
    return st + wet * np.stack([_conv(st[:, 0], irl), _conv(st[:, 1], irr)], 1)
def norm(x, p=0.9): return x / (np.max(np.abs(x)) + 1e-9) * p

def synth_whoosh(d=0.5):
    n = int(d * SR); t = np.arange(n) / SR; x = rng.standard_normal(n); y = np.zeros(n)
    for i in range(0, n, 1024):
        c = 400 + 5000 * np.sin(np.pi * min(1, i / n)) ** 2; blk = x[max(0, i - 512):i + 1536]
        yy = _hp(_lp(blk, c * 1.6), c * 0.5); off = i - max(0, i - 512); seg = yy[off:off + 1024]; y[i:i + len(seg)] = seg[:len(y[i:i + 1024])]
    y *= np.sin(np.pi * t / d) ** 3
    return norm(np.stack([y * np.linspace(1, .3, n), y * np.linspace(.3, 1, n)], 1), .8)
def synth_impact():
    n = int(1.4 * SR); t = np.arange(n) / SR
    x = np.sin(2 * np.pi * np.cumsum(42 + 55 * np.exp(-t / .06)) / SR) * _env(n, .003, .38) + _lp(rng.standard_normal(n), 700) * _env(n, .002, .06) * 1.5
    return norm(verb(_st(x), .3), .9)
def synth_riser(d=1.5):
    n = int(d * SR); t = np.arange(n) / SR; p = t / d
    x = _hp(_lp(rng.standard_normal(n), 6000), 600) * .5 + .35 * sum(np.sin(2 * np.pi * np.cumsum(mf(m) * (1 + .5 * p ** 2)) / SR) for m in (76, 83, 88)) / 3
    x *= p ** 2.2 * (1 - np.exp(-(d - t) / .01)); return norm(verb(np.stack([x, np.roll(x, 500)], 1), .3), .85)

def load_sfx(rel):
    """rel like 'glass/notification' (uisfx CC0) or 'synth/whoosh|impact|riser'."""
    if rel.startswith("synth/"):
        return {"whoosh": synth_whoosh, "impact": synth_impact, "riser": synth_riser}[rel[6:]]()
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", f"{A}/uisfx/sounds/{rel}.mp3", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return norm(np.frombuffer(raw, np.float32).reshape(-1, 2).astype(float))

MOODS = {  # chords (root, voicing), drums density
    "bright": dict(prog=[(41, [57, 60, 64, 65]), (43, [59, 62, 64, 67]), (40, [55, 59, 62, 64]), (45, [55, 60, 64, 67])], drums="lofi"),
    "calm": dict(prog=[(36, [55, 60, 64, 67]), (41, [57, 60, 64, 69]), (45, [57, 60, 64, 67]), (43, [55, 59, 62, 67])], drums="soft"),
    "energetic": dict(prog=[(45, [57, 60, 64, 69]), (41, [57, 60, 65, 69]), (36, [55, 60, 64, 67]), (43, [55, 59, 62, 67])], drums="four"),
    "serious": dict(prog=[(45, [57, 60, 64, 69]), (40, [55, 59, 64, 67]), (41, [57, 60, 65, 69]), (40, [56, 59, 64, 68])], drums="soft"),
}
def make_music(total, bpm=96, mood="bright", drop=None, quiet=()):
    """Original background music (stereo float). drop: time drums enter; quiet: [(a,b)] spans w/o drums + darker."""
    N = int((total + .3) * SR); T = np.arange(N) / SR; M = MOODS.get(mood, MOODS["bright"])
    beat = 60 / bpm; bar = 4 * beat; drop = 0.0 if drop is None else drop; T0 = drop - 2 * bar
    def place(buf, sig, t, g=1.0):
        i = int(round(t * SR))
        if i < 0: sig = sig[-i:]; i = 0
        j = min(len(buf), i + len(sig))
        if i < len(buf): buf[i:j] += sig[:j - i] * g
    EP = np.zeros((N, 2)); PAD = np.zeros((N, 2)); BASS = np.zeros(N); DR = np.zeros((N, 2))
    kick = np.sin(2 * np.pi * np.cumsum(48 + 70 * np.exp(-np.arange(int(.35 * SR)) / SR / .03)) / SR) * _env(int(.35 * SR), .002, .16)
    rim = _hp(_lp(rng.standard_normal(int(.08 * SR)), 6000), 1500) * _env(int(.08 * SR), .0005, .012)
    shk = _hp(rng.standard_normal(int(.07 * SR)), 6000) * _env(int(.07 * SR), .006, .02)
    def ep(m, d, v):
        n = int(d * SR); t = np.arange(n) / SR; f = mf(m)
        return np.sin(2 * np.pi * f * t + 1.8 * np.exp(-t / .25) * np.sin(2 * np.pi * f * t)) * _env(n, .004, .9) * (1 - np.exp(-(d - t) / .05)) * v
    in_quiet = lambda t: any(a <= t < b for a, b in quiet)
    for b in range(-3, int(total / bar) + 3):
        bt = T0 + b * bar
        if bt > total: break
        root, ch = M["prog"][b % 4]; n = int(bar * SR); tt = np.arange(n) / SR
        pad = sum(2 * ((tt * mf(m) * (1 + dd)) % 1) - 1 for m in ch for dd in (-.004, .004)) / 8
        pad *= np.minimum(1, tt / .6) * np.minimum(1, (bar - tt) / .3); place(PAD, _st(pad, -.3), bt, .5); place(PAD, _st(np.roll(pad, 300), .3), bt, .5)
        for off, v, notes in ((0, 1, ch), (1.5 * beat, .55, ch[1:]), (2.5 * beat, .5, [ch[-1] + 12])):
            for m in notes: place(EP, _st(ep(m, 1.3, v * .25), (m - 62) / 30), bt + off)
        nn = int(1.2 * beat * SR); tb = np.arange(nn) / SR
        for off in (0, 2 * beat): place(BASS, np.sin(2 * np.pi * mf(root) * tb) * np.minimum(1, tb / .01) * np.exp(-tb / .6), bt + off)
        full = bt >= drop - .01 and not in_quiet(bt) and bt < total - 1.5
        if full:
            for k in range(4):
                t = bt + k * beat
                if M["drums"] == "four" or k in (0, 2): place(DR, _st(kick), t, .9 if M["drums"] != "soft" else .5)
                if k in (1, 3): place(DR, _st(rim, .15), t, .3)
            if M["drums"] != "soft":
                for s in range(16): place(DR, _st(shk, .35), bt + s * beat / 4 + (.018 if s % 2 else 0), .14 if s % 2 else .08)
    PADf = np.stack([_lp(PAD[:, 0], 1600), _lp(PAD[:, 1], 1600)], 1)
    mus = verb(EP * .9 + PADf * .22, .28) + _st(_lp(BASS, 400)) * .55 + DR * .85
    dark = np.stack([_lp(mus[:, 0], 900), _lp(mus[:, 1], 900)], 1)
    w = np.clip((T - (drop - 1.2)) / 1.2, 0, 1)
    for a, b in quiet: w = np.where((T >= a) & (T < b), w * .35, w)
    mus = dark * (1 - w[:, None]) + mus * w[:, None]
    mus *= (np.minimum(1, T / .35) * np.clip((total + .3 - T) / 2.0, 0, 1))[:, None]
    return norm(mus, .9)

def write_wav(path, st):
    s = (np.clip(st, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(s.tobytes())

def mix_master(video_in, music_wav, sfx_wav, out, music_vol=0.095, sfx_vol=0.45, mute=()):
    vol = "1.0" if not mute else "if(" + "+".join(f"between(t,{a:.2f},{b:.2f})" for a, b in mute) + ",0.0,1.0)"
    ins = ["-i", video_in]; chains = ["[0:a]asplit=2[vo][key]"]; mixin = "[vo]"; k = 1; n = 1
    if music_wav:
        ins += ["-i", music_wav]; chains.append(f"[{k}:a]volume={music_vol},volume='{vol}':eval=frame[mu];[mu][key]sidechaincompress=threshold=0.03:ratio=3:attack=25:release=400:knee=4[mud]"); mixin += "[mud]"; k += 1; n += 1
    else: chains[0] = "[0:a]anull[vo]"
    if sfx_wav: ins += ["-i", sfx_wav]; chains.append(f"[{k}:a]volume={sfx_vol}[fx]"); mixin += "[fx]"; n += 1
    MIX = ";".join(chains) + f";{mixin}amix=inputs={n}:normalize=0:duration=first"
    err = subprocess.run(["ffmpeg", *ins, "-filter_complex", MIX + ",loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"], capture_output=True, text=True).stderr
    J = json.loads(err[err.rfind("{"):err.rfind("}") + 1])
    ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={J['input_i']}:measured_TP={J['input_tp']}:measured_LRA={J['input_lra']}:"
          f"measured_thresh={J['input_thresh']}:offset={J['target_offset']}:linear=true")
    run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", MIX + f",{ln},alimiter=limit=0.86:level=false,aresample=48000[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", out])
