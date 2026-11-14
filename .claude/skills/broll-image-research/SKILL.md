---
name: broll-image-research
description: Plan B-roll and illustrative images for a vertical clip — where to insert, why it aids understanding, Thai + English search terms, stills vs short clips, visual style, placement that never covers the face or key gestures, and the fallback of drawn animated explainer cards when stock sites are blocked. Use when a plan or render needs supporting visuals.
---
# ภาพประกอบ / B-roll

## ขั้นตอน
1. ดู contact sheet (0.5 วิ/เฟรม) → จด **ท่าเด่น** (เวลา) = ห้ามมีภาพทับ
2. หาคำสำคัญใน transcript ("ขาด…", "เสี่ยง…", ชื่อสิ่งของ/สถานที่/อารมณ์) → จุดแทรก = **หลังท่าเด่น ตรงกับคำสำคัญ**, ยาว 0.8–2.5 วิ
3. ต่อจุด ให้: ภาพนิ่ง (ไทย/อังกฤษ) · คลิปสั้น (ไทย/อังกฤษ) · เหตุผลว่าช่วยเข้าใจอย่างไร (ทำนามธรรม→รูปธรรม, ให้คนดูนึกถึงตัวเอง, ทำตัวเลขให้จับต้องได้)
4. สไตล์เดียวทั้งคลิป: clean / minimal / soft pastel / cinematic / vibrant — คลิปความรู้สุขภาพ = soft pastel + clean, เลี่ยงภาพน่ากลัว

## รูปแบบวาง
- การ์ดมุมมน (r 36–40px) ขอบชมพู 6–8px + เงา navy 30% · กว้าง ~760px · **อยู่ในช่วง y 1000–1420** และ x 160–920 (เลี่ยงหน้า + UI TikTok)
- ถ้าหน้าผู้พูดลงต่ำ (โน้มตัว/ซูมแรง) → เลื่อน zoom anchor ขึ้น (เช่น 0.38→0.75) หรือย่อการ์ด
- In: slide จากขวา 120px + scale 92→100% (0.35 วิ, ease-out-back) · ระหว่างแสดง Ken Burns 100→102% · Out: fade + ลง 40px (0.2 วิ)
- ใช้ฟิลเตอร์เดียวกันกับทุก B-roll (Temp -3, Sat -5, Fade +5)

## แหล่งภาพ
- เว็บ (ให้ผู้ใช้ดาวน์โหลด): Pexels, Pixabay, Mixkit, Unsplash, CapCut Stock — เครื่องคลาวด์เข้าไม่ได้
- **Fallback อัตโนมัติ**: การ์ดอธิบายวาดเอง (`examples/9-signals/gfx.py`): ประเภทที่ทำได้ — อาหาร 4 อย่างเด้งทีละชิ้น (`food_body`), A→B ลูกศร (`body3/7`), กราฟเส้นวาด (`body6`), เกจ+ตัวนับ (`body9`), แก้วเติมน้ำ (`body1`), ฟอง/อนุภาคลอย (`body8`)
- อีโมจิ Noto Color Emoji (OFL) เป็นภาพประกอบในการ์ดได้; ตรวจว่าอีโมจิ render ได้ก่อน (บางตัวใหม่อาจไม่มี)
- ข้อมูลตัวเลขบนการ์ด (เช่น 140/90) ต้องเป็นความรู้ทั่วไปที่ตรวจสอบได้ และบอกผู้ใช้ให้ทวนก่อนโพสต์
