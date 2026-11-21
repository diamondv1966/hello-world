import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from affiliate import content, render, store  # noqa: E402

PRODUCT = {"id": "x", "name": "เครื่องฉีดน้ำ อันดับ1", "price": 2600, "url": "https://s.shopee.co.th/abc"}


def good_copy() -> dict:
    return {
        "angle": "problem_solution", "voice": "male",
        "video": {"lines": [
            {"say": "พื้นหน้าบ้านเขียวตะไคร่ทุกหน้าฝน ขัดเท่าไหร่ก็ไม่หมด", "caption": "ตะไคร่หน้าบ้าน\nขัดไม่ออก"},
            {"say": "ตัวนี้แรงดันหนึ่งร้อยยี่สิบบาร์ สายยาวแปดเมตร", "caption": "แรงดัน 120 บาร์"},
            {"say": "คนรีวิวบอกว่าฉีดคราบที่พื้นออกง่าย เสียงไม่ดังมาก", "caption": "คนรีวิวบอกว่า\nคราบออกง่าย"},
            {"say": "วางพิกัดไว้ในตะกร้านะ เผื่อใครหาอยู่", "caption": "พิกัดในตะกร้า"},
        ]},
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

    def test_status(self):
        p = {"id": "zz_none", "extra_rate": 5, "features": ["x"]}
        self.assertEqual(store.status_of(p), "skip")
        p["extra_rate"] = 9
        self.assertEqual(store.status_of(p), "needs_info")  # no images yet


class ThaiWrap(unittest.TestCase):
    def test_never_starts_row_with_a_mark(self):
        text = "คนรีวิวบอกว่าฉีดคราบออกง่ายและเสียงไม่ดังมากเลยนะ"
        for row in render.wrap_thai(text, 12)[1:]:
            self.assertNotIn(row[0], render.THAI_NO_BREAK_BEFORE)

    def test_explicit_rows_kept(self):
        self.assertEqual(render.wrap_thai("แถวหนึ่ง\\nแถวสอง"), ["แถวหนึ่ง", "แถวสอง"])


if __name__ == "__main__":
    unittest.main()
