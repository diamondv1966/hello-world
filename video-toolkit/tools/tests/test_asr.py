import os, sys, json, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
from vt import asr

PROJ = os.path.join(os.path.dirname(TOOLS), "projects", "thai9")
a = np.fromfile(os.path.join(PROJ, "audio16k.f32"), dtype=np.float32)
t0 = time.time()
r = asr.transcribe(a, "th")
print(f"runtime {time.time() - t0:.0f}s, audio {len(a) / 16000:.1f}s")
with open(os.path.join(PROJ, "asr_test.json"), "w", encoding="utf-8") as f:
    json.dump(r, f, ensure_ascii=False, indent=1)

W, S, C = r["words"], r["segments"], r["coverage"]
inwin = [w for w in W if w["e"] > 3 and w["s"] < 57]
pts = [3.0] + [x for w in inwin for x in (w["s"], w["e"])] + [57.0]
pts = sorted(min(max(p, 3.0), 57.0) for p in pts)
gaps = []
cur = 3.0
for w in sorted(inwin, key=lambda w: w["s"]):
    gaps.append(w["s"] - cur); cur = max(cur, w["e"])
gaps.append(57.0 - cur)
maxgap = max(gaps)
print("words", len(W), "first", W[0]["w"], W[0]["s"], "last", W[-1]["w"], W[-1]["e"])
print("max gap 3-57s", round(maxgap, 2))
print("rerun_spans", C["rerun_spans"], "uncovered", C["uncovered_spans"])
print("segments", len(S))
print("text", "".join(w["w"] for w in W)[:300])

assert maxgap <= 2.0, maxgap
assert C["uncovered_spans"] == [], C["uncovered_spans"]
assert len(W) >= 150, len(W)
assert S and all(S[i]["s"] <= S[i]["e"] and (i == 0 or S[i]["s"] >= S[i - 1]["s"]) for i in range(len(S)))
assert all(W[i]["s"] <= W[i + 1]["s"] for i in range(len(W) - 1))
print("OK")
