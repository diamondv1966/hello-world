# Module contracts (Tier 0) — each module has ONE owner agent; edit only your own files

Coordinates: **source px** = original clip pixels; **output px** = final 1080x1920. Times: **source s** vs **output s** (after cuts).
Shared data lives in `projects/<name>/pipeline_manifest.json` (schema: `docs/schemas/pipeline_manifest.schema.json`).
All modules: pure functions, no network, CPU only, Python 3.13, import from `tools/vt/`. Assets via `vt_lib.A` (assets dir).

## tools/vt/asr.py — owner 03-asr-thai-transcriber
```python
transcribe(audio16k: np.ndarray, lang: str = "th") -> dict
# returns {"words":[{w,s,e}], "segments":[{text,s,e,i0,i1}], "coverage":{speech_spans,transcribed_spans,rerun_spans,uncovered_spans}}
```
- split audio at silences into chunks of 20–30 s (keep `chunk_offset`), faster-whisper per chunk:
  `word_timestamps=True, condition_on_previous_text=False, vad_filter=True, vad_parameters={"min_silence_duration_ms":400,"speech_pad_ms":250}`
- Thai words: token chars → per-char times → pythainlp `newmm` words (see current `vt_lib.transcribe_words`)
- gap check: windows where RMS > -35 dBFS for ≥ 2 s but no word → re-transcribe that span alone (pad 0.3 s); report leftovers in `uncovered_spans`
- segments: split at pauses > 0.45 s or sentence-final particles (ค่ะ คะ ครับ นะคะ) / . ! ? (not numeric tokens like "7."); **i1 is exclusive** → words[i0:i1]
- model: `vt_lib._model()` (Whisper small in assets — never download at runtime)

## tools/vt/dedup.py — owner 04-thai-dedup-cutter
```python
find_retakes(segments: list, words: list, lang="th", window=15.0, min_sim=0.72, prefix_n=3) -> list[dict]
# -> [{"a":src_s,"b":src_s,"kind":"retake","reason":str,"similarity":float}]  (spans to REMOVE = the bad/earlier take)
plan_cuts(duration, silences, retakes, skips, max_gap, pad, end_pad) -> (cuts: list[dict], keeps: list[[a,b]])
```
- compare each segment with following segments starting ≤ `window` s later: `difflib.SequenceMatcher` on pythainlp word lists (≥ min_sim) OR first `prefix_n` words equal (false start) → remove the earlier one (from its start to the later one's start), keep the last complete take
- silences come from `vt_lib.silences()`; cut kinds: head/tail/silence/retake/skip

## tools/vt/face.py — owner 05-cv-face-tracker
```python
track(path: str, step=0.25) -> list[{"t":src_s, "box":[x,y,w,h] | None}]      # source px, padded +35%, smoothed + hold ≤1.0 s
window_for(face_box, src_w, src_h, zoom: float, face_y=0.40, out_w=1080, out_h=1920) -> [x0,y0,w,h]  # visible source window (9:16) centred on face
to_output(box_src, window) -> [x,y,w,h]                                     # map a source-px box into output px for that window
segment_face_out(track, a, b, win0, win1) -> [x,y,w,h] | None                # union of output-px face boxes over [a,b] (start & end windows)
```
- OpenCV 4 Haar (`haarcascade_frontalface_default`) + optional profile cascade; padding 35 % (more on top for hair); EMA smoothing; hold last box ≤ 1 s when detection drops
- window: width = src_h*9/16/zoom (clamped to src), height = src_h/zoom; place so face centre sits at `face_y` of the window height; clamp inside the frame

## tools/vt/layout.py — owner 06-graphics-broll-compositor
```python
text_bbox(text, font_path, size, anchor_x=540, baseline_y=..., align="bottom") -> [x,y,w,h]   # real PIL getbbox incl. Thai upper/lower marks
thai_font_size_for_height(px_height, font_path, probe="ผู้ใหญ่หาผ้าใหม่ ให้สะใภ้ใช้คล้องคอ") -> int
place_card(t0, t1, card_wh, faces_out: list[bbox], captions: list[{t0,t1,bbox}], safe=dict) -> {"bbox":[x,y,w,h], "mode": "card"|"card_small"|"broll_full", "scale":float}
resolve_captions(captions, cards, faces_out, margin=24, safe=dict) -> captions (bbox/y adjusted)
count_collisions(manifest) -> {"collision_count":n, "face_card_overlaps":n1, "sub_card_overlaps":n2, "details":[...]}
```
- priority: face (after zoom) > subtitle > card; cards try: default zone (lower) → opposite zone (upper) → smaller (×0.75) → broll_full (cut-away)
- captions must clear cards by ≥ 24 px; everything inside safe zone (top ≥130, bottom ≤1440, right ≤930 for UI-heavy elements)

## tools/vt/qa_visual.py — owner 07-ffmpeg-render-engineer
```python
audio_diagnostics(project_dir, out_png)   # waveform + dBFS curve + ASR coverage bands + cut lines + uncovered spans in red
contact_sheet(project_dir, out_png)       # frames at strongest zooms / card starts / caption mids; draw face=red, card=blue, caption=green boxes
```
- reads `pipeline_manifest.json` + `src.mp4` + `FINAL.mp4`; writes PNGs to `projects/<name>/artifacts/qa/` and copies to `video-toolkit/artifacts/qa/`
- also writes `qa` block (collision_count etc.) back into the manifest via `layout.count_collisions`

## tools/auto_edit.py (integration) — owner 07-ffmpeg-render-engineer
reads preset + `presets/user_settings.json` + project `config.json`; calls asr → dedup → face → layout → render → qa_visual; writes manifest at every stage.

## Manifest additions (v2)
- `overlays`: [{kind: hook|cta|cta_sub|disclaimer, t0, t1, bbox}] — counted in `qa.collision_count` (overlay∩caption gap<24 px; disclaimer 12 px; hook/cta∩face) and drawn yellow on the contact sheet
- `qa`: collision_count, collision_count_layout, collision_count_visual, overlay_collisions, caption_face_soft_overlaps, caption_y, asr_uncovered_s, lufs, peak, duration, render_s, images
- config `transcript_overrides`: [{s, e, text}] corrected Thai text per source span (applied after ASR, before dedup/captions)
- ASS rule: **Spacing=0 in every style, never `\fsp`** (Thai mark-to-mark positioning)
