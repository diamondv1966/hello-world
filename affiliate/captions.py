"""Word-synced Thai captions (karaoke style) as an ASS subtitle file.

Short-form best practice: show 2-4 words at a time in the lower-middle of the frame,
bold font with a heavy outline, and highlight the word being spoken. Thai has no
spaces between words, so words come from edge-tts word boundaries when available,
else from pythainlp ("longest" engine), else from a safe character split.
"""
import re
from dataclasses import dataclass

from . import config

MARKS = set(chr(c) for c in [0x0E31] + list(range(0x0E34, 0x0E3B)) + list(range(0x0E47, 0x0E4F)))
LEADING_VOWELS = set("เแโใไ")
ATTACH_TO_PREV = re.compile(r"^[ๆ.,!?…)\]\"'%]+$")

# ASS colours are &HAABBGGRR
WHITE = "&H00FFFFFF"
BLACK = "&H00000000"
YELLOW = "&H004DE1FF"      # #FFE14D active word
ORANGE = "&H002D4DEE"      # #EE4D2D Shopee orange (title box)
KEYWORD = "&H00458AFF"     # #FF8A45 keywords
SHADOW = "&H96000000"

# Colour themes so clips do not all look the same; the planner picks one per clip (learning.choose).
THEMES = {
    "shopee": {"title_box": ORANGE, "title_text": WHITE, "active": YELLOW, "cta_box": YELLOW, "cta_text": BLACK,
               "cta_active": ORANGE},
    "night": {"title_box": "&H00151515", "title_text": WHITE, "active": "&H00FFE14D", "cta_box": WHITE,
              "cta_text": BLACK, "cta_active": "&H002D2DE0"},
    "mint": {"title_box": "&H007FA310", "title_text": WHITE, "active": YELLOW, "cta_box": "&H007FA310",
             "cta_text": WHITE, "cta_active": YELLOW},
    "berry": {"title_box": "&H005B18C2", "title_text": WHITE, "active": YELLOW, "cta_box": YELLOW, "cta_text": BLACK,
              "cta_active": "&H005B18C2"},
}


@dataclass
class Word:
    text: str
    start: float
    end: float
    space_after: bool = False


def visible_len(s: str) -> int:
    return sum(1 for ch in s if ch not in MARKS and not ch.isspace())


def _safe_split(text: str, size: int = 6) -> list[str]:
    """Fallback when pythainlp is missing: cut every ~size chars, never before a mark or after a leading vowel."""
    out, cur = [], ""
    for i, ch in enumerate(text):
        cur += ch
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if visible_len(cur) >= size and nxt and nxt not in MARKS and ch not in LEADING_VOWELS:
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return out


def tokenize(text: str) -> list[str]:
    """Words with single " " tokens where the text had spaces."""
    text = re.sub(r"\s+", " ", text.strip())
    try:
        from pythainlp.tokenize import word_tokenize
        raw = word_tokenize(text, engine="longest", keep_whitespace=True)
    except Exception:  # noqa: BLE001 - library missing or failed
        raw = []
        for i, part in enumerate(text.split(" ")):
            if i:
                raw.append(" ")
            raw += _safe_split(part)
    tokens: list[str] = []
    for tok in raw:
        if tok.isspace():
            if tokens and tokens[-1] != " ":
                tokens.append(" ")
        elif tokens and tokens[-1] != " " and ATTACH_TO_PREV.match(tok):
            tokens[-1] += tok
        elif tok:
            tokens.append(tok)
    while tokens and tokens[-1] == " ":
        tokens.pop()
    return tokens


def _weight(tok: str) -> float:
    w = 0.0
    for ch in tok:
        if ch.isdigit():
            w += 2.5          # "120" is read as several syllables
        elif ch in MARKS:
            continue
        elif ch.isascii() and ch.isalpha():
            w += 0.6
        else:
            w += 1.0
    return max(w, 0.5)


def time_words(text: str, start: float, end: float) -> list[Word]:
    """Estimate word timings by spreading [start, end] over the words by spoken weight."""
    tokens = tokenize(text)
    weights = [1.6 if t == " " else _weight(t) for t in tokens]  # a space is a short pause
    total = sum(weights) or 1
    t, words = start, []
    for tok, w in zip(tokens, weights):
        dur = (end - start) * w / total
        if tok == " ":
            if words:
                words[-1].space_after = True
        else:
            words.append(Word(tok, t, t + dur))
        t += dur
    return words


def words_from_boundaries(text: str, bounds: list[tuple[float, float, str]], offset: float) -> list[Word] | None:
    """Use edge-tts WordBoundary events if their words spell out the text; otherwise None."""
    if not bounds:
        return None
    squash = lambda s: re.sub(r"[\s.,!?…]", "", s)  # noqa: E731
    if squash("".join(b[2] for b in bounds)) != squash(text):
        return None
    words, pos = [], 0
    for start, dur, wtext in bounds:
        pos = text.find(wtext, pos)
        if pos < 0:
            return None
        pos += len(wtext)
        space = pos < len(text) and text[pos] == " "
        words.append(Word(wtext, offset + start, offset + start + dur, space))
    for a, b in zip(words, words[1:]):  # close tiny gaps so the highlight never blinks off mid-phrase
        if b.start - a.end < 0.25:
            a.end = b.start
    return words


def chunk(words: list[Word], max_len: int = 13, max_words: int = 4) -> list[list[Word]]:
    """Group words into one-row caption chunks; prefer breaking where the speaker pauses."""
    chunks, cur = [], []
    for w in words:
        cur_len = sum(visible_len(x.text) for x in cur)
        too_long = cur and cur_len + visible_len(w.text) > max_len
        pause_break = cur and cur[-1].space_after and cur_len >= 6
        if too_long or pause_break or len(cur) >= max_words:
            chunks.append(cur)
            cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    return chunks


def ass_time(t: float) -> str:
    t = max(t, 0)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _style(name, size, primary, outline_col, back, border_style, outline, shadow, align, margin_v, margin_lr=110):
    return (f"Style: {name},{config.FONT},{size},{primary},{primary},{outline_col},{back},-1,0,0,0,100,100,0,0,"
            f"{border_style},{outline},{shadow},{align},{margin_lr},{margin_lr},{margin_v},1")


def header(w: int, h: int, styles: list[str]) -> str:
    return ("[Script Info]\nScriptType: v4.00+\n"
            f"PlayResX: {w}\nPlayResY: {h}\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n" + "\n".join(styles) +
            "\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")


def _escape(s: str) -> str:
    return s.replace("\\", "").replace("{", "(").replace("}", ")")


def _render_chunk(ch: list[Word], active: int, keywords: list[str], active_colour: str, base_colour: str) -> str:
    parts = []
    for i, w in enumerate(ch):
        text = _escape(w.text)
        if i == active:
            parts.append(f"{{\\c{active_colour}}}{text}{{\\c{base_colour}}}")
        elif any(k and k in w.text for k in keywords):
            parts.append(f"{{\\c{KEYWORD}}}{text}{{\\c{base_colour}}}")
        else:
            parts.append(text)
        if w.space_after and i < len(ch) - 1:
            parts.append(" ")
    return "".join(parts)


def video_ass(title: str, lines_words: list[list[Word]], line_ends: list[float], keywords: list[str],
              total: float, theme: str = "shopee") -> str:
    """Title box at the top for the whole clip; word-synced captions lower-middle; last line styled as CTA."""
    th = THEMES.get(theme, THEMES["shopee"])
    title_rows = [r.strip() for r in title.replace("\\n", "\n").split("\n") if r.strip()][:2]
    ass = header(1080, 1920, [
        _style("Title", 80, th["title_text"], th["title_box"], th["title_box"], 3, 18, 0, 8, 215),
        _style("Cap", 104, WHITE, BLACK, SHADOW, 1, 8, 3, 2, 410),
        _style("CTA", 92, th["cta_text"], th["cta_box"], th["cta_box"], 3, 16, 0, 2, 430),
    ])
    if title_rows:
        rows = "\\N".join(_escape(r) for r in title_rows)
        ass += f"Dialogue: 1,{ass_time(0)},{ass_time(total)},Title,,0,0,0,,{{\\fad(150,0)}}{rows}\n"
    last = len(lines_words) - 1
    for li, (words, line_end) in enumerate(zip(lines_words, line_ends)):
        chunks = chunk(words)
        is_cta = li == last
        style = "CTA" if is_cta else "Cap"
        active_colour = th["cta_active"] if is_cta else th["active"]
        base_colour = th["cta_text"] if is_cta else WHITE
        for ci, ch in enumerate(chunks):
            next_start = chunks[ci + 1][0].start if ci + 1 < len(chunks) else line_end
            for wi, w in enumerate(ch):
                start = w.start
                end = ch[wi + 1].start if wi + 1 < len(ch) else next_start
                pop = "{\\fscx88\\fscy88\\t(0,100,\\fscx100\\fscy100)}" if wi == 0 else ""
                text = _render_chunk(ch, wi, keywords, active_colour, base_colour)
                ass += f"Dialogue: 0,{ass_time(start)},{ass_time(end)},{style},,0,0,0,,{pop}{text}\n"
    return ass


def image_ass(headline: str, theme: str = "shopee") -> str:
    th = THEMES.get(theme, THEMES["shopee"])
    rows = [r.strip() for r in headline.replace("\\n", "\n").split("\n") if r.strip()][:2]
    ass = header(1080, 1350, [_style("Head", 74, th["title_text"], th["title_box"], th["title_box"], 3, 18, 0, 8, 60, 80)])
    joined = "\\N".join(_escape(r) for r in rows)
    return ass + f"Dialogue: 0,0:00:00.00,0:00:05.00,Head,,0,0,0,,{joined}\n"
