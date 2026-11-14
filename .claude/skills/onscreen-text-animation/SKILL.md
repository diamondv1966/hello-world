---
name: onscreen-text-animation
description: Design Thai on-screen text (headline, body, cause highlight, CTA) for vertical video in the light-blue → blue → light-pink palette, with sizes, positions inside TikTok safe zones, timing and animation recipes (CapCut presets + ASS/libass tags). Use when planning or rendering captions, supers, hooks, CTAs or text animation.
---
# ข้อความบนจอ + อนิเมชัน

## จานสี (ASS ใช้ &HAABBGGRR)
| ชื่อ | HEX | ASS | ใช้กับ |
|---|---|---|---|
| ฟ้าอ่อน | #7DD3FC | &H00FCD37D | หัวข้อเล็ก, ปุ่มรอง, วงแหวน |
| น้ำเงิน | #1E46B8 | &H00B8461E | กล่องสาเหตุ/ไฮไลต์ |
| Navy | #122A6B | &H006B2A12 | ขอบตัวอักษร, เงา |
| ชมพูอ่อน | #F9A8D4 | &H00D4A8F9 | เลขข้อ, คำเน้น, progress |
| ขาว | #FFFFFF | &H00FFFFFF | ตัวหลัก |
ฟอนต์: Kanit ExtraBold (พาดหัว/เลข) · Kanit Regular (บรรยายยาว) — `video-toolkit/assets/fonts/`

## ขนาด/ตำแหน่ง (1080x1920)
- Safe zone: บน ≥130px, ล่าง ≤1440px (ล่าง 480px = แคปชั่น/ชื่อ), ขวา ≤930px (ปุ่ม TikTok)
- พาดหัว 110–150px กลางบน y 250–420 · หัวข้อเล็ก 46px y≈160 · เลขข้อ 210px (135,378) · อาการ 112px (265,300) · กล่องสาเหตุ 80px (265,455) · คำเตือน 34px y≈600 · CTA 78–88px y 1200–1400
- ข้อความไทยยาว >14 ตัว → ลดเป็น 96px หรือขึ้น 2 บรรทัด

## อนิเมชัน (≤0.3 วิ, ease-out)
| ประเภท | CapCut | ASS recipe |
|---|---|---|
| Hook คำเน้น | Pop / Scale up | `{\fscx70\fscy70\t(0,120,\fscx108\fscy108)\t(120,200,\fscx100\fscy100)}` |
| พาดหัวทีละคำ | Typewriter | `{\alpha&HFF&\t(0,90,\alpha&H00&)}คำ1 {\alpha&HFF&\t(170,260,\alpha&H00&)}คำ2` |
| เลขข้อ | Pop + rotate | `{\an5\fscx0\fscy0\frz-12\t(0,170,\fscx118\fscy118\frz3)\t(170,260,\fscx100\fscy100\frz0)}` |
| อาการ | Slide in | `{\move(x,y+30,x,y,0,280)\fad(130,0)\blur6\t(0,260,\blur0.6)}` |
| สาเหตุ (ไฮไลต์) | Wipe → right | `{\clip(240,0,240,1920)\t(0,320,\clip(240,0,1080,1920))}` + BorderStyle 3 กล่องน้ำเงิน |
| CTA ปุ่ม | Bounce + Pulse | `\t(0,200,\fscx110)\t(200,300,\fscx100)` แล้ว pulse 106% ทุก 1 วิ |
| progress bar | Keyframe width | `\p1` rect + `\clip` แอนิเมต 1/N ต่อข้อ |

## กติกา
- ข้อความเดียวกับที่พูด (คำพูด = ข้อความ = แคปชั่น สอดคล้อง)
- ข้อความเก่าออกก่อนข้อใหม่ 0.05 วิ; อย่าซ้อนพาดหัวกับข้อแรก
- กล่องสีห้ามแยกสีในบรรทัดเดียว (libass แตกกล่อง) — ใช้สีเดียวทั้งกล่อง
- Kanit ไม่มี ↔ และสัญลักษณ์พิเศษบางตัวใน PIL → ใช้คำไทยแทน (libass ใช้ font fallback ได้)
- คลิปสุขภาพ: ใส่คำเตือน "ข้อมูลเบื้องต้น ไม่ใช่การวินิจฉัย"
อ้างอิงโค้ดจริง: `video-toolkit/examples/9-signals/video.py`
