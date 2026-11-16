import os, sys, json, statistics
HERE = os.path.dirname(os.path.abspath(__file__))
TK = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(TK, "tools"))
import cv2, numpy as np
from vt import face

P = os.path.join(TK, "projects", "thai9")
src = os.path.join(P, "src.mp4")
tr = face.track(src)
boxes = [p for p in tr if p["box"]]
rate = len(boxes) / len(tr)
W, H = 540, 960
med = [statistics.median(p["box"][i] for p in boxes) for i in range(4)]
print(f"samples={len(tr)} detection_rate={rate:.1%} median_box={[round(v,1) for v in med]}")
json.dump({"detection_rate": rate, "median_box": med, "track": tr}, open(os.path.join(P, "face_test.json"), "w"))
assert rate >= 0.80, rate
for p in boxes:
    x, y, w, h = p["box"]
    assert x >= 0 and y >= 0 and x + w <= W + 0.5 and y + h <= H + 0.5 and w > 0 and h > 0, p
worst = 0
for a, b in zip(tr, tr[1:]):
    if a["box"] and b["box"]:
        for i in (2, 3):
            worst = max(worst, abs(b["box"][i] - a["box"][i]) / a["box"][i])
print(f"max consecutive size change={worst:.1%}")
assert worst < 0.25, worst

# zoom math (median face placed mid-frame vertically so clamping does not hide the effect)
mface = [med[0], max(med[1], 0), med[2], med[3]]
sizes = []
for z in (1.0, 1.15, 1.3):
    win = face.window_for(mface, W, H, z)
    o = face.to_output(mface, win)
    cy = o[1] + o[3] / 2
    print(f"zoom {z}: win={[round(v,1) for v in win]} out_face={[round(v,1) for v in o]} cy={cy:.0f}")
    sizes.append(o[2])
    assert win[0] >= 0 and win[1] >= 0 and win[0] + win[2] <= W + 1e-6 and win[1] + win[3] <= H + 1e-6
    clamped = win[1] <= 1e-6 or win[1] + win[3] >= H - 1e-6
    if not clamped:
        assert abs(cy - 0.40 * 1920) <= 60, cy
for z, s in zip((1.0, 1.15, 1.3), sizes):
    assert abs(s / sizes[0] - z) <= 0.10 * z, (z, s / sizes[0])
# synthetic unclamped check on a landscape source
w2 = face.window_for([800, 400, 200, 250], 1920, 1080, 1.3)
o2 = face.to_output([800, 400, 200, 250], w2)
print("landscape win", [round(v, 1) for v in w2], "out", [round(v, 1) for v in o2])
assert abs(o2[1] + o2[3] / 2 - 768) <= 60
assert face.window_for(None, 1920, 1080, 1.0)[2] == 1080 * 9 / 16
assert face.segment_face_out([{"t": 0, "box": None}], 0, 1, w2, w2) is None
seg = face.segment_face_out(tr, 0, 5, face.window_for(mface, W, H, 1.0), face.window_for(mface, W, H, 1.3))
print("segment_face_out", seg)

# visual check
cap = cv2.VideoCapture(src)
tiles = []
for t in (3, 12, 22, 33, 45, 55):
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, fr = cap.read()
    p = min(tr, key=lambda q: abs(q["t"] - t))
    if p["box"]:
        x, y, w, h = map(int, p["box"]); cv2.rectangle(fr, (x, y), (x + w, y + h), (0, 0, 255), 3)
    cv2.putText(fr, f"t={t}", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
    tiles.append(cv2.resize(fr, (270, int(fr.shape[0] * 270 / fr.shape[1]))))
cv2.imwrite(os.path.join(P, "face_test.jpg"), np.hstack(tiles))
print("OK")
