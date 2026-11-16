import json, os, subprocess, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from vt import qa_visual

P = "/tmp/claude-0/-home-user-hello-world/a93d516e-1313-53e9-bd9e-ff3626c10438/scratchpad/qa_test"
os.makedirs(P, exist_ok=True)
SR = 16000

# 15 s source audio: speech-like bursts (tone w/ AM), a loud gap region 9-12 s left uncovered
t = np.arange(15 * SR) / SR
y = np.zeros_like(t)
for a, b, amp in [(0.5, 4.5, .5), (5.5, 8.5, .4), (9.0, 12.0, .45), (13, 14.5, .3)]:
    m = (t >= a) & (t < b)
    y[m] = amp * np.sin(2 * np.pi * 180 * t[m]) * (0.6 + 0.4 * np.sin(2 * np.pi * 4 * t[m]))
y.astype("<f4").tofile(os.path.join(P, "audio16k.f32"))

subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=25:d=12",
                "-f", "lavfi", "-i", "sine=f=440:d=12", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-shortest", os.path.join(P, "FINAL.mp4")], check=True)

words = [{"w": f"คำ{i}", "s": 0.6 + i * 0.5, "e": 1.0 + i * 0.5} for i in range(8)] + \
        [{"w": f"ไทย{i}", "s": 5.6 + i * 0.5, "e": 6.0 + i * 0.5} for i in range(5)]
man = {
    "version": 1, "project": "qa_test",
    "src": {"path": "src.mp4", "sha256": "x", "duration": 15.0, "w": 1920, "h": 1080},
    "settings": {}, "asr": {"words": words, "segments": [], "coverage": {
        "speech_spans": [[0.5, 4.5], [5.5, 8.5], [9.0, 12.0], [13, 14.5]],
        "transcribed_spans": [[0.6, 4.5], [5.6, 8.5], [13, 14.5]],
        "rerun_spans": [[13, 14.5]],
        "uncovered_spans": [[9.0, 12.0]]}},
    "cuts": [{"a": 0, "b": 0.5, "kind": "head"}, {"a": 4.5, "b": 5.5, "kind": "silence"},
             {"a": 8.5, "b": 9.0, "kind": "retake"}, {"a": 12.0, "b": 13.0, "kind": "skip"},
             {"a": 14.5, "b": 15.0, "kind": "tail"}],
    "keeps": [[0.5, 4.5], [5.5, 8.5], [9.0, 12.0], [13.0, 14.5]],
    "segments": [
        {"a": 0.5, "b": 4.5, "oa": 0, "ob": 4, "z0": 1.0, "z1": 1.1, "face_out": [300, 500, 480, 560]},
        {"a": 5.5, "b": 8.5, "oa": 4, "ob": 8, "z0": 1.2, "z1": 1.5, "face_out": [280, 450, 520, 600]},
        {"a": 9.0, "b": 14.5, "oa": 8, "ob": 12, "z0": 1.0, "z1": 1.0, "face_out": [320, 520, 440, 520]}],
    "captions": [{"t0": 0.2, "t1": 3.0, "text": "สวัสดีค่ะ", "bbox": [200, 1250, 680, 120]},
                 {"t0": 4.2, "t1": 7.5, "text": "ผู้ใหญ่หาผ้าใหม่", "bbox": [150, 1200, 780, 130]},
                 {"t0": 9.0, "t1": 11.5, "text": "จบแล้ว", "bbox": [250, 1250, 580, 120]}],
    "cards": [{"t0": 6.5, "t1": 7.6, "bbox": [200, 700, 650, 520], "mode": "card"}],
    "qa": {"lufs": -14.1, "peak": -1.8, "duration": 12.0, "asr_uncovered_s": 3.0},
}
json.dump(man, open(os.path.join(P, "pipeline_manifest.json"), "w"), ensure_ascii=False)

a = qa_visual.audio_diagnostics(P, os.path.join(P, "audio_diagnostics.png"))
r = qa_visual.contact_sheet(P, os.path.join(P, "contact_sheet.png"))
for f in ("audio_diagnostics.png", "contact_sheet.png"):
    assert os.path.getsize(os.path.join(P, f)) > 10000, f
    assert os.path.exists(os.path.join(qa_visual.QA_COPY_DIR, f)), f
assert r["collision_count"] == 2, r
m = json.load(open(os.path.join(P, "pipeline_manifest.json")))
assert m["qa"]["collision_count"] == 2 and m["qa"]["images"], m["qa"]
print("tiles:", [(x["t"], x["status"]) for x in r["tiles"]])
print("OK")
