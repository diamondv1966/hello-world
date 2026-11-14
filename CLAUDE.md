# AI Video Production Team — กติกาประจำ repo

repo นี้คือ **ระบบทีมตัดต่อคลิปสั้นแนวตั้ง (TikTok/Reels) ภาษาไทย** เครื่องมืออยู่ใน `video-toolkit/`, Skills ใน `.claude/skills/`, Agents ใน `.claude/agents/`

## ลำดับบังคับ
1. **เตรียมระบบก่อนเสมอ**: `cd video-toolkit && ./setup.sh && ./check_system.sh` → ต้องได้ "ระบบพร้อมใช้งานแล้ว" ก่อนแตะคลิป
2. **รับคลิปใหม่**: `tools/new_project.sh <clip> <name>` → ยืนยันชื่อไฟล์ + SHA-256 ให้ผู้ใช้เห็น; ถ้า registry เตือนว่าซ้ำ ให้แจ้งผู้ใช้ทันที
3. **ห้ามใช้ข้อมูล/ผลวิเคราะห์จากคลิปเก่า** เว้นแต่ผู้ใช้อนุญาต — วิเคราะห์ใหม่จากไฟล์ที่แนบในข้อความล่าสุดเท่านั้น
4. ตอบตามโครงสร้าง 12 หัวข้อ (skill `video-clip-analysis`) แล้วค่อย render เมื่อผู้ใช้สั่ง
5. ตอบเป็นภาษาไทย; ตรวจคุณภาพด้วยเฟรมจริง + ค่า LUFS ก่อนส่งงานเสมอ

## ⚡ โหมดหลัก: "หย่อนคลิป + บอกเรฟ"
เมื่อผู้ใช้แนบคลิปและบอกเรฟ (ไฟล์คลิปตัวอย่าง / ชื่อครีเอเตอร์ เช่น Hormozi, Ali Abdaal / ชื่อ preset / คำบรรยาย) → ใช้ skill **`edit-like-reference`** ทันที:
`tools/edit_like.sh <clip> <ref> <name> th --plan-only` → แก้ถอดเสียง + เขียน config.json (hook/emphasis/cards/cta) → `tools/auto_edit.py` → QA (qa.jpg, LUFS) → ส่ง FINAL.mp4
presets: clean-pastel (ค่าเริ่มต้น) · bold-hormozi · calm-abdaal · codie-bold · minimal-aesthetic (`video-toolkit/presets/`)

## มาตรฐาน
Hook ≤3 วิ · ตัดเงียบ >0.2–0.3 วิ · ยาว 35–55 วิ · สี ฟ้าอ่อน #7DD3FC → น้ำเงิน #1E46B8 → ชมพูอ่อน #F9A8D4 · ภาพประกอบ+อนิเมชันในจุดสำคัญ · -14 LUFS / TP ≤ -1.5 dBFS · safe zone TikTok: บน 130px, ล่าง 480px, ขวา 150px

## ทีม (agents) และสกิลหลัก
video-editor → video-clip-analysis · hook-script → onscreen-text-animation · visual-director / motion-designer → onscreen-text-animation, broll-image-research · sound-designer → sound-design · music-director → music-direction · broll-researcher → broll-image-research · capcut-ffmpeg → capcut-ffmpeg-workflow · research-trend → trend-research · skill-builder → ดูแล `.claude/skills/*` และ system-docs-pdf

## ข้อจำกัดเครื่องคลาวด์
Pexels/Pixabay/Mixkit/Freesound/HuggingFace ถูกบล็อก → ใช้ npm/PyPI, การ์ดภาพประกอบที่วาดเอง (`examples/9-signals/gfx.py`) หรือ B-roll ที่ผู้ใช้แนบ
