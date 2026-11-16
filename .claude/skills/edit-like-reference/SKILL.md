---
name: edit-like-reference
description: One-drop professional edit — when the user drops a clip and names a reference (a reference video file, a creator style like Hormozi/Ali Abdaal/Codie Sanchez, a preset name, or a description), analyze the reference style, auto-edit the clip (cuts, retakes, face-aware zoom, word-by-word Thai/English captions, cards, SFX, original music, -14 LUFS) and add Claude's creative pass (hook, emphasis, cards, CTA, transcript fixes) before delivering a ready-to-post MP4. Use whenever a clip arrives with "ตัดให้เหมือน/สไตล์/เรฟ/ref/แบบนี้".
---
# ตัดคลิปตามเรฟ (หย่อนคลิป + บอกเรฟ → ได้คลิปมืออาชีพ)

## 1. รับงาน (บอกผู้ใช้ทุกครั้ง)
- คลิป: path ไฟล์ล่าสุดที่แนบ · เรฟ: ไฟล์วิดีโอ / ชื่อสไตล์ / ชื่อ preset / คำบรรยาย
- เรฟเป็น **ลิงก์** (TikTok/YouTube) → เครื่องคลาวด์ดาวน์โหลดไม่ได้: ขอไฟล์ หรือเดาสไตล์จากชื่อครีเอเตอร์ แล้วบอกผู้ใช้
- ไม่ระบุเรฟ → **`thai-clear`** (ค่าเริ่มต้น) · preset ส่วนตัว: `user/<name>` (สร้างด้วย `tools/make_user_preset.py <ref.mp4> <name>`)
- คำบรรยายเรฟ → เลือก preset: ความรู้/สุขภาพ/พาสเทล=`clean-pastel` · ธุรกิจ/ปลุกใจ/เร็ว=`bold-hormozi` · สอน/เล่าเรื่องนุ่ม=`calm-abdaal` · การเงิน/ข้อคิดตัวหนาขาว=`codie-bold` · vlog/บิวตี้=`minimal-aesthetic`

## 2. Plan รอบแรก (อัตโนมัติ)
```bash
cd video-toolkit && ./check_system.sh | tail -2
tools/edit_like.sh <clip> <ref|preset|keyword> <name> th --plan-only
```
→ ยืนยัน **ชื่อไฟล์ + SHA-256** (ถ้าเตือนซ้ำ ให้แจ้ง), สร้าง words.json, plan.json, report.md, ref/style_report.md + ref_sheet.jpg

## 3. Creative pass — ตาม `presets/user_settings.json` → `automation_level`
- ระดับ 1: ข้ามขั้นนี้ render ทันที · **ระดับ 2 (ค่าเริ่มต้น)**: ทำขั้นนี้แล้ว render · ระดับ 3: ทำขั้นนี้ + ส่งแผน 12 หัวข้อให้ผู้ใช้อนุมัติก่อน render
1. อ่านคำพูดเต็ม: `python3 -c "import json;print(''.join(w['w'] for w in json.load(open('projects/<name>/words.json'))))"`
2. **แก้คำที่ถอดผิด** ใน words.json (แก้ `w` เท่านั้น ห้ามแตะเวลา) — ซับบนจอใช้ข้อความนี้ตรง ๆ
3. ดู `ref/ref_sheet.jpg` (ถ้ามีเรฟ) + `tools/contact_sheet.sh projects/<name>/src.mp4 projects/<name>/gest.jpg 2` → ฟอนต์/สีไฮไลต์/ตำแหน่งซับ/ลูกเล่นของเรฟ และท่าเด่นของคลิป
4. เขียน `projects/<name>/config.json`:
   - `hook.lines` 1–2 บรรทัด ≤14 ตัว/บรรทัด สร้าง open loop (ตัวเลข/คำเตือน/คำถาม)
   - `emphasis` 3–8 คำ **สะกดตรงกับ words.json** (คำตอบ/ตัวเลข/คำสำคัญ) → สีเน้น + เสียง + ซูม punch
   - `cards` สำหรับคำนามธรรม (≤1 ใบต่อ 8–10 วิ, `at` = คำที่พูด, ไม่ทับท่าเด่น) — items = [อีโมจิ, ป้าย]
   - `broll` ถ้าผู้ใช้แนบไฟล์ภาพ/คลิป (`mode` pip|full)
   - `cta` + `disclaimer` (สุขภาพ/การเงิน) · `skip` = ช่วงพูดผิด/ไม่จำเป็นที่ระบบไม่เจอ
   - override สไตล์ได้ เช่น `"captions": {"highlight": "#FFE600", "y": 1180}` ถ้าเรฟต่างจาก preset
5. Render: `python3 -I tools/auto_edit.py projects/<name> --preset <p> [--ref projects/<name>/ref/style_profile.json]`

## 4. QA ก่อนส่ง (บังคับ — Visual QA Protocol)
- เปิดด้วย Read: `projects/<name>/artifacts/qa/audio_diagnostics.png` (ไม่มีแถบแดงกลางคลิป) และ `contact_sheet.png` (กรอบแดง=หน้า น้ำเงิน=การ์ด เขียว=ซับ ไม่ทับกัน)
- manifest `qa.collision_count == 0` · ถ้า >0 หลังแก้ 1 รอบ → escalate 01-director-orchestrator (opus) / ให้ 02-visual-qa-critic ตรวจรับ
- ดู `qa.jpg` (+ ดึงเฟรมเพิ่มที่การ์ด/คำเน้น): ซับถูก/อ่านง่าย, ไม่บังหน้า, อยู่ใน safe zone (y≤1440, x≤930), การ์ดไม่ชนซับ
- `report.md`: ความยาว 35–55 วิ (เกิน → เพิ่ม `skip` ตัดช่วงรอง), LUFS ≈ -14, peak ≤ -1.4
- แก้ → render ซ้ำ (ข้อมูลวิเคราะห์ถูก cache ไว้ เร็ว)

## 5. ส่งมอบ
FINAL.mp4 · ปก (เฟรม hook) · captions.srt · cue_sheet.tsv · แคปชั่น + แฮชแท็ก 6–10 · สรุปสั้น: เรฟที่ใช้ (preset + ค่าที่วัดได้), จุดตัด, สิ่งที่ควรเช็ก
ตอบตามโครงสร้าง 12 หัวข้อ (skill video-clip-analysis) เมื่อผู้ใช้ขอแผนละเอียด

## ข้อจำกัดที่ต้องบอก
ถอดเสียงไทยด้วย Whisper small อาจผิดคำ (แก้ในขั้น 3.2) · OCR เรฟประมาณขนาดฟอนต์คร่าว ๆ (ยืนยันด้วยตาจาก ref_sheet) · ไม่มี B-roll stock ถ้าผู้ใช้ไม่แนบ (ใช้การ์ดวาดแทน) · ฟังเสียงเองไม่ได้ ให้ผู้ใช้ฟังรอบสุดท้าย
อ้างอิงงานวิจัย: `.claude/skills/trend-research/references/ai-video-editing-2026-11.md`
