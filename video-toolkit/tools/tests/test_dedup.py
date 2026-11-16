import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from vt.dedup import find_retakes, plan_cuts


def build(items):
    """items: [(text_tokens_list, start, dur)] -> segments, words"""
    words, segs = [], []
    for toks, s, d in items:
        i0 = len(words); step = d / len(toks)
        for k, t in enumerate(toks):
            words.append({"w": t, "s": s + k * step, "e": s + (k + 1) * step})
        segs.append({"text": "".join(toks), "s": s, "e": s + d, "i0": i0, "i1": len(words)})
    return segs, words

rows = []
# 1 retake
segs, words = build([(["ข้อ", "สอง", "กิน", "ผัก", "ใบ", "เขียว"], 0.0, 2.0),
                     (["ข้อ", "สอง", "กิน", "ผัก", "ใบ", "เขียว", "เพราะ", "มี", "แมกนีเซียม", "สูง"], 4.0, 4.0)])
r = find_retakes(segs, words)
assert len(r) == 1 and r[0]["a"] == 0.0 and r[0]["b"] == 4.0, r
rows.append(("retake", r[0]["a"], r[0]["b"], r[0]["similarity"], r[0]["reason"]))
# 2 false start
segs, words = build([(["วันนี้", "เรา", "จะ", "มา"], 0.0, 1.5),
                     (["วันนี้", "เรา", "จะ", "มา", "พูดถึง", "สัญญาณ", "เตือน", "ของ", "ร่างกาย"], 2.5, 4.0)])
r = find_retakes(segs, words)
assert len(r) == 1 and r[0]["b"] == 2.5, r
rows.append(("false start", r[0]["a"], r[0]["b"], r[0]["similarity"], r[0]["reason"]))
# 3a list items
segs, words = build([(["1", "ค่ะ", "ปวด", "หัว", "ขาด", "น้ำ", "ค่ะ"], 0.0, 3.0),
                     (["2", "ค่ะ", "เป็น", "ตะคริว", "ขาด", "แมกนีเซียม", "ค่ะ"], 3.5, 3.0)])
assert find_retakes(segs, words) == []
segs, words = build([(["ข้อ", "2", "ค่ะ", "ปวด", "หัว"], 0.0, 2.0),
                     (["ข้อ", "2", "ค่ะ", "เป็น", "ตะคริว", "ที่", "น่อง"], 2.5, 3.0)])
assert find_retakes(segs, words) == []
# 3b far apart
segs, words = build([(["วันนี้", "เรา", "จะ", "มา"], 0.0, 1.5),
                     (["วันนี้", "เรา", "จะ", "มา", "พูดถึง", "ผัก"], 30.0, 3.0)])
assert find_retakes(segs, words) == []
rows.append(("no false positive", 0, 0, 0.0, "list items + >15s apart: none"))
# chain: keep last take
segs, words = build([(["ข้อ", "สอง", "กิน", "ผัก"], 0.0, 1.0),
                     (["ข้อ", "สอง", "กิน", "ผัก", "ใบ"], 2.0, 1.5),
                     (["ข้อ", "สอง", "กิน", "ผัก", "ใบ", "เขียว", "ดี"], 4.0, 2.0)])
r = find_retakes(segs, words)
assert len(r) == 1 and r[0]["a"] == 0.0 and r[0]["b"] == 4.0, r
rows.append(("chain merged", r[0]["a"], r[0]["b"], r[0]["similarity"], "keep last"))

# 4 plan_cuts
D = 30.0
cuts, keeps = plan_cuts(D, [(0.0, 0.8), (10.0, 10.6), (10.7, 11.0), (29.2, 30.0)],
                        [{"a": 10.5, "b": 14.0, "kind": "retake", "reason": "x", "similarity": .9}],
                        [(20.0, 21.0)], max_gap=0.3, pad=0.1, end_pad=0.2)
kinds = [c["kind"] for c in cuts]
assert kinds == ["head", "retake", "skip", "tail"], cuts
assert abs(cuts[0]["b"] - 0.7) < 1e-9 and abs(cuts[3]["a"] - 29.4) < 1e-9
assert cuts[1]["a"] == 10.1 + 0.0 or abs(cuts[1]["a"] - 10.1) < 1e-9
total_cut = sum(c["b"] - c["a"] for c in cuts)
total_keep = sum(b - a for a, b in keeps)
assert abs(total_cut + total_keep - D) < 1e-6, (total_cut, total_keep)
assert all(b - a > 0.08 for a, b in keeps)
for k in keeps:
    for c in cuts:
        assert k[1] <= c["a"] + 1e-9 or k[0] >= c["b"] - 1e-9
rows.append(("plan_cuts", len(cuts), len(keeps), round(total_keep, 2), ",".join(kinds)))

print(f"{'case':<20}{'a':>7}{'b':>7}{'sim':>8}  note")
for n, a, b, s, note in rows:
    print(f"{n:<20}{a:>7}{b:>7}{s:>8}  {note}")
print("ALL PASS")
