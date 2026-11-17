---
description: รับช่วงงานต่อด้วยโมเดลหลัก (Opus) โดยโหลด D-Skill Playbook และแสดงสถานะ 7 ขั้นตอนก่อนเริ่ม
argument-hint: "[งานที่จะรับช่วง]"
---

<!-- D-SKILL-PREFLIGHT:BEGIN -->
## D-Skill Preflight (บังคับ — ทำก่อนอย่างอื่นทั้งหมด)

1. โหลด Skill `00-fable-d-skill-playbook` ด้วยเครื่องมือ Skill ถ้าโหลดไม่ได้ ให้อ่านไฟล์
   `.claude/skills/00-fable-d-skill-playbook/SKILL.md` (ระดับโปรเจกต์) หรือ
   `~/.claude/skills/00-fable-d-skill-playbook/SKILL.md` (ระดับผู้ใช้) โดยตรง
   ถ้าไม่พบทั้งสองที่ ให้ **หยุด** และแจ้งผู้ใช้ว่า Skill ไม่ได้ติดตั้ง ห้ามทำงานต่อจากความจำ
2. พิมพ์ตาราง `D-SKILL STATUS` ครบ 7 ขั้นตอนตามแม่แบบใน Skill ก่อนเริ่มงาน
3. ทำ Step 1 (Ground Truth) ด้วยคำสั่งอ่านอย่างเดียว แล้วเติมหลักฐานลงตาราง
4. ระบุแถวใน Failure-Mode Table (V/D/R) ที่เกี่ยวกับงานนี้
5. ยืนยันว่า advisor ปิดอยู่ ถ้าติดเกิน 2 รอบ ให้ใช้ `docs/ESCALATION_BRIEF.md` (ไม่เกิน 300 คำ)
6. ห้ามทำการกระทำภายนอกใดๆ (Step 6) จนกว่าผู้ใช้จะยืนยัน
<!-- D-SKILL-PREFLIGHT:END -->

## งาน

$ARGUMENTS

ถ้าไม่ได้ระบุงาน ให้สรุปสถานะปัจจุบันจากผล Step 1 (branch, งานค้าง, เทสต์ที่ล้ม) แล้วเสนองานถัดไป 1–3 ข้อ

## ตอนจบ

- รันเกตของ Step 5 และแสดงผลจริง
- เพิ่มรายการใน `docs/COST_QUALITY_LOG.json` (Step 7)
- พิมพ์ตาราง `D-SKILL STATUS` อีกครั้งพร้อมหลักฐานครบทุกขั้น
