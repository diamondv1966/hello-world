#!/usr/bin/env bash
# Report what is ready / missing for the video toolkit.
ROOT="$(cd "$(dirname "$0")" && pwd)"; A="$ROOT/assets"; ok=0; bad=0
chk(){ if eval "$2" >/dev/null 2>&1; then printf '  ✅ %s\n' "$1"; ok=$((ok+1)); else printf '  ❌ %s  → %s\n' "$1" "$3"; bad=$((bad+1)); fi; }
echo "ระบบ / System"
chk "FFmpeg + libass/harfbuzz (ใส่ข้อความไทย)" "ffmpeg -hide_banner -filters | grep -q ' ass ' && ffmpeg -version | grep -q harfbuzz" "./setup.sh"
chk "Python 3 + faster-whisper"                 "python3 -c 'import faster_whisper'" "./setup.sh"
chk "Pillow + raqm (วาดกราฟิกภาษาไทย)"         "python3 -c 'from PIL import features; assert features.check(\"raqm\")'" "pip install pillow (with libraqm)"
chk "numpy / fonttools"                         "python3 -c 'import numpy, fontTools'" "./setup.sh"
chk "Node + Playwright/Chromium (ทำ PDF)"        "node -e \"require('playwright')\"" "ใช้ Chromium ที่ติดตั้งมากับเครื่อง"
echo "Assets"
chk "โมเดลถอดเสียง Whisper (assets/model)"      "test -s '$A/model/model.bin'" "./setup.sh"
chk "ฟอนต์ Kanit (assets/fonts)"                "test -s '$A/fonts/KanitXB.ttf' && test -s '$A/fonts/KanitRegular.ttf'" "./setup.sh"
chk "ฟอนต์อีโมจิ Noto Color Emoji"               "fc-list | grep -qi 'Noto Color Emoji'" "apt-get install fonts-noto-color-emoji"
chk "เสียงเอฟเฟกต์ CC0 (assets/uisfx)"          "test -d '$A/uisfx/sounds/glass'" "./setup.sh"
echo "ข้อจำกัดเครือข่าย (ข้อมูล)"
for h in www.pexels.com pixabay.com mixkit.co freesound.org; do
  c=$(curl -s -o /dev/null -w '%{http_code}' -m 6 "https://$h" || true)
  if [ "$c" = "000" ]; then printf '  ⚠️  %s ถูกบล็อก (ต้องส่งไฟล์ B-roll มาเอง)\n' "$h"; else printf '  ✅ %s เข้าถึงได้ (%s)\n' "$h" "$c"; fi
done
echo; echo "พร้อม $ok / ขาด $bad"; [ $bad -eq 0 ] && echo "ระบบพร้อมใช้งานแล้ว ✅"
