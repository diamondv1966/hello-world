---
description: ปรับปรุง D-Skill Playbook จากความล้มเหลวจริงที่บันทึกไว้ (contrastive distillation) แล้วตรวจความปลอดภัยของ Skills
argument-hint: "[หมวดหรือเหตุการณ์ที่จะสกัด]"
---

<!-- D-SKILL-PREFLIGHT:BEGIN -->
## D-Skill Preflight (บังคับ — ทำก่อนอย่างอื่นทั้งหมด)

1. โหลด Skill `00-fable-d-skill-playbook` (หรืออ่าน `SKILL.md` ของมันโดยตรงจาก `.claude/skills/` หรือ
   `~/.claude/skills/`) แล้วพิมพ์ตาราง `D-SKILL STATUS` ครบ 7 ขั้นตอน
2. อ่าน `docs/COST_QUALITY_LOG.json` ของจริง ห้ามสรุปจากความจำ
3. กฎการแก้ Playbook:
   - เพิ่ม/แก้แถวใน Step 2 ได้ **เฉพาะ** เมื่อมีรายการในล็อกที่ `new_failure_mode` ไม่ว่าง หรือมีหลักฐานความล้มเหลวจริง (diff, error, ภาพ)
   - ทุกแถวต้องครบ 3 ช่อง: นักเรียนมักพลาด / เกณฑ์ของครู / หลักฐานบังคับที่ตรวจด้วยเครื่องได้
   - ห้ามเพิ่มข้อความบรรยายความสามารถลอยๆ ที่ไม่มีวิธีตรวจ
   - `SKILL.md` ต้องไม่เกิน 400 บรรทัด ถ้าเกินให้ย้ายรายละเอียดไป `references/`
   - ห้ามใส่ไวยากรณ์ dynamic context หรือคำสั่งที่อ่านโทเคนแล้วส่งออกเครือข่าย
4. หลังแก้ รัน `python .claude/skills/00-fable-d-skill-playbook/scripts/audit_skills_security.py`
   (หรือพาธเดียวกันใต้ `~/.claude/`) ต้อง exit code 0 จึงถือว่าเสร็จ
<!-- D-SKILL-PREFLIGHT:END -->

## ขอบเขต

$ARGUMENTS

## ผลลัพธ์ที่ต้องรายงาน

- แถวที่เพิ่ม/แก้ พร้อมรายการในล็อกที่เป็นที่มา
- ผล audit จริง
- Cost per Acceptable Task ล่าสุดที่คำนวณจากล็อก (ถ้าข้อมูลต้นทุนเป็น `null` ให้รายงานอัตรา accepted และจำนวนรอบแก้เฉลี่ยแทน)
