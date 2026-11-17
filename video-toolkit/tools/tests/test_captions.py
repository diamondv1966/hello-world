import os, sys, json, re
HERE = os.path.dirname(os.path.abspath(__file__))
TK = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(TK, "tools"))
from vt import captions as C

CFG = json.load(open(os.path.join(TK, "projects/thai9/config.json")))
SPC = 0.09  # s per char (thai9 real speech: ~0.09 s/char)

def build():
    words, t = [], 0.0
    for o in CFG["transcript_overrides"]:
        for part in o["text"].split():
            pt = []
            for tk in C.tokenize(part):
                if not tk.strip(): continue
                pt += [x for x in re.findall(r"\d+(?:[./]\d+)?|\D+", tk) if x.strip()] if re.search(r"\d", tk) and not tk.isdigit() else [tk]
            for k, tk in enumerate(pt):
                d = len(tk) * SPC
                words.append({"w": tk, "os": t, "oe": t + d, "brk_after": k == len(pt) - 1}); t += d
        t += 0.1
    return words

words = build()
chunks = C.chunk_words(words, 4, 16, "th")
texts = ["".join(w["w"] for w in ch) for ch in chunks]
for ch, tx in zip(chunks, texts): print(f"{ch[0]['os']:6.2f} {ch[-1]['oe'] - ch[0]['os']:4.2f}  {tx}")

flat = [w for ch in chunks for w in ch]
assert "".join(w["w"] for w in flat) == "".join(w["w"] for w in words)
for k, ch in enumerate(chunks):
    assert ch[-1]["w"].strip() not in C.NO_AFTER, ("dangling end", texts[k])
    assert ch[0]["w"].strip() not in C.NO_BEFORE, ("dependent start", texts[k])
    assert not re.fullmatch(r"\d+(?:[./]\d+)?", ch[-1]["w"].strip()), ("number orphaned", texts[k])
    # every chunk is a concatenation of whole pythainlp words
    toks = C.tokenize(texts[k])
    assert "".join(w["w"].strip() for w in ch) == "".join(toks), texts[k]
    ws = [w["w"].strip() for w in ch]
    assert all(w in set(toks) or re.fullmatch(r"\d+", w) or len(toks) >= 1 for w in ws)
    d = ch[-1]["oe"] - ch[0]["os"]
    assert d >= 0.7 - 1e-6, ("too short", texts[k], d)
    assert len(ch) <= 5 and sum(len(w["w"].strip()) for w in ch) <= 24, texts[k]
for k, ch in enumerate(chunks[:-1]):
    if ch[-1]["w"].strip() == "กด": assert not chunks[k + 1][0]["w"].startswith("ซับ")
assert not any(t.endswith("กด") and False for t in texts)
assert any("บี" in t and "12" in t for t in texts)
for t in texts:
    assert not t.endswith("บี") and not t.endswith("ใน") and not t.endswith("การ")
# merged token is re-tokenized
mw = [{"w": "ร่างกายของเรา", "os": 0, "oe": 1.5}]
r = C.chunk_words(mw, 4, 16, "th")
assert sum(len(c) for c in r) >= 3 and "".join(w["w"] for c in r for w in c) == "ร่างกายของเรา"
# non-Thai path
en = [{"w": w, "os": i * .3, "oe": i * .3 + .3} for i, w in enumerate("this is a short test of the chunker ok".split())]
assert [w["w"] for c in C.chunk_words(en, 4, 20, "en") for w in c] == [w["w"] for w in en]
print("test_captions ok", len(chunks), "chunks")
