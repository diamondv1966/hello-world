#!/usr/bin/env bash
# Usage: tools/contact_sheet.sh <video> <out.jpg> [fps=0.5]  → grid of frames to review gestures/framing
ffmpeg -v error -y -i "$1" -vf "fps=${3:-0.5},scale=180:-1,tile=8x4" -frames:v 1 "$2" && echo "$2"
