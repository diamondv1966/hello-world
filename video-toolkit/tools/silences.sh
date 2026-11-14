#!/usr/bin/env bash
# Usage: tools/silences.sh <video> [noise_dB=-33] [min_sec=0.2]  → lists silent gaps (start-end duration)
ffmpeg -i "$1" -af "silencedetect=noise=${2:--33}dB:d=${3:-0.2}" -f null - 2>&1 \
 | grep -o "silence_end: [0-9.]* | silence_duration: [0-9.]*" \
 | awk '{printf "%6.2f - %6.2f  (%.2fs)\n",$2-$5,$2,$5}'
