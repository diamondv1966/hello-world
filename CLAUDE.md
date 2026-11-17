# Automated Thai Video Production System — กติกาประจำ repo

ระบบตัดต่อคลิปสั้นแนวตั้ง (TikTok/Reels) ภาษาไทยอัตโนมัติ · เครื่องมือ `video-toolkit/` · Agents `.claude/agents/` · Skills `.claude/skills/`
เอกสารหลัก: `video-toolkit/docs/KNOWLEDGE_BASE.md` · สัญญาโมดูล `video-toolkit/docs/INTERFACES.md` · สคีมากลาง `video-toolkit/docs/schemas/pipeline_manifest.schema.json`

**อ่านก่อนแก้โค้ด/เขียน config/ส่งงาน:** skill `01-video-d-skill-playbook` (กฎ ❌/✅ จากความล้มเหลวจริง + checklist ก่อนส่ง)

## 1. ลำดับบังคับ (ทุกงาน)
1. เตรียมระบบ: `cd video-toolkit && ./setup.sh && ./check_system.sh` → ต้องได้ "ระบบพร้อมใช้งานแล้ว"
2. รับคลิป: `tools/new_project.sh <clip> <name>` → แจ้ง **ชื่อไฟล์ + SHA-256**; registry เตือนซ้ำ → แจ้งผู้ใช้ทันที
3. ห้ามใช้ผลวิเคราะห์ของคลิปเก่า เว้นแต่ผู้ใช้อนุญาต (คลิป "9 สัญญาณ" SHA `bf61fbfd…` = อนุญาตเป็นคลิปทดสอบภาษาไทย)
4. ตอบภาษาไทย · QA ด้วยภาพจริงทุกครั้ง (หัวข้อ 5) ก่อนส่งงาน

## 2. ระดับความอัตโนมัติ (`video-toolkit/presets/user_settings.json` → `automation_level`)
| ระดับ | ชื่อ | พฤติกรรม |
|---|---|---|
| 1 | auto | ระบบทำเองทั้งหมด ส่ง FINAL ทันที |
| **2** | **creative-assisted (ค่าเริ่มต้น)** | Claude แก้คำถอดผิด (words) + hook + คำเน้น + การ์ด + CTA ใน `config.json` แล้ว render |
| 3 | plan-approval | ส่งแผน 12 หัวข้อ + plan ให้ผู้ใช้อนุมัติก่อน render |

## 3. โหมดหลัก: "หย่อนคลิป + บอกเรฟ" (skill `edit-like-reference`)
`tools/edit_like.sh <clip> <ref|preset|keyword> <name> th --plan-only` → creative pass (ระดับ 2) → `python3 -I tools/auto_edit.py projects/<name> --preset <p>` → QA → ส่งมอบ
- preset ค่าเริ่มต้น **`thai-clear`** (กระชับ อ่านง่ายสำหรับคนไทย) · อื่น ๆ: clean-pastel, bold-hormozi, calm-abdaal, codie-bold, minimal-aesthetic
- preset ส่วนตัวจากคลิปเรฟ → `presets/user/` (analyze_ref → overrides)
- ลิงก์ TikTok/YouTube โหลดไม่ได้ → ขอไฟล์ หรือใช้ชื่อสไตล์

## 4. มาตรฐานคุณภาพ
Hook ≤3 วิ · ตัดเงียบ >0.2–0.3 วิ · ยาว 35–55 วิ · สี ฟ้าอ่อน #7DD3FC → น้ำเงิน #1E46B8 → ชมพูอ่อน #F9A8D4 (navy #122A6B)
safe zone: บน ≥130 · ล่าง ≤1440 · ขวา ≤930 (1080x1920) · ลำดับพื้นที่: **ใบหน้า (หลังซูม) > ซับ > การ์ด** · ซับห่างการ์ด ≥24 px
-14 LUFS ±1 · true peak ≤ -1.4 dBFS · ซับไทยต้องตรงคำพูด (แก้ถอดผิดก่อน render)

## 5. Visual QA Protocol (ชดเชยที่ Claude ฟังเสียงไม่ได้/เห็นแค่ภาพนิ่ง)
ทุก render ต้องสร้าง (`tools/vt/qa_visual.py`):
- `artifacts/qa/audio_diagnostics.png` — waveform + dBFS + แถบช่วงที่ถอดเสียงได้ + เส้นจุดตัด + แถบแดง = เสียงพูดที่ไม่มีซับ
- `artifacts/qa/contact_sheet.png` — เฟรม ณ ซูมแรง/การ์ด/ซับ + กรอบ **แดง=หน้า · น้ำเงิน=การ์ด · เขียว=ซับ**
- manifest `qa.collision_count` ต้อง = 0 · `asr.coverage.uncovered_spans` ต้องว่าง
เปิดดูภาพด้วย Read ก่อนส่งงานเสมอ (หรือให้ 02-visual-qa-critic ตรวจ)

## 6. Cascading Model Routing (Tier 0 → 1 → 2 → 3)
| Tier | โมเดล | Agents | งาน |
|---|---|---|---|
| 0 | เซสชันหลัก | — | สถาปัตยกรรม, สัญญาโมดูล, **dispatcher** (spawn depth = 1: subagent สั่ง subagent ต่อไม่ได้ → Tier 0 สั่งทุก tier เอง), creative pass |
| 1 | opus | 01-director-orchestrator, 02-visual-qa-critic | วินิจฉัยปัญหาข้ามโมดูล, ตรวจรับงานจากภาพ QA |
| 2 | sonnet | 03-asr-thai-transcriber, 04-thai-dedup-cutter, 05-cv-face-tracker, 06-graphics-broll-compositor, 07-ffmpeg-render-engineer | เขียน/แก้โค้ดโมดูลของตัวเองเท่านั้น |
| 3 | haiku | Explore, 09-test-runner, 10-bundle-guardian | ค้นโค้ด, รันเทสต์ (ไม่แก้โค้ด), commit + bundle |

### กติกา routing
- เริ่ม **ค้นหา/รันเทสต์ที่ Haiku**, **เขียนโค้ดที่ Sonnet**; Opus เฉพาะ escalation + QA gate
- งานโมดูลต่างกัน → สั่ง Sonnet ขนานกันได้ (แต่ละตัวแก้เฉพาะไฟล์ตัวเองตาม INTERFACES.md)
- **Escalate → 01-director-orchestrator** เมื่อ: Sonnet แก้บั๊กเดิมไม่ผ่าน 2 รอบติด · `collision_count > 0` หลังแก้ 1 รอบ · ปัญหาข้ามโมดูล/สัญญาไม่พอ
- ส่งต่องานผ่าน `projects/<name>/pipeline_manifest.json` (สคีมากลาง) ไม่ส่งผ่านข้อความยาว
- prompt ให้ subagent: ระบุไฟล์ที่แก้ได้, สัญญา, คำสั่งทดสอบ, เกณฑ์ผ่าน — สั้นและครบ

## 7. ความต่อเนื่องของงาน (เครื่องถูกล้างได้)
- จบ milestone → commit → **push 1 ครั้ง** (403 = ไม่ต้องวนซ้ำ) → `git bundle create video-production-system.bundle --all` → ส่งไฟล์ bundle ให้ผู้ใช้
- ห้าม commit สื่อ (mp4/mov/wav/assets/projects) — gitignored
- ห้ามดาวน์โหลดโมเดลจาก HuggingFace ตอนรัน (ถูกบล็อก) → ใช้ `assets/model` (Whisper small) จาก `setup.sh`

## 8. ข้อจำกัดเครื่องคลาวด์
CPU 4 คอร์ ไม่มี GPU · เข้าได้: npm, PyPI, apt, WebSearch · บล็อก: HuggingFace, Pexels/Pixabay/Mixkit/Freesound, YouTube/TikTok · GitHub push 403
B-roll = ไฟล์ที่ผู้ใช้แนบ หรือการ์ดวาดเอง · เพลง/เสียง = สังเคราะห์ + uisfx (CC0)
