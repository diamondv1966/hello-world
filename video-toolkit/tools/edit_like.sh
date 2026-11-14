#!/usr/bin/env bash
# One command: clip + reference style -> edited clip.
# Usage: tools/edit_like.sh <clip.mp4> <ref> [project-name] [--lang th|en] [--plan-only]
#   <ref> = path to a reference video (.mp4/.mov) | preset name (clean-pastel, bold-hormozi, calm-abdaal, codie-bold, minimal-aesthetic)
#           | creator keyword (hormozi, abdaal, codie, minimal, pastel)
# Claude then reviews projects/<name>/ (transcript, ref_sheet.jpg), writes config.json (hook/emphasis/cards/cta)
# and re-runs:  python3 -I tools/auto_edit.py projects/<name> --preset <p> [--ref .../style_profile.json]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
CLIP="$1"; REF="$2"; NAME="${3:-}"; LANG_=th; EXTRA=()
for a in "$@"; do case "$a" in --lang) ;; th|en) LANG_=$a;; --plan-only) EXTRA+=(--plan-only);; esac; done
[[ -z "$NAME" || "$NAME" == --* ]] && NAME="$(date +%m%d-%H%M)-$(basename "${CLIP%.*}" | tr -cd '[:alnum:]-' | cut -c1-20)"
tools/new_project.sh "$CLIP" "$NAME" > "projects/.last_intake.txt"; cat projects/.last_intake.txt
P="projects/$NAME"; [ -f "$P/config.json" ] || echo "{\"language\": \"$LANG_\"}" > "$P/config.json"
case "${REF,,}" in
  *hormozi*|*bold*) PRESET=bold-hormozi;; *abdaal*|*calm*) PRESET=calm-abdaal;; *codie*) PRESET=codie-bold;;
  *minimal*|*vlog*|*aesthetic*) PRESET=minimal-aesthetic;; *pastel*|*clean*|default) PRESET=clean-pastel;; *) PRESET="";;
esac
REFARG=()
if [ -z "$PRESET" ] && [ -f "$REF" ]; then
  echo "🔎 วิเคราะห์ reference: $(basename "$REF")"
  python3 -I tools/analyze_ref.py "$REF" "$P/ref" --lang "$LANG_" | tail -4
  PRESET=$(python3 -c "import json;print(json.load(open('$P/ref/style_profile.json'))['suggested_base_preset'])")
  REFARG=(--ref "$P/ref/style_profile.json")
elif [ -z "$PRESET" ]; then echo "⚠️ ไม่รู้จัก ref '$REF' → ใช้ clean-pastel"; PRESET=clean-pastel; fi
echo "🎨 preset: $PRESET"
python3 -I tools/auto_edit.py "$P" --preset "$PRESET" "${REFARG[@]}" "${EXTRA[@]}"
