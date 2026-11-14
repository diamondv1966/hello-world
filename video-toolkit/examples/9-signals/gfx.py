# Motion-graphics layer: renders RGBA frames (1080x1920 @30fps) to stdout.
import sys, math, functools
from PIL import Image, ImageDraw, ImageFont, ImageFilter
D = sys.argv[1]; V = sys.argv[2]; sys.path.insert(0, V)
from timeline import GT, TOTAL, CARDS
W, H, FPS = 1080, 1920, 30
PREVIEW = len(sys.argv) > 3  # preview mode: save PNGs at given times
EMO = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", 109)
FONT = f"{D}/assets/fonts/KanitXB.ttf"
NAVY = (18, 42, 107); BLUE = (30, 70, 184); SKY = (125, 211, 252); PINK = (249, 168, 212); PINK2 = (251, 207, 232); WHITE = (255, 255, 255)

def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease_out(p): p = clamp(p); return 1 - (1 - p) ** 3
def ease_back(p):
    p = clamp(p); c1 = 1.70158; c3 = c1 + 1; return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2
@functools.lru_cache(None)
def font(sz): return ImageFont.truetype(FONT, sz, layout_engine=ImageFont.Layout.RAQM)
@functools.lru_cache(None)
def emoji(e, sz):
    g = Image.new("RGBA", (160, 140), (0, 0, 0, 0)); ImageDraw.Draw(g).text((0, 0), e, font=EMO, embedded_color=True)
    g = g.crop(g.getbbox()); s = sz / max(g.size)
    return g.resize((max(1, int(g.width * s)), max(1, int(g.height * s))), Image.LANCZOS)
@functools.lru_cache(None)
def text(s, sz, col=NAVY, stroke=0, scol=WHITE):
    f = font(sz); bb = f.getbbox(s, stroke_width=stroke)
    im = Image.new("RGBA", (bb[2] - bb[0] + 4, bb[3] - bb[1] + 4), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((2 - bb[0], 2 - bb[1]), s, font=f, fill=col, stroke_width=stroke, stroke_fill=scol)
    return im
def paste_c(dst, im, cx, cy, scale=1.0, alpha=1.0, rot=0.0):
    if scale <= 0.01 or alpha <= 0.01: return
    if scale != 1.0: im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    if rot: im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
    if alpha < 1.0:
        a = im.getchannel("A").point(lambda v: int(v * alpha)); im = im.copy(); im.putalpha(a)
    dst.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))

# ---------- badge icons ----------
@functools.lru_cache(None)
def badge(e, S=220):
    R = int(S * 0.39); im = Image.new("RGBA", (S, S), (0, 0, 0, 0)); c = S // 2
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0)); ImageDraw.Draw(sh).ellipse((c - R, c - R + 8, c + R, c + R + 8), fill=NAVY + (110,))
    im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(S / 24))); d = ImageDraw.Draw(im)
    d.ellipse((c - R, c - R, c + R, c + R), fill=PINK + (255,)); b = max(4, S // 31)
    d.ellipse((c - R + b, c - R + b, c + R - b, c + R - b), fill=WHITE + (255,))
    g = emoji(e, int(S * 0.51)); im.alpha_composite(g, (c - g.width // 2, c - g.height // 2)); return im

# ---------- card frame ----------
CW, CH = 760, 430; CX, CY = 540, 1385  # card centre (lower half, clear of face & TikTok UI)
@functools.lru_cache(None)
def card_base(title):
    pad = 30; im = Image.new("RGBA", (CW + 2 * pad, CH + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 14, pad + CW, pad + CH + 14), 40, fill=NAVY + (80,))
    im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(14))); d = ImageDraw.Draw(im)
    d.rounded_rectangle((pad, pad, pad + CW, pad + CH), 40, fill=PINK + (255,))
    d.rounded_rectangle((pad + 6, pad + 6, pad + CW - 6, pad + CH - 6), 35, fill=WHITE + (255,))
    hdr = Image.new("RGBA", (CW - 12, 88), (0, 0, 0, 0)); hd = ImageDraw.Draw(hdr)
    for x in range(hdr.width):  # sky -> pink gradient
        u = x / hdr.width; col = tuple(int(SKY[i] * (1 - u) + PINK[i] * u) for i in range(3))
        hd.line([(x, 0), (x, 88)], fill=col + (255,))
    m = Image.new("L", hdr.size, 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, hdr.width - 1, 120), 35, fill=255)
    hdr.putalpha(m); im.alpha_composite(hdr, (pad + 6, pad + 6))
    t = text(title, 46, NAVY); im.alpha_composite(t, (pad + CW // 2 - t.width // 2, pad + 6 + 44 - t.height // 2))
    return im, pad

def food_body(c, lt, items):  # 4 foods pop in with stagger
    for i, (e, lab) in enumerate(items):
        p = (lt - 0.18 - i * 0.09) / 0.32
        x = 115 + i * 177
        paste_c(c, emoji(e, 118), x, 205 - 10 * math.sin(lt * 3 + i), ease_back(p), clamp(p * 3))
        paste_c(c, text(lab, 32, NAVY), x, 318, 1.0, clamp((lt - 0.35 - i * 0.09) / 0.2))
    paste_c(c, text("กินให้หลากหลาย ครบ 5 หมู่", 28, BLUE), CW // 2, 382, 1.0, clamp((lt - 0.8) / 0.3))

def body1(c, lt):  # glass filling + 60%
    d = ImageDraw.Draw(c); gx, gy, gw, gh = 70, 120, 170, 270
    lvl = 0.15 + 0.7 * ease_out((lt - 0.1) / 0.8)
    top = gy + gh - int(gh * lvl)
    wave = [(gx + 8 + i, top + 6 * math.sin(i / 18 + lt * 8)) for i in range(0, gw - 15)]
    d.polygon(wave + [(gx + gw - 8, gy + gh - 8), (gx + 12, gy + gh - 8)], fill=SKY + (230,))
    d.line([(gx, gy), (gx + 14, gy + gh), (gx + gw - 14, gy + gh), (gx + gw, gy)], fill=NAVY + (255,), width=7, joint="curve")
    paste_c(c, emoji("💧", 70), gx + gw // 2, top - 40 - 10 * abs(math.sin(lt * 4)), 1.0, clamp(lt / 0.2))
    a = clamp((lt - 0.25) / 0.25)
    paste_c(c, text("ร่างกายเรามีน้ำ", 40, NAVY), 505, 175, 1.0, a)
    paste_c(c, text(f"~{int(60 * ease_out((lt - 0.25) / 0.6))}%", 110, BLUE, 6, WHITE), 505, 275, ease_back((lt - 0.25) / 0.35), a)
    paste_c(c, text("ขาดน้ำนิดเดียวก็ปวดหัวได้", 30, (190, 60, 130)), 505, 375, 1.0, clamp((lt - 0.5) / 0.25))

def arrow(c, x0, x1, y, p, col=PINK):
    d = ImageDraw.Draw(c); x = x0 + (x1 - x0) * ease_out(p)
    if p <= 0: return
    d.line([(x0, y), (x, y)], fill=col + (255,), width=12)
    if p > 0.6: d.polygon([(x + 22, y), (x - 8, y - 22), (x - 8, y + 22)], fill=col + (255,))

def body3(c, lt):
    paste_c(c, emoji("🦵", 130), 150, 220, ease_back((lt - 0.1) / 0.3))
    paste_c(c, text("ขาบวม", 34, NAVY), 150, 320, 1.0, clamp((lt - 0.2) / 0.2))
    arrow(c, 265, 470, 220, (lt - 0.35) / 0.35)
    beat = 1 + 0.08 * max(0, math.sin(lt * 2 * math.pi * 1.3)) ** 4
    paste_c(c, emoji("🫀", 130), 600, 220, ease_back((lt - 0.65) / 0.3) * beat)
    paste_c(c, text("หัวใจ", 34, NAVY), 600, 320, 1.0, clamp((lt - 0.75) / 0.2))
    paste_c(c, text("หัวใจสูบฉีดไม่ดี น้ำจึงคั่งที่ขา", 30, (190, 60, 130)), CW // 2, 385, 1.0, clamp((lt - 0.9) / 0.3))

def body6(c, lt):
    paste_c(c, emoji("🩸", 110), 105, 215, ease_back((lt - 0.05) / 0.3))
    d = ImageDraw.Draw(c); x0, y0, x1, y1 = 210, 120, 720, 320
    d.line([(x0, y0), (x0, y1), (x1, y1)], fill=(180, 190, 220, 255), width=5)
    d.line([(x0, y0 + 95), (x1, y0 + 95)], fill=PINK + (255,), width=3)
    paste_c(c, text("ระดับปกติ", 24, (200, 120, 160)), x0 + 70, y0 + 78, 1.0, 1.0)
    pts = [(x0 + 10 + i * 10, y0 + 40 + 150 * (1 / (1 + math.exp(-(i - 28) / 6))) + 6 * math.sin(i / 3)) for i in range(50)]
    n = int(len(pts) * ease_out((lt - 0.2) / 0.9))
    if n > 1:
        d.line(pts[:n], fill=BLUE + (255,), width=9, joint="curve")
        ex, ey = pts[n - 1]; d.ellipse((ex - 11, ey - 11, ex + 11, ey + 11), fill=(230, 70, 120, 255))
    paste_c(c, text("สมองขาดพลังงาน จึงเวียนหัว", 30, (190, 60, 130)), CW // 2, 385, 1.0, clamp((lt - 0.8) / 0.3))

def body7(c, lt):
    paste_c(c, emoji("🦠", 120), 160, 215, ease_back((lt - 0.1) / 0.3), 1.0, 10 * math.sin(lt * 6))
    paste_c(c, text("ลำไส้", 34, NAVY), 160, 320, 1.0, clamp((lt - 0.2) / 0.2))
    arrow(c, 280, 470, 215, (lt - 0.35) / 0.35)
    paste_c(c, emoji("👄", 120), 600, 215, ease_back((lt - 0.6) / 0.3))
    for k in range(3):  # odor wisps
        ph = (lt * 0.9 + k / 3) % 1
        paste_c(c, text("~", 60, (150, 190, 120)), 640 + 20 * k, 170 - 90 * ph, 1.0, clamp((lt - 0.7) / 0.2) * (1 - ph))
    paste_c(c, text("กลิ่นปาก", 34, NAVY), 600, 320, 1.0, clamp((lt - 0.7) / 0.2))
    paste_c(c, text("แบคทีเรียในลำไส้ไม่สมดุล", 30, (190, 60, 130)), CW // 2, 385, 1.0, clamp((lt - 0.9) / 0.3))

def o2(sz):
    im = Image.new("RGBA", (sz, sz), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse((0, 0, sz - 1, sz - 1), fill=SKY + (200,), outline=WHITE + (255,), width=3)
    t1 = text("O", int(sz * 0.45), NAVY); t2 = text("2", int(sz * 0.26), NAVY)
    im.alpha_composite(t1, (sz // 2 - t1.width // 2 - 6, sz // 2 - t1.height // 2)); im.alpha_composite(t2, (sz // 2 + t1.width // 2 - 8, sz // 2))
    return im
O2 = {s: o2(s) for s in (60, 80, 100)}
def body8(c, lt):
    br = 1 + 0.06 * math.sin(lt * 2 * math.pi * 0.8)
    paste_c(c, emoji("🫁", 170), 190, 225, ease_back((lt - 0.05) / 0.35) * br)
    for k in range(7):
        ph = (lt * 0.55 + k / 7) % 1; sz = (60, 80, 100)[k % 3]
        paste_c(c, O2[sz], 420 + (k * 53) % 280 + 15 * math.sin(lt * 3 + k), 340 - 230 * ph, 1.0, clamp((lt - 0.3) / 0.3) * min(1, (1 - ph) * 3, ph * 6))
    paste_c(c, text("หาวบ่อย = ร่างกายต้องการอากาศ", 30, (190, 60, 130)), CW // 2, 385, 1.0, clamp((lt - 0.7) / 0.3))

def body9(c, lt):
    d = ImageDraw.Draw(c); cx, cy, R = 190, 320, 140
    segs = [((150, 220, 170), 180, 252), ((250, 220, 120), 252, 306), ((240, 110, 140), 306, 360)]
    for col, a0, a1 in segs: d.arc((cx - R, cy - R, cx + R, cy + R), a0, a1, fill=col + (255,), width=34)
    p = ease_out((lt - 0.2) / 1.6); ang = math.radians(180 + 165 * p)
    d.line([(cx, cy), (cx + (R - 30) * math.cos(ang), cy + (R - 30) * math.sin(ang))], fill=NAVY + (255,), width=10)
    d.ellipse((cx - 18, cy - 18, cx + 18, cy + 18), fill=NAVY + (255,))
    sys_ = int(100 + 45 * p); dia = int(60 + 32 * p); hi = sys_ >= 140
    col = (225, 60, 120) if hi else BLUE
    paste_c(c, text(f"{sys_}/{dia}", 96, col, 6, WHITE), 540, 190, 1.0 + (0.08 * math.sin(lt * 12) if hi else 0), clamp(lt / 0.2))
    paste_c(c, text("mmHg", 28, (150, 160, 190)), 540, 262, 1.0, clamp(lt / 0.2))
    paste_c(c, text("เกิน 140/90 = ความดันสูง", 30, (190, 60, 130)), 545, 340, 1.0, clamp((lt - 1.2) / 0.3))

CARD_DEF = {
 "1": ("ร่างกายขาดน้ำ", body1),
 "2": ("แมกนีเซียมพบใน", lambda c, lt: food_body(c, lt, [("🥜", "ถั่ว"), ("🥑", "อะโวคาโด"), ("🥬", "ผักใบเขียว"), ("🍌", "กล้วย")])),
 "3": ("ขาบวม = สัญญาณหัวใจ", body3),
 "4": ("ธาตุเหล็กพบใน", lambda c, lt: food_body(c, lt, [("🥩", "เนื้อแดง"), ("🥬", "ผักใบเขียว"), ("🥚", "ไข่แดง"), ("🫘", "ถั่วแดง")])),
 "5": ("วิตามิน B12 พบใน", lambda c, lt: food_body(c, lt, [("🐟", "ปลา"), ("🥚", "ไข่"), ("🥛", "นม"), ("🍗", "ไก่")])),
 "6": ("น้ำตาลในเลือดต่ำ", body6),
 "7": ("กลิ่นปาก มาจากลำไส้", body7),
 "8": ("ออกซิเจนไม่พอ", body8),
 "9": ("วัดความดันโลหิต", body9),
}
def draw_card(fr, key, t):
    a, b = CARDS[key]
    if not (a <= t <= b): return
    lt = t - a; title, body = CARD_DEF[key]
    base, pad = card_base(title); c = base.copy(); sub = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    body(sub, lt); c.alpha_composite(sub, (pad, pad))
    pin = ease_back(lt / 0.35); pout = clamp((t - (b - 0.2)) / 0.2)
    sc = 0.88 * (0.9 + 0.1 * pin) * (1 + 0.02 * lt)  # entrance + slow ken-burns
    paste_c(fr, c, CX + 120 * (1 - ease_out(lt / 0.35)), CY + 40 * pout, sc, clamp(lt / 0.15) * (1 - pout))

# ---------- other motion graphics ----------
ICON_E = {"hook": "🚨", "1": "💧", "2": "🦵", "3": "🦶", "4": "💇", "5": "✋", "6": "😵", "7": "👃", "8": "🥱", "9": "👂", "teaser": "💡", "cta": "🔔"}
ICONS = [("hook", 0.25, GT["hook"][1] - 0.05)] + [(k, GT[k][0] + 0.3, CARDS[k][0] - 0.02) for k in CARDS] + \
        [("teaser", GT["teaser"][0] + 0.3, GT["teaser"][1] - 0.05), ("cta", GT["cta"][0] + 0.4, TOTAL)]
def draw_icons(fr, t):
    for k, s, e in ICONS:
        if not (s <= t <= e): continue
        lt = t - s; a = clamp(lt / 0.2) * clamp((e - t) / 0.15)
        rot = 14 * math.exp(-lt * 1.5) * math.sin(lt * 14) if k == "cta" else 0
        paste_c(fr, badge(ICON_E[k]), 910, 750 - 34 * (1 - ease_out(lt / 0.3)) + 7 * math.sin(lt * 2.6), ease_back(lt / 0.3), a, rot)

def ecg_pts():
    pts = []; x = 0
    pattern = [(0, 0), (60, 0), (75, -18), (90, 0), (110, 0), (120, 20), (135, -120), (150, 60), (162, 0), (200, 0), (225, -30), (250, 0), (270, 0)]
    while x < W + 270:
        pts += [(x + px, py) for px, py in pattern]; x += 270
    return pts
ECG = ecg_pts()
def draw_ecg(fr, t):
    if t > 1.5: return
    p = ease_out(t / 1.0); xmax = W * p; a = clamp((1.5 - t) / 0.4)
    pts = [(x, 690 + y) for x, y in ECG if x <= xmax]
    if len(pts) < 2: return
    lay = Image.new("RGBA", (W, 260), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    pp = [(x, y - 560) for x, y in pts]
    d.line(pp, fill=PINK + (int(150 * a),), width=22, joint="curve"); lay = lay.filter(ImageFilter.GaussianBlur(8))
    d = ImageDraw.Draw(lay); d.line(pp, fill=(236, 72, 153, int(255 * a)), width=8, joint="curve")
    hx, hy = pp[-1]; d.ellipse((hx - 12, hy - 12, hx + 12, hy + 12), fill=WHITE + (int(255 * a),))
    fr.alpha_composite(lay, (0, 560))

def draw_rings(fr, t):
    for k in range(2):
        lt = t - 0.3 - k * 0.35
        if 0 <= lt <= 0.9:
            p = ease_out(lt / 0.9); r = 120 + 260 * p
            lay = Image.new("RGBA", (W, 700), (0, 0, 0, 0))
            ImageDraw.Draw(lay).ellipse((540 - r * 1.4, 350 - r * 0.5, 540 + r * 1.4, 350 + r * 0.5), outline=SKY + (int(220 * (1 - p)),), width=8)
            fr.alpha_composite(lay, (0, 120))

def draw_grid(fr, t):
    s, e = GT["teaser"][0] + 0.25, GT["teaser"][1] - 0.1
    if not (s <= t <= e): return
    a_out = clamp((e - t) / 0.25)
    for i, k in enumerate("123456789"):
        lt = t - s - i * 0.09; r, c = divmod(i, 3)
        paste_c(fr, badge(ICON_E[k], 150), 395 + c * 145, 1185 + r * 145, ease_back(lt / 0.3), clamp(lt / 0.12) * a_out)
        if lt > 0.2:
            paste_c(fr, text(k, 34, WHITE, 5, NAVY), 395 + c * 145 + 48, 1185 + r * 145 - 48, ease_back((lt - 0.2) / 0.25), a_out)

def frame(t):
    fr = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_ecg(fr, t); draw_rings(fr, t); draw_icons(fr, t); draw_grid(fr, t)
    for k in CARDS: draw_card(fr, k, t)
    return fr

if PREVIEW:
    for ts in sys.argv[3:]:
        frame(float(ts)).save(f"{V}/pv_{ts}.png")
else:
    out = sys.stdout.buffer; n = int(round(TOTAL * FPS)) + 3
    for i in range(n): out.write(frame(i / FPS).tobytes())
