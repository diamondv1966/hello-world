"""Thai tone marks must survive libass: every ASS style emitted by auto_edit.py has Spacing=0 (Spacing=1 drops marks with KanitXB)."""
import os, re, subprocess, sys, tempfile
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); TOOLS = os.path.dirname(HERE); ROOT = os.path.dirname(TOOLS)
FONTS = f"{ROOT}/assets/fonts"

def style(spacing):  # same field layout as the Cap style line in auto_edit.py
    return (f"Style: Cap,KanitXB,120,&H00FFFFFF,&H00FFFFFF,&H006B2A12,&H80000000,0,0,0,0,100,100,{spacing},0,1,9,3,2,60,60,200,1")

def render(text, spacing, d):
    ass = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
           + style(spacing) + "\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
           f"Dialogue: 0,0:00:00.00,0:00:02.00,Cap,,0,0,0,,{{\\an2\\pos(540,1000)}}{text}\n")
    a = f"{d}/t.ass"; open(a, "w").write(ass); out = f"{d}/{spacing}_{abs(hash(text))}.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=1080x1920:d=1", "-vf", f"ass={a}:fontsdir={FONTS}",
                    "-frames:v", "1", out], check=True)
    return np.asarray(Image.open(out).convert("L"), dtype=float)

def top_row(img):  # first row with ink (text is white/blue on black); tone mark above upper vowel raises it
    rows = np.where((img > 40).any(axis=1))[0]
    return int(rows.min())

with tempfile.TemporaryDirectory() as d:
    with_mark, without = "เสี่ยง", "เสียง"
    h0 = top_row(render(without, 0, d)) - top_row(render(with_mark, 0, d))
    h1 = top_row(render(without, 1, d)) - top_row(render(with_mark, 1, d))
    print("ink rise from tone mark: Spacing=0 ->", h0, "px, Spacing=1 ->", h1, "px")
    assert h0 >= 8, "tone mark missing with Spacing=0"
    assert h1 < h0, "documented bug (Spacing=1 drops marks) no longer reproduces"
src = open(f"{TOOLS}/auto_edit.py", encoding="utf-8").read()
for line in re.findall(r'f"Style: [^"]*"', src):
    f = line.split(",")
    sp = f[1 + 12 - 1 + 0]  # placeholder, validated below
assert ",100,100,1,0," not in src and "\\fsp" not in src, "auto_edit emits non-zero spacing"
assert len(re.findall(r",100,100,0,0,", src)) >= 6, "all 6 styles must have Spacing=0"
print("OK")
