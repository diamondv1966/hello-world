"""Turn copy + product photos into a 9:16 Shopee Video clip and a 4:5 Facebook image.

Video recipe (short-form best practice, see docs/PLAN.md "การผลิตคลิป"):
  - title box on screen from frame 1 (most people watch muted)
  - one photo per spoken line, cut on the line, each with its own slow zoom or pan
  - word-synced captions in the lower-middle safe area, current word highlighted
  - AI voice (edge-tts, free), loudness normalised to -14 LUFS, optional quiet music
Needs ffmpeg/ffprobe on PATH. If the voice fails the clip is rendered silent with captions.
"""
import asyncio
import json
import random
import shutil
import subprocess
from pathlib import Path

from . import captions, config

FPS = 30
FG = 880          # product photo size on the 1080x1920 canvas
FG_Y = 470        # photo top edge: below the title box, above the captions
MOTIONS = [
    ("1+0.12*on/{n}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),            # zoom in
    ("1.12", "(iw-iw/zoom)*on/{n}", "ih/2-(ih/zoom/2)"),                  # pan right
    ("1.12-0.12*on/{n}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),         # zoom out
    ("1.12", "(iw-iw/zoom)*(1-on/{n})", "ih/2-(ih/zoom/2)"),              # pan left
]


def run(cmd: list[str], cwd: Path) -> None:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {r.stderr[-800:]}")


def duration(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
                       capture_output=True, text=True)
    return float(json.loads(r.stdout)["format"]["duration"])


async def _tts(text: str, voice: str, out: Path) -> list[tuple[float, float, str]]:
    import edge_tts
    try:
        comm = edge_tts.Communicate(text, voice, rate=config.TTS_RATE, boundary="WordBoundary")
    except TypeError:  # edge-tts < 7 has no boundary option
        comm = edge_tts.Communicate(text, voice, rate=config.TTS_RATE)
    bounds = []
    with out.open("wb") as f:
        async for c in comm.stream():
            if c["type"] == "audio":
                f.write(c["data"])
            elif c["type"] == "WordBoundary":
                bounds.append((c["offset"] / 1e7, c["duration"] / 1e7, c["text"]))
    return bounds


def tts(text: str, voice: str, out: Path) -> tuple[float | None, list]:
    """Returns (seconds, word boundaries) or (None, []) when the voice service is unreachable."""
    try:
        bounds = asyncio.run(_tts(text, voice, out))
        return duration(out), bounds
    except Exception as e:  # noqa: BLE001 - fall back to a silent clip
        print(f"   ! TTS failed, rendering without voice ({str(e)[:120]})")
        return None, []


def font_args() -> str:
    """Point libass at the bundled Kanit font (relative path keeps Windows drive colons out of the filter)."""
    return ":fontsdir=fonts" if config.FONT_FILE.exists() else ""


def copy_fonts(work: Path) -> None:
    if config.FONT_FILE.exists():
        (work / "fonts").mkdir(exist_ok=True)
        shutil.copy(config.FONT_FILE, work / "fonts" / config.FONT_FILE.name)


def _segment(img: Path, seconds: float, motion: int, out: str, work: Path) -> None:
    n = max(int(round(seconds * FPS)), 1)
    z, x, y = (part.format(n=n) for part in MOTIONS[motion % len(MOTIONS)])
    src = f"src_{out}{img.suffix.lower()}"
    shutil.copyfile(img, work / src)
    vf = (f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:3,"
          f"eq=brightness=-0.20:saturation=1.15,setsar=1[bg];"
          # upscale before zoompan so the slow zoom does not shake
          f"[1:v]scale={FG}:{FG}:force_original_aspect_ratio=decrease,pad={FG}:{FG}:(ow-iw)/2:(oh-ih)/2:color=white,"
          f"scale={FG * 3}:{FG * 3},zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={FG}x{FG}:fps={FPS},setsar=1[fg];"
          f"[bg][fg]overlay=(W-w)/2:{FG_Y}:shortest=1,format=yuv420p")
    run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-t", f"{seconds:.3f}", "-i", src, "-i", src,
         "-filter_complex", vf, "-frames:v", str(n), "-r", str(FPS),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", out], work)


def make_video(content: dict, images: list[Path], out_mp4: Path) -> float:
    work = out_mp4.parent / "_work"
    work.mkdir(parents=True, exist_ok=True)
    video = content["video"]
    lines = video["lines"]
    voice = config.VOICES.get(content.get("voice", "female"), config.VOICES["female"])

    # 1) voice per line -> line slots and word timings
    slots, line_words, voiced = [], [], True
    t = 0.0
    for i, line in enumerate(lines):
        say = line["say"].strip()
        d, bounds = tts(say, voice, work / f"l{i}.mp3") if voiced else (None, [])
        if d is None:
            voiced = False
            d = max(1.8, captions.visible_len(say) / 9.5)
            words = captions.time_words(say, t + 0.05, t + d)
        else:
            words = captions.words_from_boundaries(say, bounds, t) or captions.time_words(say, t + 0.08, t + d - 0.05)
        gap = 0.25 if i < len(lines) - 1 else 0.6
        slots.append(d + gap)
        line_words.append(words)
        t += d + gap
    total = sum(slots)
    if total < config.MIN_VIDEO_SEC:
        slots[-1] += config.MIN_VIDEO_SEC - total
        total = config.MIN_VIDEO_SEC
    line_ends, acc = [], 0.0
    for s in slots:
        acc += s
        line_ends.append(acc)

    # 2) audio track
    parts = []
    for i, d in enumerate(slots):
        wav = f"l{i}.wav"
        if voiced:
            run(["ffmpeg", "-y", "-i", f"l{i}.mp3", "-af", f"apad=whole_dur={d:.3f}", "-ar", "44100", "-ac", "2", wav], work)
        else:
            run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", f"{d:.3f}", wav], work)
        parts.append(f"file '{wav}'")
    (work / "audio.txt").write_text("\n".join(parts), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "audio.txt", "-c:a", "pcm_s16le", "voice.wav"], work)

    # 3) picture: one photo per line, cut on the line
    clips = []
    offset = random.randrange(len(MOTIONS))
    for i, d in enumerate(slots):
        name = f"v{i}.mp4"
        _segment(images[i % len(images)], d, i + offset, name, work)
        clips.append(f"file '{name}'")
    (work / "video.txt").write_text("\n".join(clips), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "video.txt", "-c", "copy", "video.mp4"], work)

    # 4) captions + final mix
    title = video.get("title") or lines[0].get("caption", "")
    ass = captions.video_ass(title, line_words, line_ends, content.get("keywords", []), total)
    (work / "subs.ass").write_text(ass, encoding="utf-8")
    copy_fonts(work)
    music = sorted(p for p in config.MUSIC_DIR.glob("*") if p.suffix.lower() in {".mp3", ".m4a", ".wav"}) \
        if config.MUSIC_DIR.exists() else []
    loud = "loudnorm=I=-14:TP=-1.5:LRA=11"
    cmd = ["ffmpeg", "-y", "-i", "video.mp4", "-i", "voice.wav"]
    if music:
        shutil.copyfile(random.choice(music), work / "music.audio")
        cmd += ["-stream_loop", "-1", "-i", "music.audio"]
        # music ducks under the voice
        audio = (f"[1:a]asplit=2[v1][v2];[2:a]volume={config.MUSIC_VOLUME}[m];"
                 "[m][v1]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[d];"
                 f"[v2][d]amix=inputs=2:duration=first:normalize=0,{loud}[a]")
    else:
        audio = f"[1:a]{loud}[a]"
    cmd += ["-filter_complex", f"[0:v]subtitles=subs.ass{font_args()}[v];{audio}", "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-t", f"{total:.3f}", "-movflags", "+faststart", "final.mp4"]
    run(cmd, work)
    shutil.move(str(work / "final.mp4"), out_mp4)
    shutil.rmtree(work, ignore_errors=True)
    return round(total, 1)


def make_image(content: dict, image: Path, out_jpg: Path) -> None:
    work = out_jpg.parent / "_img"
    work.mkdir(parents=True, exist_ok=True)
    src = f"src{image.suffix.lower()}"
    shutil.copyfile(image, work / src)
    (work / "head.ass").write_text(captions.image_ass(content["image_headline"]), encoding="utf-8")
    copy_fonts(work)
    vf = ("[0:v]scale=1080:1350:force_original_aspect_ratio=increase,crop=1080:1350,boxblur=30:3,"
          "eq=brightness=-0.20:saturation=1.15[bg];"
          "[0:v]scale=900:900:force_original_aspect_ratio=decrease,pad=900:900:(ow-iw)/2:(oh-ih)/2:color=white[fg];"
          f"[bg][fg]overlay=90:340,subtitles=head.ass{font_args()}")
    run(["ffmpeg", "-y", "-loop", "1", "-t", "1", "-i", src, "-filter_complex", vf,
         "-frames:v", "1", "-q:v", "2", "post.jpg"], work)
    shutil.move(str(work / "post.jpg"), out_jpg)
    shutil.rmtree(work, ignore_errors=True)
