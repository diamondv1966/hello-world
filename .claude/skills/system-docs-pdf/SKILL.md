---
name: system-docs-pdf
description: Create or update readable Thai documentation and the system-summary PDF for the video production system — HTML with Kanit fonts and the blue/pink theme rendered to A4 PDF via Playwright Chromium, then visually checked page by page. Use when the user asks for a PDF/summary/manual or after the system setup changes.
---
# เอกสาร + PDF สรุประบบ

ต้นฉบับ: `video-toolkit/docs/system_guide.html` → PDF: `video-toolkit/docs/AI-Video-Production-System.pdf`
```bash
cd video-toolkit/docs && node ../tools/make_pdf.js system_guide.html AI-Video-Production-System.pdf
pdfinfo AI-Video-Production-System.pdf | grep Pages
pdftoppm -r 40 -png AI-Video-Production-System.pdf <scratch>/p   # แล้วดูภาพทุกหน้า
```
## กติกาการออกแบบ
- ฟอนต์ `@font-face` ชี้ `../assets/fonts/KanitRegular.ttf` และ `KanitXB.ttf` (ต้องรัน setup.sh ก่อน)
- A4, margin 15–16mm; ปก gradient ฟ้า→ขาว→ชมพู; h2 มีวงเลขชมพู + เส้น gradient
- `h2 { break-after: avoid }`; หัวข้อใหญ่ขึ้นหน้าใหม่ด้วย `class="page"`; ตาราง `tr { page-break-inside: avoid }`
- **ห้ามใช้ `position: fixed` footer** (Chromium วางทับหัวข้อ)
- ตรวจทุกหน้า: หัวข้อไม่ค้างท้ายหน้า, ไม่มีกล่องว่าง (□) จากฟอนต์ขาด glyph, ตารางไม่ล้น
## เนื้อหาขั้นต่ำ
ภาพรวม · ทีม/agents · skills · สิ่งที่เตรียมไว้ (สถานะจริงจาก check_system.sh) · วิธีค้นคว้า · มาตรฐานคุณภาพ · ขั้นตอนงาน · รูปแบบตอบ 12 หัวข้อ · วิธีใช้สั้น ๆ · เคล็ดลับ (บังคับคลิปใหม่ด้วย SHA-256)
