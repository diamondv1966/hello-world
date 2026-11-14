"""Thai transcription with timestamps (overlapping chunks are more robust than one pass).
Usage: python3 -I tools/transcribe.py <project_dir> [chunk=9] [step=6.5]
Reads <project_dir>/audio16k.f32, writes transcript.txt"""
import sys, os, numpy as np
from faster_whisper import WhisperModel
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = sys.argv[1]; CH = float(sys.argv[2]) if len(sys.argv) > 2 else 9.0; ST = float(sys.argv[3]) if len(sys.argv) > 3 else 6.5
m = WhisperModel(f"{ROOT}/assets/model", device="cpu", compute_type="int8")
a = np.fromfile(f"{P}/audio16k.f32", dtype="float32"); dur = len(a) / 16000; lines = []
for st in np.arange(0, max(dur - 1, 0.1), ST):
    seg = a[int(st * 16000):int((st + CH) * 16000)]
    for s in m.transcribe(seg, language="th", beam_size=5, condition_on_previous_text=False)[0]:
        lines.append(f"[{st + s.start:6.2f}-{st + s.end:6.2f}] {s.text.strip()}")
open(f"{P}/transcript.txt", "w").write("\n".join(lines) + "\n"); print("\n".join(lines))
