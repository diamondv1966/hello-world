# video-toolkit — ระบบทีมตัดต่อคลิปสั้น (TikTok / Reels)

เปลี่ยนคลิปดิบแนวตั้งให้เป็นคลิประดับมืออาชีพ: ตัดช่วงเงียบ, ข้อความไทยพร้อมอนิเมชัน, การ์ดภาพประกอบที่เคลื่อนไหว, เอฟเฟกต์เสียง CC0, เพลงที่สร้างใหม่ และมาสเตอร์ที่ -14 LUFS

📘 คู่มือฉบับเต็ม: [`docs/AI-Video-Production-System.pdf`](docs/AI-Video-Production-System.pdf)

## เริ่มต้น
```bash
cd video-toolkit
./setup.sh           # ติดตั้งโมเดลถอดเสียง, ฟอนต์ Kanit, เสียง uisfx ลง assets/ (~15 วินาที)
./check_system.sh    # ✅/❌ ทุกส่วน → "ระบบพร้อมใช้งานแล้ว"
```

## ใช้กับคลิปใหม่
```bash
tools/new_project.sh /path/to/clip.mp4 my-clip   # ยืนยันชื่อไฟล์ + SHA-256, เตือนถ้าเป็นคลิปซ้ำ
python3 -I tools/transcribe.py projects/my-clip  # ถอดเสียงไทย → transcript.txt
tools/silences.sh projects/my-clip/src.mp4       # ช่วงเงียบ ≥0.2s
tools/measure.sh  projects/my-clip/src.mp4       # LUFS / เสียงรบกวน / ความสว่าง / ความอิ่มสี
# เขียน projects/my-clip/timeline.py (ดูตัวอย่าง examples/9-signals/timeline.py)
tools/render_example.sh projects/my-clip         # → projects/my-clip/FINAL.mp4
```

## โครงสร้าง
| path | คืออะไร |
|---|---|
| `setup.sh`, `check_system.sh` | ติดตั้ง / ตรวจระบบ |
| `tools/` | เครื่องมือ: new_project, transcribe, silences, measure, contact_sheet, render_example, make_pdf |
| `examples/9-signals/` | pipeline เต็มที่ใช้จริง (timeline → video → sound → sfx → gfx) ใช้เป็นแม่แบบ |
| `docs/` | คู่มือ PDF + ต้นฉบับ HTML (`node tools/make_pdf.js docs/system_guide.html docs/out.pdf`) |
| `assets/` *(gitignored)* | โมเดล, ฟอนต์, เสียง — สร้างโดย setup.sh |
| `projects/` *(gitignored)* | งานแต่ละคลิป + `.registry.tsv` (SHA-256 ของคลิปที่เคยใช้) |

## ข้อจำกัดของเครื่องคลาวด์
เว็บ Stock/เสียง (Pexels, Pixabay, Mixkit, Freesound, HuggingFace) ถูกบล็อก → ทุกอย่างดึงจาก npm/PyPI; B-roll ใช้การ์ดภาพประกอบที่วาดเอง หรือแนบไฟล์มาเอง

## ใบอนุญาตสื่อ
uisfx = CC0 1.0 · Kanit = SIL OFL · Noto Color Emoji = OFL · Whisper = MIT · เพลง/เสียงสังเคราะห์ = สร้างใหม่ในระบบ
