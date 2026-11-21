import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from affiliate import captions, content, store  # noqa: E402

PRODUCT = {"id": "x", "name": "เครื่องฉีดน้ำ อันดับ1", "price": 2600, "url": "https://s.shopee.co.th/abc"}


def good_copy() -> dict:
    return {
        "angle": "problem_solution", "audience": "เจ้าของบ้านที่ล้างพื้นเอง", "fb_format": "video",
        "fb_format_reason": "ต้องเห็นแรงน้ำตอนฉีด", "voice": "male",
        "video": {"title": "ตะไคร่หน้าบ้าน\nขัดยังไงก็ไม่ออก", "lines": [
            {"say": "พื้นหน้าบ้านเขียวตะไคร่ทุกหน้าฝน ขัดเท่าไหร่ก็ไม่หมด"},
            {"say": "ตัวนี้แรงดัน 120 บาร์ สายยาว 8 เมตร"},
            {"say": "คนรีวิวบอกว่าฉีดคราบที่พื้นออกง่าย เสียงไม่ดังมาก"},
            {"say": "วางพิกัดไว้ในตะกร้านะ เผื่อใครหาอยู่"},
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


if __name__ == "__main__":
    unittest.main()
