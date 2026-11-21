import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import random  # noqa: E402
import tempfile  # noqa: E402

from affiliate import captions, config, content, learning, render, store, tracker  # noqa: E402

PRODUCT = {"id": "x", "name": "เครื่องฉีดน้ำ อันดับ1", "price": 2600, "url": "https://s.shopee.co.th/abc"}


def good_copy() -> dict:
    return {
        "angle": "problem_solution", "audience": "เจ้าของบ้านที่ล้างพื้นเอง", "fb_format": "video",
        "fb_format_reason": "ต้องเห็นแรงน้ำตอนฉีด", "voice": "male",
        "video": {"title": "ตะไคร่หน้าบ้าน\nขัดยังไงก็ไม่ออก", "lines": [
            {"say": "พื้นหน้าบ้านเขียวตะไคร่ทุกหน้าฝน ขัดเท่าไหร่ก็ไม่หมดสักที"},
            {"say": "ตัวนี้แรงดัน 120 บาร์ สายยาว 8 เมตร เดินฉีดได้ทั่วลานจอดรถ"},
            {"say": "คนรีวิวบอกว่าฉีดคราบที่พื้นออกง่าย เสียงไม่ดังมาก ใช้ตอนเช้าได้สบาย"},
            {"say": "ล้างรถเสร็จแล้วฉีดพื้นต่อได้เลย ไม่ต้องเปลี่ยนอุปกรณ์"},
            {"say": "วางพิกัดไว้ในตะกร้านะ เผื่อมีคนหาอยู่พอดี"},
        ]},
        "keywords": ["120 บาร์", "ออกง่าย"],
        "image_headline": "ตะไคร่หน้าบ้าน\nจบง่ายขึ้น",
        "shopee_caption": "ตะไคร่หน้าบ้านหายง่ายขึ้น",
        "fb_post": "หน้าฝนทีไรพื้นเขียวทุกที\nบ้านใครเจอบ้าง?",
        "fb_first_comment": "พิกัด {LINK} (ลิงก์ Affiliate)",
        "hashtags": ["#ล้างพื้น", "#ของใช้ในบ้าน", "#ป้ายยา", "#เครื่องฉีดน้ำ"],
        "facts_used": ["120 บาร์"],
    }


class QC(unittest.TestCase):
    def test_good_copy_passes(self):
        self.assertEqual(content.qc(PRODUCT, good_copy()), [])

    def test_first_hand_claim_fails(self):
        c = good_copy()
        c["fb_post"] = "ลองใช้มาสองอาทิตย์ ดีมาก"
        self.assertTrue(any("ลองใช้" in x for x in content.qc(PRODUCT, c)))

    def test_banned_word_in_product_name_is_allowed(self):
        c = good_copy()
        c["shopee_caption"] = "เครื่องฉีดน้ำ อันดับ1 ตัวนี้"
        self.assertEqual(content.qc(PRODUCT, c), [])

    def test_price_and_link_rules(self):
        c = good_copy()
        c["video"]["lines"][1]["say"] = "ราคาแค่ 999 บาท"
        c["fb_post"] = "ดูที่ https://shopee.co.th/x"
        c["fb_first_comment"] = "พิกัดในโปรไฟล์"
        problems = " ".join(content.qc(PRODUCT, c))
        for needle in ("999", "fb_post ห้ามมีลิงก์", "{LINK}", "Affiliate"):
            self.assertIn(needle, problems)


class Parsing(unittest.TestCase):
    def test_inbox_block(self):
        raw = store.parse_block("ชื่อ: A\nลิงก์: https://s.shopee.co.th/Q1w2\nราคา: 1,290\n"
                                "ค่าคอมพิเศษ: 10%\nขายแล้ว: 2.3พัน\nจุดเด่น:\n- กันน้ำ\n- เบา\nรูป:\nhttp://a/1.jpg")
        self.assertEqual(raw["price"], 1290)
        self.assertEqual(raw["extra_rate"], 10)
        self.assertEqual(raw["sold"], 2300)
        self.assertEqual(raw["features"], ["กันน้ำ", "เบา"])
        self.assertEqual(raw["images"], ["http://a/1.jpg"])
        self.assertEqual(store.product_id(raw["url"]), "Q1w2")

    def test_full_size_image_url(self):
        self.assertEqual(store.full_size_url("https://down-th.img.susercontent.com/file/abc_tn"),
                         "https://down-th.img.susercontent.com/file/abc")
        self.assertEqual(store.full_size_url("https://x/file/abc_tn?x=1"), "https://x/file/abc?x=1")
        self.assertEqual(store.full_size_url("https://x/file/abc_tnx"), "https://x/file/abc_tnx")

    def test_status_uses_baht_per_order(self):
        cheap = {"id": "zz_none", "price": 10, "extra_rate": 8, "features": ["x"]}
        self.assertEqual(store.status_of(cheap), "skip")              # ~1 baht per order
        shoe = {"id": "zz_none", "price": 3300, "extra_rate": 5, "features": ["x"]}
        self.assertAlmostEqual(store.commission_per_order(shoe), 231)  # 66 base + 165 extra
        self.assertEqual(store.status_of(shoe), "needs_info")         # worth it; only photos missing
        big = {"price": 20000, "extra_rate": 0}
        self.assertEqual(store.commission_per_order(big), 225)        # base capped


class Captions(unittest.TestCase):
    def test_thai_words_and_numbers(self):
        toks = captions.tokenize("คนรีวิวบอกว่าฉีดคราบออกง่าย แรงดัน 120 บาร์ๆ")
        self.assertIn("บอก", toks)
        self.assertIn(" ", toks)
        self.assertTrue(any(t.endswith("ๆ") for t in toks))  # mai yamok stays on its word

    def test_timings_fill_the_line_in_order(self):
        words = captions.time_words("ตัวนี้แรงดัน 120 บาร์ สายยาว 8 เมตร", 1.0, 4.0)
        self.assertAlmostEqual(words[0].start, 1.0)
        self.assertAlmostEqual(words[-1].end, 4.0, places=5)
        self.assertTrue(all(a.end <= b.start + 1e-9 for a, b in zip(words, words[1:])))

    def test_chunks_fit_one_row(self):
        words = captions.time_words("คนรีวิวบอกว่าฉีดคราบที่พื้นออกง่ายมาก แถมเสียงก็ไม่ดังเลย", 0, 5)
        for ch in captions.chunk(words):
            self.assertLessEqual(sum(captions.visible_len(w.text) for w in ch), 13 + 6)
            self.assertLessEqual(len(ch), 4)

    def test_boundaries_used_when_they_match(self):
        b = [(0.1, 0.3, "ตัว"), (0.4, 0.3, "นี้"), (0.9, 0.5, "ดี")]
        w = captions.words_from_boundaries("ตัวนี้ ดี", b, 2.0)
        self.assertEqual([x.text for x in w], ["ตัว", "นี้", "ดี"])
        self.assertTrue(w[1].space_after)
        self.assertAlmostEqual(w[0].start, 2.1)
        self.assertIsNone(captions.words_from_boundaries("อย่างอื่น", b, 0))

    def test_ass_highlights_each_word(self):
        words = captions.time_words("ตัวนี้ดีมาก", 0, 2)
        ass = captions.video_ass("หัวข้อ", [words], [2.5], [], 2.5)
        self.assertEqual(sum(l.startswith("Style:") for l in ass.splitlines()), 3)
        self.assertEqual(ass.count(",Cap,") + ass.count(",CTA,"), len(words))
        self.assertIn(captions.ORANGE, ass)


class Learning(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = (config.TRACKER, learning.DIR, learning.WEIGHTS, learning.INSIGHTS, learning.LESSONS)
        d = Path(self.tmp.name)
        config.TRACKER = d / "posts.csv"
        learning.DIR, learning.WEIGHTS, learning.INSIGHTS, learning.LESSONS = d, d / "w.json", d / "i.md", d / "l.jsonl"

    def tearDown(self):
        config.TRACKER, learning.DIR, learning.WEIGHTS, learning.INSIGHTS, learning.LESSONS = self.old
        self.tmp.cleanup()

    def test_learns_which_style_earns_more(self):
        rows = []
        for i in range(4):
            rows.append({"date": "2026-11-21", "link_id": f"a{i}", "platform": "shopee_video", "utm_content": "value_deal",
                         "utm_campaign": "quickcut|mint|th-TH-NiwatNeural", "clicks": "20", "commission_net": "60"})
            rows.append({"date": "2026-11-21", "link_id": f"b{i}", "platform": "shopee_video", "utm_content": "style_pick",
                         "utm_campaign": "framed|shopee|th-TH-NiwatNeural", "clicks": "5", "commission_net": "0"})
        tracker.write(rows)
        w = learning.learn()
        styles = w["dimensions"]["style"]
        self.assertEqual(next(iter(styles)), "quickcut")
        self.assertTrue(styles["quickcut"]["proven"])
        picks = [learning.choose("style", render.STYLES, random.Random(s), w) for s in range(200)]
        self.assertGreater(picks.count("quickcut"), 120)       # mostly the winner
        self.assertGreater(len(set(picks)), 1)                 # but still exploring

    def test_untried_options_get_tried_first(self):
        self.assertIn(learning.choose("theme", list(captions.THEMES), random.Random(1), {"dimensions": {}}),
                      captions.THEMES)

    def test_lesson_is_appended(self):
        learning.add_lesson("เว้นช่วงเงียบน้อยลง", "video", "out/x/video.mp4", "owner")
        self.assertIn("เว้นช่วงเงียบ", learning.LESSONS.read_text(encoding="utf-8"))


class Voice(unittest.TestCase):
    def test_particles_follow_the_voice(self):
        self.assertEqual(render.adapt_particles("ใส่สบายมากนะคะ", "male"), "ใส่สบายมากนะครับ")
        self.assertEqual(render.adapt_particles("กดตะกร้าได้เลยค่ะ", "male"), "กดตะกร้าได้เลยครับ")
        self.assertEqual(render.adapt_particles("ดีมากครับ", "female"), "ดีมากค่ะ")
        self.assertEqual(render.adapt_particles("คะแนนรีวิวดี", "male"), "คะแนนรีวิวดี")  # not an ending

    def test_short_script_fails_qc(self):
        c = good_copy()
        c["video"]["lines"] = c["video"]["lines"][:4]
        for line in c["video"]["lines"]:
            line["say"] = line["say"][:20]
        self.assertTrue(any("บทพูดรวม" in x for x in content.qc(PRODUCT, c)))


class GeminiVoice(unittest.TestCase):
    """Gemini TTS is tried first; when its quota runs out the whole run moves to the next voice."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.work = Path(self.tmp.name)
        self.saved = (render._tts_gemini, render._tts)
        render._DEAD_ENGINES.clear()

    def tearDown(self):
        render._tts_gemini, render._tts = self.saved
        render._DEAD_ENGINES.clear()
        self.tmp.cleanup()

    def test_gemini_voice_used_and_trimmed(self):
        import math
        import struct

        def fake(text, name, out):  # 0.3 s silence + 1 s tone + 0.5 s silence at 24 kHz
            tone = [int(8000 * math.sin(2 * math.pi * 300 * n / 24000)) for n in range(24000)]
            out.write_bytes(struct.pack(f"<{7200 + 24000 + 12000}h", *([0] * 7200 + tone + [0] * 12000)))
            return 24000
        render._tts_gemini = fake
        durs, _, voice = render.synthesize([{"say": "ทดสอบ"}, {"say": "อีกบรรทัด"}], "female", self.work)
        self.assertEqual(voice, "gemini:Kore")
        self.assertTrue(all(0.9 < d < 1.2 for d in durs), durs)  # silence cut off

    def test_quota_moves_on_and_remembers(self):
        def quota(*_):
            raise render.QuotaExhausted("429")

        async def edge_down(*_):
            raise RuntimeError("offline")
        render._tts_gemini, render._tts = quota, edge_down
        render.time.sleep, saved_sleep = (lambda s: None), render.time.sleep
        try:
            self.assertIsNone(render.synthesize([{"say": "ทดสอบ"}], "male", self.work)[2])
        finally:
            render.time.sleep = saved_sleep
        self.assertIn("gemini", render._DEAD_ENGINES)


class ShotPlan(unittest.TestCase):
    def test_broll_only_between_real_photos(self):
        shots = render._shot_plan([2, 2, 2, 2], "framed", 3, 1, random.Random(0))
        self.assertEqual(shots[0][0], "photo")
        self.assertEqual(shots[-1][0], "photo")
        self.assertIn("clip", [s[0] for s in shots])

    def test_quickcut_doubles_the_shots(self):
        self.assertEqual(len(render._shot_plan([2, 2, 2], "quickcut", 3, 0, random.Random(0))), 6)
        self.assertAlmostEqual(sum(s[2] for s in render._shot_plan([2, 2, 2], "quickcut", 3, 0, random.Random(0))), 6)


if __name__ == "__main__":
    unittest.main()
