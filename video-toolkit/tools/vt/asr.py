"""ASR for Thai (and other) speech: zero-skip chunked Whisper + gap re-run + segments.

transcribe(audio16k, lang="th") -> {"words": [{w,s,e}], "segments": [{text,s,e,i0,i1}],
                                    "coverage": {speech_spans, transcribed_spans, rerun_spans, uncovered_spans}}
"""
import os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vt_lib as L  # noqa: E402

SR = 16000
SIL_DB, SIL_MIN = -40.0, 0.3          # chunk-cut silence
SPEECH_DB, GAP_WIN, GAP_MIN = -35.0, 0.5, 2.0
CHUNK_MIN, CHUNK_MAX = 20.0, 30.0
PAUSE_SPLIT = 0.45
THAI_FINAL = ("นะคะ", "นะครับ", "ค่ะ", "คะ", "ครับ")


# ------------------------------------------------------------------ helpers
def _db(x):
    return 20 * np.log10(np.sqrt(np.mean(np.square(x, dtype=np.float64)) + 1e-12))


def _frame_db(a, frame):
    n = len(a) // frame
    if n == 0:
        return np.zeros(0)
    f = a[:n * frame].astype(np.float64).reshape(n, frame)
    return 20 * np.log10(np.sqrt((f ** 2).mean(1) + 1e-12))


def _silences(a, thr=SIL_DB, min_dur=SIL_MIN, frame_s=0.05):
    frame = int(SR * frame_s)
    db = _frame_db(a, frame)
    out, i = [], 0
    while i < len(db):
        if db[i] < thr:
            j = i
            while j < len(db) and db[j] < thr:
                j += 1
            if (j - i) * frame_s >= min_dur:
                out.append((i * frame_s, j * frame_s))
            i = j
        else:
            i += 1
    return out


def _chunks(a):
    """[(start_s, end_s)] chunks of 20-30 s, cut at the longest silence in the window."""
    dur = len(a) / SR
    sil = _silences(a)
    out, t = [], 0.0
    while dur - t > CHUNK_MAX:
        cands = [(e - s, (s + e) / 2) for s, e in sil if t + CHUNK_MIN <= (s + e) / 2 <= t + CHUNK_MAX]
        cut = max(cands)[1] if cands else t + CHUNK_MAX
        out.append((t, cut)); t = cut
    out.append((t, dur))
    return out


def _merge(spans, tol=0.0):
    out = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1] + tol:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [[round(a, 3), round(b, 3)] for a, b in out]


def _tokens(audio, lang, offset, vad=True):
    kw = dict(language=lang, beam_size=5, word_timestamps=True, condition_on_previous_text=False)
    if vad:
        kw.update(vad_filter=True, vad_parameters={"min_silence_duration_ms": 400, "speech_pad_ms": 250})
    segs, _ = L._model().transcribe(audio, **kw)
    return [(w.word, offset + w.start, offset + w.end) for s in segs for w in (s.words or [])]


def _to_words(toks, lang):
    toks = [t for t in toks if t[0].strip()]
    if lang != "th":
        return [{"w": t.strip(), "s": round(s, 3), "e": round(e, 3)} for t, s, e in toks]
    from pythainlp.tokenize import word_tokenize
    chars, times = [], []
    for t, s, e in toks:
        t = t.replace(" ", "")
        n = max(1, len(t))
        for k, ch in enumerate(t):
            chars.append(ch)
            times.append((s + (e - s) * k / n, s + (e - s) * (k + 1) / n))
    text = "".join(chars)
    words, pos = [], 0
    for w in word_tokenize(text, engine="newmm", keep_whitespace=False):
        k = text.find(w, pos)
        if k < 0 or not w.strip():
            continue
        words.append({"w": w, "s": round(times[k][0], 3), "e": round(times[k + len(w) - 1][1], 3)})
        pos = k + len(w)
    return words


def _speech_spans(a):
    """Merged spans of 0.5 s windows with RMS > -35 dBFS."""
    frame = int(SR * GAP_WIN)
    db = _frame_db(a, frame)
    spans = [(i * GAP_WIN, (i + 1) * GAP_WIN) for i in range(len(db)) if db[i] > SPEECH_DB]
    return _merge(spans)


def _overlap(w, x):
    return max(0.0, min(w["e"], x["e"]) - max(w["s"], x["s"]))


def _uncovered(words, speech, min_len=GAP_MIN):
    """Sub-spans of `speech` (>= min_len long) with no word overlapping."""
    out = []
    for a, b in speech:
        cur = a
        for w in sorted((w for w in words if w["e"] > a and w["s"] < b), key=lambda w: w["s"]):
            if w["s"] - cur >= min_len:
                out.append([cur, w["s"]])
            cur = max(cur, w["e"])
        if b - cur >= min_len:
            out.append([cur, b])
    return [[round(a, 3), round(b, 3)] for a, b in out]


def _segments(words, lang):
    segs, i0 = [], 0
    join = "" if lang == "th" else " "
    for i, w in enumerate(words):
        last = i == len(words) - 1
        brk = last
        if not last:
            brk = words[i + 1]["s"] - w["e"] > PAUSE_SPLIT
        if not brk:
            t = w["w"]
            brk = t.endswith((".", "!", "?")) or (lang == "th" and t in THAI_FINAL)
        if brk:
            seg = words[i0:i + 1]
            segs.append({"text": join.join(x["w"] for x in seg), "s": seg[0]["s"], "e": seg[-1]["e"], "i0": i0, "i1": i})
            i0 = i + 1
    return segs


# ------------------------------------------------------------------ main
def transcribe(audio16k, lang="th"):
    a = np.asarray(audio16k, dtype=np.float32)
    words = []
    for cs, ce in _chunks(a):
        chunk = a[int(cs * SR):int(ce * SR)]
        if len(chunk) < SR * 0.3:
            continue
        words += _to_words(_tokens(chunk, lang, cs), lang)
    words.sort(key=lambda w: w["s"])

    speech = _speech_spans(a)
    dur = len(a) / SR
    rerun = _uncovered(words, speech)
    for ra, rb in rerun:
        pa, pb = max(0.0, ra - 0.3), min(dur, rb + 0.3)
        new = _to_words(_tokens(a[int(pa * SR):int(pb * SR)], lang, pa, vad=False), lang)
        for nw in new:
            dl = max(1e-3, nw["e"] - nw["s"])
            if any(_overlap(nw, w) / dl > 0.5 for w in words):
                continue
            words.append(nw)
        words.sort(key=lambda w: w["s"])
    uncovered = _uncovered(words, speech)

    return {
        "words": words,
        "segments": _segments(words, lang) if words else [],
        "coverage": {
            "speech_spans": speech,
            "transcribed_spans": _merge([(w["s"], w["e"]) for w in words], tol=0.6),
            "rerun_spans": rerun,
            "uncovered_spans": uncovered,
        },
    }
