---
name: video-clip-analysis
description: Analyze a newly attached vertical talking-head clip (Thai TikTok/Reels) and produce the 12-section editing plan — intake with filename + SHA-256 confirmation, transcription, silence/cut list, structure, text, B-roll, graphics, SFX, music, color, CapCut steps, research notes. Use whenever the user attaches a video or asks to analyze/plan/edit a clip.
---
# วิเคราะห์คลิป + วางแผนตัดต่อ 12 หัวข้อ

## 0. Intake (บังคับ)
1. `cd video-toolkit && ./check_system.sh` (ถ้ามี ❌ → `./setup.sh`)
2. `tools/new_project.sh <path-ของไฟล์ที่แนบในข้อความล่าสุด> <ชื่อ>` → รายงาน **ชื่อไฟล์, SHA-256, ความยาว, ขนาด**
3. ถ้ามีคำเตือน "เหมือนกับที่เคยใช้แล้ว" → แจ้งผู้ใช้ชัด ๆ แต่ยังวิเคราะห์ใหม่จากไฟล์นี้ (ไม่ copy ผลเก่า)

## 1. เก็บข้อมูลจากไฟล์ (ทำใหม่ทุกครั้ง)
```bash
P=projects/<ชื่อ>
python3 -I tools/transcribe.py $P            # transcript.txt (ช่วงซ้อน 9 วิ / ก้าว 6.5 วิ)
tools/silences.sh $P/src.mp4 -33 0.2         # ช่วงเงียบ
tools/measure.sh  $P/src.mp4                 # LUFS, hiss, YAVG (ความสว่าง), SATAVG
tools/contact_sheet.sh $P/src.mp4 $P/gest.jpg 2   # ท่าทางทุก 0.5 วิ → หา "ท่าเด่น" ห้ามบัง
```
ถอดเสียงด้วย Whisper small อาจเพี้ยนคำเฉพาะ → เรียบเรียงตามบริบท และบอกผู้ใช้ให้เช็ก

## 2. กติกาการตัด
- ช่วงเงียบ ≥0.2 วิ → ตัดเหลือ ~0.1 วิ (เผื่อหายใจ); ช่วงต้นคลิปเงียบ → ตัดทิ้งให้ Hook เริ่มเฟรมแรก
- คำพูดผิด/ซ้ำ: เทียบ transcript ช่วงซ้อน ถ้าประโยคเดียวกันปรากฏ 2 รอบในเวลาต่างกัน = พูดซ้ำ → เก็บรอบที่ชัดกว่า
- ตัดกลางประโยค → ซูมเพิ่ม +6% ซ่อน jump cut
- เป้าหมาย 35–55 วิ; ถ้าเกิน เสนอเวอร์ชันสั้น (ตัดช่วงเกริ่น/ส่วนรอง)

## 3. โครงสร้างคำตอบ (ต้องครบ)
1 สรุปคลิป (เนื้อหา อารมณ์ กลุ่มเป้าหมาย จุดเด่น/อ่อน + ค่าที่วัดได้) · 2 ถอดเสียง + timestamp · 3 ตารางจุดตัด + เหตุผล · 4 โครงสร้าง Hook→เนื้อหา→CTA + กล้อง (ช่วงละ zoom start→end) · 5 ข้อความ + อนิเมชัน (skill onscreen-text-animation) · 6 B-roll + คำค้นไทย/อังกฤษ (skill broll-image-research) · 7 กราฟิก/อนิเมชันเพิ่มเติม (เวลาเข้า-ออก) · 8 SFX + dB (skill sound-design) · 9 เพลง (skill music-direction) · 10 สี (ค่าตัวเลข CapCut) · 11 CapCut ทีละขั้น (skill capcut-ffmpeg-workflow) · 12 ข้อเสนอจากการค้นคว้า (skill trend-research)

เวลาในหัวข้อ 2–3 = เวลาต้นฉบับ; หัวข้อ 4–11 = เวลาหลังตัด (บอกให้ชัด)

## 4. Render (เมื่อผู้ใช้สั่ง)
เขียน `$P/timeline.py` ตามแม่แบบ `examples/9-signals/timeline.py` (G = กลุ่ม/ช่วงตัด/zoom, ITEMS, CARDS) → `tools/render_example.sh $P`
QA ก่อนส่ง: ดึงเฟรมกลางทุกการ์ด → ตรวจว่าไม่บังหน้า/ท่าเด่น/safe zone; `tools/measure.sh $P/FINAL.mp4` ต้อง -14 LUFS, peak ≤ -1.4
