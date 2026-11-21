# รอบที่ 1 — ติดตั้งบนเครื่อง Windows

ผู้ทำ: **เจ้าของ** (ข้อ 1-4) แล้ว **pc-care** ตรวจ (ข้อ 5)
เหตุผล: การติดตั้งโปรแกรมและใส่คีย์ เป็นงานของเจ้าของตามกติกา บอทห้ามติดตั้งเอง

1. ติดตั้ง Git ถ้ายังไม่มี: `winget install -e --id Git.Git`
2. ดาวน์โหลดโปรเจกต์ (เปิด PowerShell ใหม่หลังติดตั้ง Git)
   ```
   git clone -b claude/awesome-faraday-pj20x4 https://github.com/diamondv1966/hello-world C:\shopee-affiliate
   cd C:\shopee-affiliate
   ```
3. รัน `powershell -ExecutionPolicy Bypass -File setup.ps1`
   - ติดตั้ง Python 3.12, FFmpeg, edge-tts, pythainlp
   - ถามคีย์ Gemini: วางคีย์เดียวกับใน AURIX `.env.local` (หรือสร้างใหม่ฟรีที่ aistudio.google.com)
   - คีย์ถูกเก็บในไฟล์ `.env` บนเครื่องเท่านั้น ไม่ขึ้น GitHub
4. ตั้งค่าพลังงาน Windows: Settings > System > Power > Screen and sleep > "When plugged in, put my device to sleep after" = **Never**
   (หรืออย่างน้อยให้เครื่องตื่นช่วง 07:00-22:45 ในวันที่จะให้ทีมทำงาน)
5. สั่ง `pc-care`:
   ```
   ใบสั่งงานรอบที่ 1: ตรวจความพร้อมเครื่อง
   - ไปที่ C:\shopee-affiliate รัน python aff.py doctor และ python -m unittest tests/test_pipeline.py
   - ตรวจพื้นที่ว่างไดรฟ์ C และการตั้งค่าโหมดหลับ
   - รายงานผลทุกบรรทัดของ doctor ตามจริง ห้ามแก้หรือติดตั้งอะไรเอง
   ```

ผ่านเมื่อ: doctor ขึ้น OK ทุกบรรทัด (products ยังเป็น needs_info 48 ถือว่าปกติ) และเทสต์ขึ้น OK
ไม่ผ่าน: ส่งผล doctor ทั้งหมดให้ Claude Code
