#!/usr/bin/env bash
# Usage: tools/measure.sh <video>  → loudness (LUFS/peak), hiss level, brightness & saturation
V="$1"; ffmpeg -i "$V" -af ebur128=peak=true -f null - 2>&1 | grep -A15 Summary | grep -E "I:|LRA:|Peak:"
ffmpeg -i "$V" -af "highpass=f=8000,volumedetect" -f null - 2>&1 | grep -o "mean_volume.*" | sed 's/^/hiss>8kHz /'
for k in YAVG SATAVG; do ffmpeg -i "$V" -vf "signalstats,metadata=print:key=lavfi.signalstats.$k:file=-" -f null - 2>/dev/null | grep "$k" | awk -F= -v k=$k '{s+=$2;n++} END{printf "%s %.1f\n",k,s/n}'; done
