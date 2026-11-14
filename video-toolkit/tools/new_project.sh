#!/usr/bin/env bash
# Usage: tools/new_project.sh <clip.mp4> [project-name]
# Creates projects/<name>/ with src.mp4, prints file identity and warns if this exact clip was used before.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; CLIP="$1"
[ -f "$CLIP" ] || { echo "❌ ไม่พบไฟล์: $CLIP"; exit 1; }
SHA=$(sha256sum "$CLIP" | cut -d' ' -f1); NAME="${2:-$(date +%Y%m%d-%H%M)-${SHA:0:8}}"
P="$ROOT/projects/$NAME"; REG="$ROOT/projects/.registry.tsv"; mkdir -p "$P"; touch "$REG"
echo "📄 ไฟล์ที่ได้รับ : $(basename "$CLIP")"
echo "🔑 SHA-256      : $SHA"
ffprobe -v error -show_entries format=duration:stream=width,height,r_frame_rate -of default=nw=1 "$CLIP" | sed 's/^/   /'
if grep -q "^$SHA" "$REG"; then
  echo "⚠️  คลิปนี้เหมือนกับที่เคยใช้แล้วทุกไบต์: $(grep "^$SHA" "$REG" | cut -f2,3 | tr '\n' ' ')"
  echo "   → ถ้าตั้งใจส่งคลิปใหม่ อาจแนบผิดไฟล์"
fi
cp "$CLIP" "$P/src.mp4"; printf '%s\t%s\t%s\n' "$SHA" "$NAME" "$(basename "$CLIP")" >> "$REG"
ffmpeg -v error -y -i "$P/src.mp4" -ac 1 -ar 16000 -f f32le "$P/audio16k.f32"
echo "📁 โปรเจกต์: $P"
