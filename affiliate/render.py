"""Turn copy + product photos into a 9:16 video (AI voice + captions) and a 4:5 image post.

Needs ffmpeg/ffprobe on PATH. Voice uses edge-tts (free); if it fails the clip is
rendered silent with captions only, so the day's work never stops on TTS.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

from . import config

THAI_NO_BREAK_BEFORE = set(chr(c) for c in list(range(0x0E30, 0x0E3B)) + list(range(0x0E45, 0x0E4F)))
THAI_NO_BREAK_AFTER = set("เแโใไ")


def run(cmd: list[str], cwd: Path) -> None:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {r.stderr[-800:]}")


def duration(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
                       capture_output=True, text=True)
    return float(json.loads(r.stdout)["format"]["duration"])


def wrap_thai(text: str, width: int = config.CAPTION_ROW_MAX) -> list[str]:
    """Split a caption into rows <= width without cutting a Thai syllable mark off its consonant."""
    rows = []
    for row in text.replace("\\n", "\n").split("\n"):
        row = row.strip()
        while len(row) > width:
            cut = row.rfind(" ", 0, width + 1)
            if cut <= 0:
                cut = width
                while cut > 1 and (row[cut] in THAI_NO_BREAK_BEFORE or row[cut - 1] in THAI_NO_BREAK_AFTER):
                    cut -= 1
            rows.append(row[:cut].strip())
            row = row[cut:].strip()
        if row:
            rows.append(row)
    return rows[:3]


def ass_time(t: float) -> str:
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def ass_header(w: int, h: int, styles: list[str]) -> str:
    return ("[Script Info]\nScriptType: v4.00+\n"
            f"PlayResX: {w}\nPlayResY: {h}\nWrapStyle: 2\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n" + "\n".join(styles) +
            "\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")


def style(name: str, size: int, colour: str, align: int, margin_v: int, box: bool = False) -> str:
    border = "3" if box else "1"
    back = "&H99000000" if box else "&H00000000"
    outline = "&H60000000" if box else "&H00000000"  # with BorderStyle 3 the box takes the outline colour
    return (f"Style: {name},{config.FONT},{size},{colour},&H000000FF,{outline},{back},-1,0,0,0,100,100,0,0,"
            f"{border},5,1,{align},60,60,{margin_v},1")


def tts(text: str, voice: str, out: Path) -> float | None:
    try:
        run([sys.executable, "-m", "edge_tts", "--voice", voice, "--rate", config.TTS_RATE,
             "--text", text, "--write-media", out.name], out.parent)
        return duration(out)
    except Exception as e:  # noqa: BLE001 - fall back to a silent clip
        print(f"   ! TTS failed, rendering without voice ({str(e)[:120]})")
        return None


def make_video(content: dict, images: list[Path], out_mp4: Path) -> float:
    work = out_mp4.parent / "_work"
    work.mkdir(parents=True, exist_ok=True)
    lines = content["video"]["lines"]
    voice = config.VOICES.get(content.get("voice", "female"), config.VOICES["female"])

    # 1) audio per line, each padded to its slot length
    durs = []
    voiced = True
    for i, line in enumerate(lines):
        mp3 = work / f"l{i}.mp3"
        d = tts(line["say"], voice, mp3) if voiced else None
        if d is None:
            voiced = False
            d = max(2.2, len(line["say"]) / 11)
        durs.append(d + 0.35)
    total = sum(durs)
    if total < config.MIN_VIDEO_SEC:
        durs[-1] += config.MIN_VIDEO_SEC - total
        total = config.MIN_VIDEO_SEC
    parts = []
    for i, d in enumerate(durs):
        wav = f"l{i}.wav"
        if voiced:
            run(["ffmpeg", "-y", "-i", f"l{i}.mp3", "-af", f"apad=whole_dur={d:.3f}", "-ar", "44100", "-ac", "2", wav], work)
        else:
            run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", f"{d:.3f}", wav], work)
        parts.append(f"file '{wav}'")
    (work / "audio.txt").write_text("\n".join(parts), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "audio.txt", "-c:a", "pcm_s16le", "audio.wav"], work)

    # 2) picture: each photo pans slowly over a blurred copy of itself
    imgs = images[:5] or []
    seg = total / len(imgs)
    clips = []
    for i, img in enumerate(imgs):
        src = work / f"src{i}{img.suffix.lower()}"
        shutil.copyfile(img, src)
        direction = "(iw-1000)*t/{d}" if i % 2 == 0 else "(iw-1000)*(1-t/{d})"
        vf = ("[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=28:2,"
              "eq=brightness=-0.10[bg];"
              "[0:v]scale=1100:1100:force_original_aspect_ratio=decrease,"
              "pad=1100:1100:(ow-iw)/2:(oh-ih)/2:color=white,"
              f"crop=1000:1000:x='{direction.format(d=seg)}':y='(ih-1000)/2'[fg];"
              "[bg][fg]overlay=40:330,format=yuv420p")
        clip = f"v{i}.mp4"
        run(["ffmpeg", "-y", "-loop", "1", "-framerate", "30", "-t", f"{seg:.3f}", "-i", src.name,
             "-filter_complex", vf, "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", clip], work)
        clips.append(f"file '{clip}'")
    (work / "video.txt").write_text("\n".join(clips), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "video.txt", "-c", "copy", "video.mp4"], work)

    # 3) captions: first line is the hook at the top, the rest at the bottom
    ass = ass_header(1080, 1920, [style("Hook", 78, "&H0000E5FF", 8, 120, box=True),
                                  style("Main", 70, "&H00FFFFFF", 2, 300, box=True)])
    t = 0.0
    for i, (line, d) in enumerate(zip(lines, durs)):
        text = "\\N".join(wrap_thai(line["caption"]))
        ass += f"Dialogue: 0,{ass_time(t)},{ass_time(t + d)},{'Hook' if i == 0 else 'Main'},,0,0,0,,{text}\n"
        t += d
    (work / "subs.ass").write_text(ass, encoding="utf-8")
    run(["ffmpeg", "-y", "-i", "video.mp4", "-i", "audio.wav", "-vf", "subtitles=subs.ass",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-c:a", "aac", "-b:a", "128k",
         "-shortest", "-movflags", "+faststart", "final.mp4"], work)
    shutil.move(str(work / "final.mp4"), out_mp4)
    shutil.rmtree(work, ignore_errors=True)
    return round(total, 1)


def make_image(content: dict, image: Path, out_jpg: Path) -> None:
    work = out_jpg.parent / "_img"
    work.mkdir(parents=True, exist_ok=True)
    src = work / f"src{image.suffix.lower()}"
    shutil.copyfile(image, src)
    rows = wrap_thai(content["image_headline"])
    ass = ass_header(1080, 1350, [style("Head", 76, "&H00FFFFFF", 2, 70, box=True)])
    joined = "\\N".join(rows)
    ass += f"Dialogue: 0,0:00:00.00,0:00:05.00,Head,,0,0,0,,{joined}\n"
    (work / "head.ass").write_text(ass, encoding="utf-8")
    vf = ("[0:v]scale=1080:1350:force_original_aspect_ratio=increase,crop=1080:1350,boxblur=28:2,eq=brightness=-0.12[bg];"
          "[0:v]scale=980:980:force_original_aspect_ratio=decrease,pad=980:980:(ow-iw)/2:(oh-ih)/2:color=white[fg];"
          "[bg][fg]overlay=50:50,subtitles=head.ass")
    run(["ffmpeg", "-y", "-loop", "1", "-t", "1", "-i", src.name, "-filter_complex", vf,
         "-frames:v", "1", "-q:v", "2", "post.jpg"], work)
    shutil.move(str(work / "post.jpg"), out_jpg)
    shutil.rmtree(work, ignore_errors=True)
