#!/usr/bin/env bash
# Install everything the video toolkit needs into ./assets (idempotent; safe to re-run).
# Sources: PyPI + npm only (stock/audio websites are blocked in Claude Code cloud sessions).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"; A="$ROOT/assets"; T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
mkdir -p "$A/fonts" "$A/model" "$A/uisfx"
say(){ printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

say "1/5 FFmpeg (libass + harfbuzz for Thai text)"
if ! command -v ffmpeg >/dev/null; then apt-get update -qq && apt-get install -y -qq ffmpeg; fi
ffmpeg -version | head -1

say "2/5 Python packages"
python3 -c "import faster_whisper, fontTools, PIL, numpy, pythainlp, cv2, pytesseract" 2>/dev/null || \
  pip install -q "faster-whisper==1.2.1" "fonttools>=4.50" "pillow>=10" "numpy>=1.26" "pythainlp>=5" "opencv-python-headless<5" "pytesseract>=0.3"
command -v tesseract >/dev/null && tesseract --list-langs 2>/dev/null | grep -q tha || \
  { apt-get install -y -qq tesseract-ocr tesseract-ocr-tha >/dev/null 2>&1 || (apt-get update -qq && apt-get install -y -qq tesseract-ocr tesseract-ocr-tha) || echo "WARN: tesseract (OCR for reference captions) not installed"; }
python3 -c "from PIL import features; assert features.check('raqm'), 'PIL needs raqm for Thai shaping'"

say "3/5 Speech-to-text model (Whisper small, CTranslate2 int8, from npm)"
if [ ! -f "$A/model/model.bin" ]; then
  ( cd "$T" && for i in 0 1 2 3; do npm pack --silent "@skillninja/shortmovie-telop-model-p$i@1.0.0" >/dev/null; mkdir -p p$i; tar xzf skillninja-shortmovie-telop-model-p$i-1.0.0.tgz -C p$i; done
    cat p0/package/model.bin.part0 p1/package/model.bin.part1 p2/package/model.bin.part2 p3/package/model.bin.part3 > model.bin
    echo "$(cat p0/package/model.sha256)  model.bin" | sha256sum -c -
    mv model.bin "$A/model/"; cp p0/package/{config.json,preprocessor_config.json,tokenizer.json,vocabulary.json} "$A/model/" )
fi

say "4/5 Thai fonts (Kanit Regular + ExtraBold, Thai+Latin merged, OFL)"
if [ ! -f "$A/fonts/KanitXB.ttf" ] || [ ! -f "$A/fonts/KanitRegular.ttf" ]; then
  ( cd "$T" && npm pack --silent @fontsource/kanit@5.3.0 >/dev/null && mkdir k && tar xzf fontsource-kanit-5.3.0.tgz -C k
    python3 -I - "$T/k/package/files" "$A/fonts" <<'PY'
import sys
from fontTools.ttLib import TTFont
from fontTools.merge import Merger
src, dst = sys.argv[1], sys.argv[2]
for w, name in ((800, "KanitXB"), (400, "KanitRegular")):
    parts = []
    for sub in ("latin", "thai"):
        f = TTFont(f"{src}/kanit-{sub}-{w}-normal.woff"); f.flavor = None
        p = f"{dst}/_{sub}.ttf"; f.save(p); parts.append(p)
    m = Merger().merge(parts)
    for r in m["name"].names:
        if r.nameID in (1, 4, 6, 16): r.string = name
    m.save(f"{dst}/{name}.ttf")
import os; [os.remove(f"{dst}/_{s}.ttf") for s in ("latin", "thai")]
PY
  )
fi
fc-list | grep -qi "Noto Color Emoji" || { apt-get install -y -qq fonts-noto-color-emoji || echo "WARN: emoji font missing (icons need it)"; }

say "5/5 Sound effects (uisfx, CC0 public domain)"
if [ ! -d "$A/uisfx/sounds" ]; then
  ( cd "$T" && npm pack --silent uisfx@0.4.0 >/dev/null && mkdir u && tar xzf uisfx-0.4.0.tgz -C u
    cp -r u/package/sounds "$A/uisfx/" && cp u/package/LICENSE-AUDIO "$A/uisfx/LICENSE-CC0.txt" )
fi

say "Done — run ./check_system.sh"
