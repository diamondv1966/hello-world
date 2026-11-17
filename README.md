# D-Skill & Zero-Advisor-Tax Kit

ชุดอัปเกรด `.claude/` สำหรับทำงานด้วย Opus/Sonnet/Haiku ตาม Playbook แบบ contrastive (D-Skill)
โดยไม่ต้องเปิด advisor ค้างไว้

## สิ่งที่อยู่ในชุด

| พาธ | หน้าที่ |
|---|---|
| `.claude/skills/00-fable-d-skill-playbook/SKILL.md` | Playbook 7 ขั้นตอน + ตารางจุดพลาด (วิดีโอไทย / Supabase & Vercel / Realtime & YouTube) |
| `.claude/skills/00-fable-d-skill-playbook/scripts/audit_skills_security.py` | ตรวจพาธ, `name` ตรงโฟลเดอร์, สเปก agentskills.io, dynamic context, การดึงโทเคนออกนอกเครื่อง |
| `.claude/skills/00-fable-d-skill-playbook/assets/` | แม่แบบ `ESCALATION_BRIEF.md` และ `COST_QUALITY_LOG.json` |
| `.claude/commands/takeover.md`, `evolve.md` | โหลด Playbook และแสดงสถานะ 7 ขั้นตอนก่อนเริ่มงาน |
| `docs/ESCALATION_BRIEF.md`, `docs/COST_QUALITY_LOG.json` | ไฟล์ใช้งานจริงของโปรเจกต์นี้ |
| `install.py` | ติดตั้งลง `~/.claude` (บน Windows คือ `C:\Users\<ชื่อ>\.claude`) |

## ติดตั้ง

```
python install.py --dry-run     # ดูก่อนว่าจะเปลี่ยนอะไร
python install.py               # ติดตั้งจริง แล้วรัน audit ให้อัตโนมัติ
```

- ถ้ามี `/takeover` หรือ `/evolve` อยู่แล้ว ไฟล์เดิมจะถูกเก็บไว้ ตัวติดตั้งแทรกเฉพาะบล็อก
  `D-SKILL-PREFLIGHT` และสำรองไฟล์เดิมเป็น `.bak`
- Skill เดิมชื่อเดียวกันจะถูกย้ายไป `~/.claude/backups/` ก่อน

## ตรวจ Skills

```
python .claude/skills/00-fable-d-skill-playbook/scripts/audit_skills_security.py
```

สแกน `~/.claude` และ `./.claude` — exit code 0 = ผ่าน, 1 = มี FAIL ตัวเลือก: `--json`, `--strict`,
`--allow-local-dynamic`, `--max-lines 400`, `--root DIR`, `--ignore NAME`

## หมายเหตุ

กฎใน Playbook มาจากรายงานวิจัยของเจ้าของโปรเจกต์ ตัวเลขราคา/โควตา/เปอร์เซ็นต์ในรายงานนั้น
ไม่ได้ถูกตรวจสอบซ้ำในชุดนี้ ให้วัดผลจริงจาก `docs/COST_QUALITY_LOG.json`
