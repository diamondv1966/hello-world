"""Turn copy + product photos into a 9:16 Shopee Video clip and a 4:5 Facebook image.

Video recipe (short-form best practice, see docs/PLAN.md "การผลิตคลิป"):
  - title box on screen from frame 1 (most people watch muted)
  - voice trimmed to the speech, lines joined with a short breath, no padded silence (no dead air)
  - shots cut on the speech; three styles so clips do not all look alike:
      framed   = photo on a blurred copy of itself, slow zoom/pan
      wide     = photo across the full width, stronger zoom
      quickcut = two shots per line, alternating photos and motions (faster pacing)
  - optional AI B-roll: clips in media/<id>/clips/*.mp4 are cut in between the real photos
  - word-synced captions in the lower-middle safe area, current word highlighted, colour theme per clip
  - AI voice (edge-tts, free), loudness normalised to -14 LUFS, optional quiet music
Needs ffmpeg/ffprobe on PATH. If every voice fails the clip is rendered silent with captions.
"""
import asyncio
import copy
import json
import re
import random
import shutil
import subprocess
import time
from pathlib import Path

from . import captions, config

FPS = 30
STYLES = ["framed", "wide", "quickcut"]
LAYOUT = {"framed": (880, 470), "wide": (1080, 420), "quickcut": (960, 450)}  # photo size, top edge
MOTIONS = [
    ("1+{zoom}*on/{n}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),             # zoom in
    ("1+{zoom}", "(iw-iw/zoom)*on/{n}", "ih/2-(ih/zoom/2)"),                  # pan right
    ("1+{zoom}-{zoom}*on/{n}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),       # zoom out
    ("1+{zoom}", "(iw-iw/zoom)*(1-on/{n})", "ih/2-(ih/zoom/2)"),              # pan left
]
SILENCE_TRIM = ("silenceremove=start_periods=1:start_threshold=-42dB:start_silence=0.03,areverse,"
                "silenceremove=start_periods=1:start_threshold=-42dB:start_silence=0.03,areverse")


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
    if out.stat().st_size < 1000:
        raise RuntimeError("empty audio")
    return bounds


def _speak_line(text: str, voice: str, work: Path, i: int) -> tuple[float, list]:
    """Synthesize one line and cut the silence around the speech. Returns (seconds, word boundaries)."""
    mp3, wav = work / f"l{i}.mp3", f"t{i}.wav"
    last_error = None
    for attempt in range(4):  # the free voice service throttles bursts: back off and retry
        try:
            bounds = asyncio.run(_tts(text, voice, mp3))
            break
        except Exception as e:  # noqa: BLE001
            last_error = e
            time.sleep(2 + 3 * attempt)
    else:
        raise RuntimeError(f"TTS {voice}: {last_error}")
    if bounds:
        start = max(0.0, bounds[0][0] - 0.05)
        end = bounds[-1][0] + bounds[-1][1] + 0.12
        trim = f"atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS"
        bounds = [(o - start, d, w) for o, d, w in bounds]
    else:
        trim = SILENCE_TRIM
    run(["ffmpeg", "-y", "-i", mp3.name, "-af", trim, "-ar", "44100", "-ac", "2", wav], work)
    return duration(work / wav), bounds


def voice_gender(voice: str) -> str:
    return next((g for g, vs in config.VOICES.items() if voice in vs), "female")


def adapt_particles(text: str, gender: str) -> str:
    """Polite endings must match the voice: a male voice never says ค่ะ/คะ, a female voice never says ครับ."""
    if gender == "male":
        text = re.sub(r"(นะ)?ค[่]?ะ(?=[\s.!?…]|$)", lambda m: (m.group(1) or "") + "ครับ", text)
        return text.replace("ดิฉัน", "ผม")
    return re.sub(r"ครับ(?=[\s.!?…]|$)", "ค่ะ", text)


def synthesize(lines: list[dict], gender: str, work: Path) -> tuple[list[float], list[list], str | None]:
    """All lines in one voice. Tries the chosen gender's voices, then the other gender's.
    Edits lines[i]["say"] in place when the voice changes gender, so captions match what is spoken."""
    order = config.VOICES.get(gender, []) + [v for g, vs in config.VOICES.items() if g != gender for v in vs]
    for voice in order:
        try:
            for line in lines:
                line["say"] = adapt_particles(line["say"], voice_gender(voice))
            out = [_speak_line(l["say"].strip(), voice, work, i) for i, l in enumerate(lines)]
            return [d for d, _ in out], [b for _, b in out], voice
        except Exception as e:  # noqa: BLE001
            print(f"   ! voice {voice} failed ({str(e)[:100]}), trying the next voice")
    return [], [], None


def font_args() -> str:
    """Point libass at the bundled Kanit font (relative path keeps Windows drive colons out of the filter)."""
    return ":fontsdir=fonts" if config.FONT_FILE.exists() else ""


def copy_fonts(work: Path) -> None:
    if config.FONT_FILE.exists():
        (work / "fonts").mkdir(exist_ok=True)
        shutil.copy(config.FONT_FILE, work / "fonts" / config.FONT_FILE.name)


def _photo_shot(img: Path, seconds: float, motion: int, style: str, out: str, work: Path) -> None:
    n = max(int(round(seconds * FPS)), 1)
    size, top = LAYOUT[style]
    zoom = "0.18" if style == "wide" else "0.12"
    z, x, y = (part.format(n=n, zoom=zoom) for part in MOTIONS[motion % len(MOTIONS)])
    src = f"src_{out}{img.suffix.lower()}"
    shutil.copyfile(img, work / src)
    vf = (f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:3,"
          f"eq=brightness=-0.20:saturation=1.15,setsar=1[bg];"
          # upscale before zoompan so the slow zoom does not shake
          f"[1:v]scale={size}:{size}:force_original_aspect_ratio=decrease,pad={size}:{size}:(ow-iw)/2:(oh-ih)/2:color=white,"
          f"scale={size * 3}:{size * 3},zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={size}x{size}:fps={FPS},setsar=1[fg];"
          f"[bg][fg]overlay=(W-w)/2:{top}:shortest=1,format=yuv420p")
    run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-t", f"{seconds:.3f}", "-i", src, "-i", src,
         "-filter_complex", vf, "-frames:v", str(n), "-r", str(FPS),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", out], work)


def _broll_shot(clip: Path, seconds: float, out: str, work: Path) -> None:
    """An AI or stock clip, filled to 9:16, muted, looped if shorter than the line."""
    src = f"src_{out}{clip.suffix.lower()}"
    shutil.copyfile(clip, work / src)
    n = max(int(round(seconds * FPS)), 1)
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", src, "-t", f"{seconds:.3f}",
         "-vf", f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps={FPS},setsar=1,format=yuv420p",
         "-an", "-frames:v", str(n), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", out], work)


def _shot_plan(slots: list[float], style: str, n_images: int, n_clips: int, rng: random.Random) -> list[tuple]:
    """(kind, index, seconds) per shot. Real photos open and close the clip; B-roll goes in between."""
    shots, img_i, clip_i = [], 0, 0
    for li, d in enumerate(slots):
        middle = 0 < li < len(slots) - 1
        if n_clips and middle and li % 2 == 1:
            shots.append(("clip", clip_i % n_clips, d))
            clip_i += 1
            continue
        parts = [d / 2, d / 2] if style == "quickcut" and d > 1.6 else [d]
        for part in parts:
            shots.append(("photo", img_i % n_images, part))
            img_i += 1
    return shots


def make_video(content: dict, images: list[Path], out_mp4: Path, style: str = "framed", theme: str = "shopee",
               clips: list[Path] | None = None, seed: int = 0) -> dict:
    work = out_mp4.parent / "_work"
    work.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    lines = copy.deepcopy(content["video"]["lines"])  # particles may change with the voice; keep the saved copy intact

    # 1) voice: trimmed per line, short breath between lines, small tail at the end
    durs, bounds_all, voice = synthesize(lines, content.get("voice", "female"), work)
    voiced = voice is not None
    slots, line_words, t = [], [], 0.0
    for i, line in enumerate(lines):
        say = line["say"].strip()
        gap = config.LINE_GAP if i < len(lines) - 1 else config.END_TAIL
        if voiced:
            d = durs[i]
            words = captions.words_from_boundaries(say, bounds_all[i], t) or captions.time_words(say, t, t + d)
        else:
            d = max(1.4, captions.visible_len(say) / 11)
            words = captions.time_words(say, t, t + d)
        slots.append(d + gap)
        line_words.append(words)
        t += d + gap
    total = sum(slots)
    line_ends, acc = [], 0.0
    for s in slots:
        acc += s
        line_ends.append(acc)

    parts = []
    for i, d in enumerate(slots):
        wav = f"l{i}.wav"
        if voiced:
            run(["ffmpeg", "-y", "-i", f"t{i}.wav", "-af", f"apad=whole_dur={d:.3f}", wav], work)
        else:
            run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", f"{d:.3f}", wav], work)
        parts.append(f"file '{wav}'")
    (work / "audio.txt").write_text("\n".join(parts), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "audio.txt", "-c:a", "pcm_s16le", "voice.wav"], work)

    # 2) picture
    clips = clips or []
    shot_files, motion = [], rng.randrange(len(MOTIONS))
    for k, (kind, idx, secs) in enumerate(_shot_plan(slots, style, len(images), len(clips), rng)):
        name = f"v{k:02d}.mp4"
        if kind == "clip":
            _broll_shot(clips[idx], secs, name, work)
        else:
            _photo_shot(images[idx], secs, motion, style, name, work)
            motion += 1 if style != "quickcut" else rng.randrange(1, len(MOTIONS))
        shot_files.append(f"file '{name}'")
    (work / "video.txt").write_text("\n".join(shot_files), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "video.txt", "-c", "copy", "video.mp4"], work)

    # 3) captions + final mix
    title = content["video"].get("title") or lines[0].get("caption", "")
    ass = captions.video_ass(title, line_words, line_ends, content.get("keywords", []), total, theme)
    (work / "subs.ass").write_text(ass, encoding="utf-8")
    copy_fonts(work)
    music = sorted(p for p in config.MUSIC_DIR.glob("*") if p.suffix.lower() in {".mp3", ".m4a", ".wav"}) \
        if config.MUSIC_DIR.exists() else []
    loud = "loudnorm=I=-14:TP=-1.5:LRA=11"
    cmd = ["ffmpeg", "-y", "-i", "video.mp4", "-i", "voice.wav"]
    if music:
        shutil.copyfile(rng.choice(music), work / "music.audio")
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
    if total < config.MIN_VIDEO_SEC:
        print(f"   ~ clip is {total:.1f}s (target {config.MIN_VIDEO_SEC:.0f}s+): the script is short, not padded with silence")
    return {"seconds": round(total, 1), "voice": voice or "none", "style": style, "theme": theme,
            "broll": len(clips)}


def make_image(content: dict, image: Path, out_jpg: Path, theme: str = "shopee") -> None:
    work = out_jpg.parent / "_img"
    work.mkdir(parents=True, exist_ok=True)
    src = f"src{image.suffix.lower()}"
    shutil.copyfile(image, work / src)
    (work / "head.ass").write_text(captions.image_ass(content["image_headline"], theme), encoding="utf-8")
    copy_fonts(work)
    vf = ("[0:v]scale=1080:1350:force_original_aspect_ratio=increase,crop=1080:1350,boxblur=30:3,"
          "eq=brightness=-0.20:saturation=1.15[bg];"
          "[0:v]scale=900:900:force_original_aspect_ratio=decrease,pad=900:900:(ow-iw)/2:(oh-ih)/2:color=white[fg];"
          f"[bg][fg]overlay=90:340,subtitles=head.ass{font_args()}")
    run(["ffmpeg", "-y", "-loop", "1", "-t", "1", "-i", src, "-filter_complex", vf,
         "-frames:v", "1", "-q:v", "2", "post.jpg"], work)
    shutil.move(str(work / "post.jpg"), out_jpg)
    shutil.rmtree(work, ignore_errors=True)
