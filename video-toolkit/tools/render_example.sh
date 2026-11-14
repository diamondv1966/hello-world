#!/usr/bin/env bash
# Full render pipeline used for the 9-signals example (template for new projects).
# Usage: tools/render_example.sh <project_dir> [script_dir=examples/9-signals]
# The project dir must contain src.mp4 and timeline.py (cuts, zooms, item text, card timings).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; P="$(cd "$1" && pwd)"; S="${2:-$ROOT/examples/9-signals}"
echo "1/5 base video (cuts + zoom + grade + Thai text)"; python3 -I "$S/video.py" "$ROOT" "$P" > "$P/video.log"
echo "2/5 music + original SFX";  python3 -I "$S/sound.py" "$ROOT" "$P"
echo "3/5 SFX cue track";        python3 -I "$S/sfx.py" "$ROOT" "$P"
echo "4/5 motion graphics layer"
python3 -I "$S/gfx.py" "$ROOT" "$P" | ffmpeg -v error -y -i "$P/video_voice.mov" -f rawvideo -pix_fmt rgba -s 1080x1920 -framerate 30 -i pipe:0 \
  -filter_complex "[0:v][1:v]overlay=0:0:eof_action=pass,format=yuv420p[v]" -map "[v]" -map 0:a -c:v libx264 -preset slow -crf 18 -c:a copy -shortest "$P/video_gfx.mov"
echo "5/5 mix + master (-14 LUFS)"
MIX="[0:a]asplit=2[vo][key];[1:a]volume=0.095[mu];[mu][key]sidechaincompress=threshold=0.03:ratio=3:attack=25:release=400:knee=4[mud];[2:a]volume=0.45[fx];[vo][mud][fx]amix=inputs=3:normalize=0:duration=first"
J=$(ffmpeg -i "$P/video_gfx.mov" -i "$P/music_original.wav" -i "$P/sfx_track.wav" -filter_complex "$MIX,loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json" -f null - 2>&1 | sed -n '/^{/,/^}/p')
g(){ echo "$J" | python3 -c "import json,sys;print(json.load(sys.stdin)['$1'])"; }
ffmpeg -v error -y -i "$P/video_gfx.mov" -i "$P/music_original.wav" -i "$P/sfx_track.wav" -filter_complex "$MIX,loudnorm=I=-14:TP=-1.5:LRA=11:measured_I=$(g input_i):measured_TP=$(g input_tp):measured_LRA=$(g input_lra):measured_thresh=$(g input_thresh):offset=$(g target_offset):linear=true,alimiter=limit=0.86:level=false,aresample=48000[a]" \
  -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 256k -movflags +faststart "$P/FINAL.mp4"
echo "✅ $P/FINAL.mp4"
