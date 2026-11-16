"""layout.py - Thai text metrics, card placement, caption/card collision handling.

All boxes are [x, y, w, h] in OUTPUT pixels (frame 1080x1920).
Priority: face > subtitle > card.
"""
from PIL import ImageFont

SAFE = {"top": 130, "bottom": 1440, "right": 930, "left": 60, "w": 1080, "h": 1920}
MARGIN = 24
PROBE = "ผู้ใหญ่หาผ้าใหม่ ให้สะใภ้ใช้คล้องคอ"
_FONTS = {}


def _safe(safe):
    s = dict(SAFE)
    if safe:
        s.update(safe)
    return s


def _font(path, size):
    k = (path, int(size))
    if k not in _FONTS:
        _FONTS[k] = ImageFont.truetype(path, int(size), layout_engine=ImageFont.Layout.RAQM)
    return _FONTS[k]


def _ink(text, font_path, size):
    """(left, top, right, bottom) real ink bbox relative to origin."""
    return _font(font_path, size).getbbox(text)


def text_bbox(text, font_path, size, anchor_x=540, bottom_y=1250, outline=8):
    """Ink bbox centred on anchor_x; the bottom edge of the returned box (ink grown by
    `outline` px each side) sits at bottom_y (libass \\an2 = bottom-centre)."""
    l, t, r, b = _ink(text, font_path, size)
    w = (r - l) + 2 * outline
    h = (b - t) + 2 * outline
    x = int(round(anchor_x - w / 2.0))
    y = int(round(bottom_y - h))
    return [x, y, int(w), int(h)]


def thai_font_size_for_height(px_height, font_path, probe=PROBE):
    """Font size whose full ink height of `probe` is closest to px_height (search 10..300)."""
    def h(s):
        l, t, r, b = _ink(probe, font_path, s)
        return b - t
    lo, hi = 10, 300
    while lo < hi:
        mid = (lo + hi) // 2
        if h(mid) < px_height:
            lo = mid + 1
        else:
            hi = mid
    # lo = first size with h >= target; pick closest of lo-1, lo
    if lo > 10 and abs(h(lo - 1) - px_height) < abs(h(lo) - px_height):
        return lo - 1
    return lo


# ---------- geometry ----------
def _inter(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def _grow(b, m):
    return [b[0] - m, b[1] - m, b[2] + 2 * m, b[3] + 2 * m]


def _tov(a0, a1, b0, b1):
    return a0 < b1 and b0 < a1


def _inside_safe(b, s):
    return b[1] >= s["top"] and b[1] + b[3] <= s["bottom"] and b[0] >= s["left"] and b[0] + b[2] <= s["right"]


def place_card(t0, t1, card_wh, faces_out, captions, safe=None, margin=MARGIN):
    s = _safe(safe)
    faces = [f["bbox"] for f in faces_out if f.get("bbox") and _tov(t0, t1, f["t0"], f["t1"])]
    caps = [c["bbox"] for c in captions if c.get("bbox") and _tov(t0, t1, c["t0"], c["t1"])]

    def valid(b):
        if not _inside_safe(b, s):
            return False
        if any(_inter(b, f) for f in faces):
            return False
        if any(_inter(_grow(c, margin), b) for c in caps):
            return False
        return True

    # horizontal side preference from face centre
    xs_extra = []
    if faces:
        fx0 = min(f[0] for f in faces)
        fx1 = max(f[0] + f[2] for f in faces)
        fc = (fx0 + fx1) / 2.0
        if fc < 540 - 40:
            xs_extra = ["right"]
        elif fc > 540 + 40:
            xs_extra = ["left"]

    for mode, scale in (("card", 1.0), ("card_small", 0.75)):
        w = int(round(card_wh[0] * scale))
        h = int(round(card_wh[1] * scale))
        xc = int(round(540 - w / 2.0))
        xr = int(s["right"] - w)
        xl = int(s["left"])
        ylow = 1420 - h
        yup = 140
        cands = [(xc, ylow), (xc, yup)]
        for side in xs_extra:
            x = xr if side == "right" else xl
            cands += [(x, ylow), (x, yup)]
        for side in ("right", "left"):
            if side not in xs_extra:
                x = xr if side == "right" else xl
                cands += [(x, ylow), (x, yup)]
        for x, y in cands:
            b = [x, y, w, h]
            if valid(b):
                return {"bbox": b, "mode": mode, "scale": scale}
    return {"bbox": [0, 0, int(s["w"]), int(s["h"])], "mode": "broll_full", "scale": 1.0}


def resolve_captions(captions, cards, faces_out, margin=MARGIN, safe=None):
    s = _safe(safe)
    real = [c for c in cards if c.get("mode") != "broll_full" and c.get("bbox")]
    out = []
    for cap in captions:
        cap = dict(cap)
        bb = list(cap["bbox"])
        cs = [c for c in real if _tov(cap["t0"], cap["t1"], c["t0"], c["t1"])]
        fs = [f["bbox"] for f in faces_out if f.get("bbox") and _tov(cap["t0"], cap["t1"], f["t0"], f["t1"])]
        hit = [c for c in cs if _inter(_grow(bb, margin), c["bbox"])]
        if hit:
            top = min(c["bbox"][1] for c in hit)
            bot = max(c["bbox"][1] + c["bbox"][3] for c in hit)

            def ok(b):
                return (b[1] >= s["top"] and b[1] + b[3] <= s["bottom"]
                        and not any(_inter(b, f) for f in fs)
                        and not any(_inter(_grow(b, margin), c["bbox"]) for c in cs))
            above = [bb[0], top - margin - bb[3], bb[2], bb[3]]
            below = [bb[0], bot + margin, bb[2], bb[3]]
            for cand in (above, below):
                if ok(cand):
                    bb = cand
                    break
            cap["bbox"] = bb
            cap["y"] = bb[1] + bb[3]
        out.append(cap)
    return out


def count_collisions(manifest):
    cards = [c for c in manifest.get("cards", []) if c.get("mode") != "broll_full" and c.get("bbox")]
    segs = manifest.get("segments", [])
    caps = manifest.get("captions", [])
    details = []
    fc = sc = 0
    for ci, c in enumerate(cards):
        for si, sg in enumerate(segs):
            fb = sg.get("face_out")
            if not fb or not _tov(c["t0"], c["t1"], sg["oa"], sg["ob"]):
                continue
            if _inter(fb, c["bbox"]):
                fc += 1
                details.append({"type": "face_card", "card": ci, "segment": si,
                                "t0": max(c["t0"], sg["oa"]), "t1": min(c["t1"], sg["ob"])})
        for ki, cap in enumerate(caps):
            if not cap.get("bbox") or not _tov(c["t0"], c["t1"], cap["t0"], cap["t1"]):
                continue
            if _inter(_grow(cap["bbox"], MARGIN), c["bbox"]):
                sc += 1
                details.append({"type": "sub_card", "card": ci, "caption": ki,
                                "t0": max(c["t0"], cap["t0"]), "t1": min(c["t1"], cap["t1"])})
    return {"collision_count": fc + sc, "face_card_overlaps": fc, "sub_card_overlaps": sc, "details": details}
