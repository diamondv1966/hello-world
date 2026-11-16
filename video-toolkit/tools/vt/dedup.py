"""Thai retake detection + rough-cut planning (owner: 04-thai-dedup-cutter).

Pure functions, no network. See docs/INTERFACES.md.
"""
import difflib
import re

_PUNCT = re.compile(r"[\s\W_]+", re.UNICODE)
_PARTICLES = {"ค่ะ", "คะ", "ครับ", "นะคะ", "นะ", "จ้ะ", "จ้า", "ค่า", "นะครับ", "ข้อ", "อัน", "อย่าง"}
_THAI_NUM = {"หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า", "สิบ"}
_PRIORITY = {"retake": 3, "skip": 3, "head": 2, "tail": 2, "silence": 1}


def _norm(w):
    return _PUNCT.sub("", str(w).strip().lower())


def _tokens(seg, words, lang):
    toks = [_norm(w.get("w", "")) for w in words[seg.get("i0", 0):seg.get("i1", 0)]]
    toks = [t for t in toks if t]
    text = _PUNCT.sub("", seg.get("text", "")) if seg.get("text") else ""
    if lang == "th" and text and (not toks or (len(toks) < 3 and len(text) > 12)
                                  or max(len(t) for t in toks) > 14):
        try:
            from pythainlp.tokenize import word_tokenize
            toks = [t for t in (_norm(x) for x in word_tokenize(seg["text"], engine="newmm",
                                                                keep_whitespace=False)) if t]
        except Exception:
            pass
    return toks


def _is_number(t):
    return t.isdigit() or t in _THAI_NUM


def _weak_prefix(prefix):
    """True if the shared prefix is only numbers / list particles (e.g. '2 ค่ะ ข้อ')."""
    return all(_is_number(t) or t in _PARTICLES for t in prefix)


def _ratio(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def find_retakes(segments, words, lang="th", window=15.0, min_sim=0.72, prefix_n=3):
    toks = [_tokens(s, words, lang) for s in segments]
    spans = []
    for i, si in enumerate(segments):
        ti = toks[i]
        if len(ti) < 3:
            continue
        for j in range(i + 1, len(segments)):
            sj = segments[j]
            if sj["s"] > si["e"] + window:
                break
            tj = toks[j]
            if len(tj) < 3 or sj["s"] <= si["s"]:
                continue
            sim = max(_ratio(ti, tj), _ratio(ti, tj[:len(ti) + 1]))
            reason = None
            if sim >= min_sim:
                reason = f"พูดซ้ำ (คล้าย {round(sim * 100)}%): “{si.get('text', ''.join(ti))}”"
            elif (len(ti) >= prefix_n and len(ti) < len(tj) and ti[:prefix_n] == tj[:prefix_n]
                  and not _weak_prefix(ti[:prefix_n])):
                bi, bj = ti[prefix_n:], tj[prefix_n:]
                body = _ratio(bi, bj[:len(bi) + 1]) if bi else 1.0
                if body >= 0.5:
                    reason = f"ขึ้นต้นซ้ำ {prefix_n} คำ (false start): “{si.get('text', ''.join(ti))}”"
            if reason:
                spans.append({"a": float(si["s"]), "b": float(sj["s"]), "kind": "retake",
                              "reason": reason, "similarity": round(sim, 3)})
                break  # nearest later take; chains handled by merging
    # merge overlapping / touching spans (chain -> keep only the last take)
    spans.sort(key=lambda d: (d["a"], d["b"]))
    out = []
    for sp in spans:
        if out and sp["a"] <= out[-1]["b"] + 1e-6:
            m = out[-1]
            m["b"] = max(m["b"], sp["b"])
            m["similarity"] = max(m["similarity"], sp["similarity"])
            m["reason"] += " + " + sp["reason"]
        else:
            out.append(dict(sp))
    return out


def plan_cuts(duration, silences, retakes, skips, max_gap, pad, end_pad):
    cuts = []
    for a, b in silences or []:
        if a <= 0.05:
            cuts.append((0.0, max(0.0, b - pad), "head", "เงียบช่วงต้นคลิป"))
        elif b >= duration - 0.05:
            cuts.append((min(duration, a + end_pad), duration, "tail", "เงียบท้ายคลิป"))
        elif b - a >= max_gap:
            cuts.append((a + pad, b - pad, "silence", f"ช่วงเงียบ {b - a:.2f} วิ"))
    for r in retakes or []:
        cuts.append((r["a"], r["b"], "retake", r.get("reason", "พูดซ้ำ")))
    for a, b in skips or []:
        cuts.append((a, b, "skip", "ตัดตาม config (คำผิด/ไม่จำเป็น)"))
    cuts = [(max(0.0, a), min(duration, b), k, r) for a, b, k, r in cuts]
    cuts = sorted(c for c in cuts if c[1] - c[0] > 0.02)
    merged = []
    for a, b, k, r in cuts:
        if merged and a <= merged[-1]["b"] + 0.02:
            m = merged[-1]
            m["b"] = max(m["b"], b)
            if _PRIORITY[k] > _PRIORITY[m["kind"]]:
                m["kind"] = k
            m["reason"] += " + " + r
        else:
            merged.append({"a": a, "b": b, "kind": k, "reason": r})
    keeps, t = [], 0.0
    for c in merged:
        if c["a"] - t > 0.08:
            keeps.append([t, c["a"]])
        t = max(t, c["b"])
    if duration - t > 0.08:
        keeps.append([t, duration])
    return merged, keeps
