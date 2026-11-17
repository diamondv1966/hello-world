"""Caption chunking (Thai-aware, phrase-aware) + fixed-height label line rendering for cards."""
import functools, math, re

FINAL_PART = ("ค่ะ", "คะ", "ครับ", "นะคะ", "นะครับ")
NO_AFTER = {"กด", "ใน", "การ", "ของ", "ที่", "และ", "กับ", "ว่า", "เป็น", "มี", "ให้", "จะ", "ได้", "ไม่", "ความ", "อย่าง", "ขาด", "เสี่ยง"}
NO_BEFORE = set(FINAL_PART) | {"นะ", "ๆ", "ด้วย", "เลย"}
VITAMIN = {"บี", "ซี", "ดี", "เอ", "เค", "B", "C", "D", "A", "K"}
MIN_DUR = 0.7
_NUM = re.compile(r"\d+(?:[./]\d+)?")


def _t(w): return w["w"].strip()
def _isnum(w): return bool(_NUM.fullmatch(_t(w)))


EXTRA_WORDS = ("ซับสไครบ์", "สไครบ์", "ไลก์", "แชร์", "นะคะ", "นะครับ", "แมกนีเซียม", "ออกซิเจน", "วิตามิน", "คอมเมนต์", "ธาตุเหล็ก", "แสดงว่า")


EXCLUDE_WORDS = ("โรคความดันโลหิตสูง",)  # long compounds that would hide breakable phrase boundaries


@functools.lru_cache(None)
def _trie():
    from pythainlp.util import Trie
    from pythainlp.corpus import thai_words
    return Trie((set(thai_words()) | set(EXTRA_WORDS)) - set(EXCLUDE_WORDS))


def _raw(s):
    from pythainlp.tokenize import word_tokenize
    return [x for x in word_tokenize(s, engine="newmm", custom_dict=_trie(), keep_whitespace=True) if x != ""]


def tokenize(s):
    """PyThaiNLP newmm words (default dictionary + protected loan words); sentence-final
    particles glued to the following word by the greedy matcher ("คะใน") are split off."""
    out = []
    for t in _raw(s):
        for p_ in ("ค่ะ", "คะ", "ครับ"):
            if t.startswith(p_) and len(t) > len(p_):
                out.append(p_); out += _raw(t[len(p_):]); break
        else: out.append(t)
    k = 0; res = []
    while k < len(out):  # "นะ" + particle -> one token
        if out[k] == "นะ" and k + 1 < len(out) and out[k + 1] in ("คะ", "ครับ"): res.append("นะ" + out[k + 1]); k += 2
        else: res.append(out[k]); k += 1
    return tuple(res)


_newmm = functools.lru_cache(None)(tokenize)


def _retokenize(words):
    """Split merged Thai tokens into PyThaiNLP words (time spread by char length)."""
    out = []
    for w in words:
        s = w["w"]; core = s.strip()
        parts = [p for p in _newmm(core) if p.strip()] if re.search(r"[฀-๿]", core) else [core]
        if len(parts) <= 1:
            out.append(dict(w)); continue
        tail = s[len(s.rstrip()):]; tot = sum(len(p) for p in parts); cum = 0
        for k, p in enumerate(parts):
            d = dict(w); d["w"] = p + (tail if k == len(parts) - 1 else "")
            for a, b in (("s", "e"), ("os", "oe")):
                if a in w and b in w:
                    d[a] = w[a] + (w[b] - w[a]) * cum / tot; d[b] = w[a] + (w[b] - w[a]) * (cum + len(p)) / tot
            if k < len(parts) - 1: d["brk_after"] = False
            cum += len(p); out.append(d)
    return out


def _flag(w): return bool(w.get("brk_after")) or _t(w) in FINAL_PART


def _no_break_between(a, b, nxt=None):
    ta, tb = _t(a), _t(b)
    if ta in NO_AFTER or tb in NO_BEFORE: return True
    if tb == "แล้ว" and nxt is not None and _t(nxt) in FINAL_PART: return True
    if _isnum(a): return True                     # "4 ผมร่วง": number stays with its item
    if _isnum(b) and ta in VITAMIN: return True   # "บี 12"
    return False


def chunk_words(words, max_words, max_chars, lang="th"):
    """words: dicts {w, os, oe, [brk_after]}; returns list of chunks (lists of word dicts).
    Boundaries fall only between (PyThaiNLP) words; phrase flags preferred; function words never dangle."""
    if lang == "th": words = _retokenize(words)
    else: words = [dict(w) for w in words]
    if not words: return []
    # hard groups: long pause or sentence punctuation
    groups, cur = [], []
    for k, w in enumerate(words):
        if cur and w["os"] - cur[-1]["oe"] > 0.6: groups.append(cur); cur = []
        cur.append(w)
        t = _t(w)
        if t[-1:] in ".!?" and not t[:-1].isdigit(): groups.append(cur); cur = []
    if cur: groups.append(cur)
    out = []
    for g in groups: out += _partition(g, max_words, max_chars)
    return out


def _partition(g, max_words, max_chars):
    n = len(g); INF = float("inf")
    clen = [0]
    for w in g: clen.append(clen[-1] + len(_t(w)))

    def cost(i, j):
        nw, chars = j - i, clen[j] - clen[i]
        if nw > 1 and (nw > max_words + 3 or chars > max_chars + 10): return INF
        end = j == n or _flag(g[j - 1])
        c = 1.5
        ow, oc = max(0, nw - max_words), max(0, chars - max_chars)
        if ow or oc: c += (2 * ow + 0.6 * oc) * (1 if end else 2)
        if nw < 2 and chars < 6: c += 4
        if nw > 2 and _isnum(g[j - 2]) and _t(g[j - 1]) in FINAL_PART: c += 5  # list marker "9 ค่ะ" leads the next chunk
        dur = g[j - 1]["oe"] - g[i]["os"]
        if dur < MIN_DUR: c += 12 + 20 * (MIN_DUR - dur)
        if j < n:
            if _no_break_between(g[j - 1], g[j], g[j + 1] if j + 1 < n else None): c += 100
            elif not end: c += 6
        c += 0.05 * max(0, max_chars - chars)
        return c

    dp = [INF] * (n + 1); bk = [0] * (n + 1); dp[0] = 0
    for j in range(1, n + 1):
        for i in range(max(0, j - max_words - 3), j):
            if dp[i] == INF: continue
            v = dp[i] + cost(i, j)
            if v < dp[j]: dp[j], bk[j] = v, i
    res, j = [], n
    while j > 0: res.append(g[bk[j]:j]); j = bk[j]
    return res[::-1]


# ---------------------------------------------------------------- card labels (fixed line boxes)
def line_box_h(font, pad=None):
    asc, desc = font.getmetrics(); pad = math.ceil(font.size * 0.35) if pad is None else pad
    return asc + desc + 2 * pad


def label_line(font, text, color, min_w=0):
    """RGBA image of FIXED height (ascent+descent+2*pad from font metrics), baseline at the same y
    for every text; only the width depends on the text (centre horizontally when pasting).
    Returns (image, baseline_y)."""
    from PIL import Image, ImageDraw
    asc, desc = font.getmetrics(); pad = math.ceil(font.size * 0.35)
    bb = font.getbbox(text, anchor="ls")
    x0 = pad - min(0, bb[0]); w = int(math.ceil(max(font.getlength(text), bb[2]))) + x0 + pad
    im = Image.new("RGBA", (max(w, min_w), asc + desc + 2 * pad))
    ImageDraw.Draw(im).text((x0, pad + asc), text, font=font, fill=color, anchor="ls")
    return im, pad + asc


def emoji_box(emoji_font, e, size):
    """Emoji scaled to fit size x size, pasted centred in a fixed size x size RGBA box."""
    from PIL import Image, ImageDraw
    g = Image.new("RGBA", (160, 140)); ImageDraw.Draw(g).text((0, 0), e, font=emoji_font, embedded_color=True)
    bb = g.getbbox()
    box = Image.new("RGBA", (size, size))
    if bb is None: return box
    g = g.crop(bb); s = size / max(g.size)
    g = g.resize((max(1, int(g.width * s)), max(1, int(g.height * s))), Image.LANCZOS)
    box.alpha_composite(g, ((size - g.width) // 2, (size - g.height) // 2))
    return box
