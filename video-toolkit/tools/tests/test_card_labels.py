import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
TK = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(TK, "tools"))
from vt import captions as C
from PIL import ImageFont

XB = os.path.join(TK, "assets/fonts/KanitXB.ttf")
fnt = lambda sz: ImageFont.truetype(XB, sz, layout_engine=ImageFont.Layout.RAQM)
cards = json.load(open(os.path.join(TK, "projects/thai9/config.json")))["cards"]
assert len(cards) == 6
NAVY = (18, 42, 107)
seen = set()
for c in cards:
    items = c["items"]; sz = 30 if len(items) <= 4 else 26
    rows = [C.label_line(fnt(sz), it[1], NAVY) for it in items]
    hs = {im.height for im, _ in rows}; bl = {b for _, b in rows}
    assert len(hs) == 1 and len(bl) == 1, (c["title"], hs, bl)
    assert hs == {C.line_box_h(fnt(sz))}
    for (im, b), it in zip(rows, items):
        ink = im.getchannel("A").getbbox(); seen.add(it[1])
        assert ink and ink[1] >= 1 and ink[3] <= im.height - 1, (it[1], ink, im.height)  # tall marks / descenders not clipped
        assert ink[0] >= 1 and ink[2] <= im.width - 1
    # title + note use fixed line boxes of their own font size too
    t, tb = C.label_line(fnt(44), c["title"], NAVY); assert t.height == C.line_box_h(fnt(44))
    if c.get("note"): n, _ = C.label_line(fnt(28), c["note"], NAVY); assert n.height == C.line_box_h(fnt(28))
    # same baseline relative to the box: render ink of a flat-base consonant in each label's first-letter position
    print(c["title"], "box_h", hs.pop(), "baseline", bl.pop(), [it[1] for it in items])
for need in ("น้ำเปล่า", "ไข่แดง", "ลุกเดิน", "ควรตรวจ", "แตงกวา"): assert need in seen, need
# same text in different cards -> pixel-identical row heights; baseline independent of glyph set
a, ba = C.label_line(fnt(30), "ก", NAVY); b, bb = C.label_line(fnt(30), "น้ำ ลุกเดิน ไข่", NAVY)
assert a.height == b.height and ba == bb
# emoji boxes: fixed square for every emoji
from PIL import ImageFont as IF
E = IF.truetype("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", 109)
sizes = {C.emoji_box(E, it[0], 112).size for c in cards for it in c["items"]}
assert sizes == {(112, 112)}, sizes
print("test_card_labels ok")
