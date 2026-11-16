import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
TK = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(TK, "tools"))
from vt import layout as L
from PIL import Image, ImageDraw, ImageFont

XB = os.path.join(TK, "assets/fonts/KanitXB.ttf")
inter = L._inter

# 1 metrics
f = ImageFont.truetype(XB, 80, layout_engine=ImageFont.Layout.RAQM)
bp = f.getbbox(L.PROBE); bk = f.getbbox("กา")
hp, hk = bp[3] - bp[1], bk[3] - bk[1]
assert hp > 1.3 * hk, (hp, hk)
for size in (30, 56, 80, 120):
    l, t, r, b = L._ink(L.PROBE, XB, size)
    assert abs(L.thai_font_size_for_height(b - t, XB) - size) <= 1, size
bb = L.text_bbox("สวัสดีครับ", XB, 70, 540, 1250, 8)
assert bb[1] + bb[3] == 1250 and abs(bb[0] + bb[2] / 2 - 540) <= 1
print("1 ok", hp, hk, bb)

def check(card, face, cap, t=(0, 2)):
    b = card["bbox"]
    if card["mode"] == "broll_full":
        return
    assert not inter(b, face)
    assert not inter(L._grow(cap, 24), b), (b, cap)
    assert b[1] >= 130 and b[1] + b[3] <= 1440

# 2
face = [330, 700, 420, 520]
cap = L.text_bbox("ทดสอบคำบรรยายยาว", XB, 70, 540, 1250, 8)
fo = [{"t0": 0, "t1": 2, "bbox": face}]
co = [{"t0": 0, "t1": 2, "text": "x", "bbox": cap, "y": 1250}]
c2 = L.place_card(0, 2, (760, 400), fo, co)
check(c2, face, cap); print("2", c2)

# 3
face3 = [250, 600, 580, 800]
c3 = L.place_card(0, 2, (760, 400), [{"t0": 0, "t1": 2, "bbox": face3}], co)
check(c3, face3, cap); print("3", c3)

# 4
card = {"t0": 0, "t1": 2, "bbox": [160, 1000, 760, 400], "mode": "card"}
cap4 = {"t0": 0, "t1": 2, "text": "x", "bbox": cap, "y": 1250}
fa = [{"t0": 0, "t1": 2, "bbox": [330, 300, 420, 400]}]
r = L.resolve_captions([cap4], [card], fa)[0]
nb = r["bbox"]
assert not inter(L._grow(nb, 24), card["bbox"]) and r["y"] == nb[1] + nb[3] and nb != cap
assert nb[1] >= 130 and nb[1] + nb[3] <= 1440
print("4", nb)

# 5
man = {"segments": [{"oa": 0, "ob": 5, "face_out": [330, 700, 420, 520]}],
       "cards": [{"t0": 1, "t1": 3, "bbox": [160, 900, 760, 400], "mode": "card"}],
       "captions": [{"t0": 1, "t1": 3, "bbox": [200, 1310, 680, 100]}]}
cc = L.count_collisions(man)
assert cc["face_card_overlaps"] == 1 and cc["sub_card_overlaps"] == 1 and cc["collision_count"] == 2, cc
man["cards"][0]["bbox"] = [160, 1000, 760, 150]
man["segments"][0]["face_out"] = [330, 300, 420, 520]
man["captions"][0]["bbox"] = [200, 1190, 680, 100]
assert L.count_collisions(man)["collision_count"] == 0
man["cards"][0]["mode"] = "broll_full"; man["cards"][0]["bbox"] = [0, 0, 1080, 1920]
assert L.count_collisions(man)["collision_count"] == 0
print("5 ok")

# 6 render
out = os.path.join(TK, "projects/thai9/layout_test.png")
sc = 360 / 1080
scen = [("zoom1.3", face, cap), ("heavy zoom", face3, cap),
        ("off-centre", [100, 500, 380, 500], cap), ("caption fix", [330, 300, 420, 400], cap)]
W = 360 * len(scen)
im = Image.new("RGB", (W, 640), (30, 30, 30)); d = ImageDraw.Draw(im)
def rect(ox, b, col, wd=2):
    d.rectangle([ox + b[0]*sc, b[1]*sc, (ox + (b[0]+b[2])*sc), (b[1]+b[3])*sc], outline=col, width=wd)
for i, (nm, fb, cb) in enumerate(scen):
    ox = i * 360
    d.rectangle([ox, 0, ox + 359, 639], outline=(90, 90, 90))
    d.rectangle([ox + 60*sc, 130*sc, ox + 930*sc, 1440*sc], outline=(70, 70, 70))
    fo_ = [{"t0": 0, "t1": 2, "bbox": fb}]
    cap_ = {"t0": 0, "t1": 2, "text": "x", "bbox": cb, "y": 1250}
    if nm == "caption fix":
        card_ = {"t0": 0, "t1": 2, "bbox": [160, 1000, 760, 400], "mode": "card"}
        cap_ = L.resolve_captions([cap_], [card_], fo_)[0]
    else:
        card_ = L.place_card(0, 2, (760, 400), fo_, [cap_])
    rect(ox, fb, (255, 60, 60), 2); rect(ox, cap_["bbox"], (60, 220, 60), 2)
    rect(ox, card_["bbox"], (70, 130, 255), 3)
    d.text((ox + 6, 6), f"{nm}: {card_['mode']}", fill=(255, 255, 255))
    print("6", nm, card_["mode"], card_["bbox"], cap_["bbox"])
im.save(out); print("saved", out)
print("ALL OK")
