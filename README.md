# Shopee Affiliate อัตโนมัติ (faceless)

สายพานผลิตคอนเทนต์ Shopee Affiliate ที่รันบน Windows ด้วยของฟรีทั้งหมด และมีทีมบอท Maus คุมงานประจำวัน

- แผนและกลยุทธ์: [docs/PLAN.md](docs/PLAN.md)
- ทีมบอท Maus 5 ตัว (ข้อความวางในช่องคำสั่งระบบ): [docs/MAUS_TEAM.md](docs/MAUS_TEAM.md)

## เริ่มใช้วันนี้ (ประมาณ 30 นาที)

1. ดาวน์โหลดโปรเจกต์นี้ลงเครื่อง เช่น `C:\shopee-affiliate`
   (`git clone https://github.com/diamondv1966/hello-world C:\shopee-affiliate` แล้ว `git checkout claude/awesome-faraday-pj20x4`)
2. เปิด PowerShell ในโฟลเดอร์นั้น รัน `powershell -ExecutionPolicy Bypass -File setup.ps1`
   (ติดตั้ง Python, FFmpeg, edge-tts และถามคีย์ Gemini ใช้คีย์เดียวกับ AURIX ได้)
3. เปิดหน้าต่าง `affiliate.shopee.co.th` ที่ล็อกอินไว้ ทิ้งไว้ให้บอท
4. สร้างบอท 5 ตัวในแอป Maus ตาม `docs/MAUS_TEAM.md`
5. สั่ง `shopee-scout` เติมข้อมูลสินค้า 10-15 ชิ้นแรก แล้วสั่ง `shopee-producer` รัน `run_daily.bat`
6. อนุมัติในแอป Maus แล้ว `shopee-publisher` จะโพสต์ Facebook ให้ และส่งคลิป Shopee Video มาให้คุณกดโพสต์จาก iPhone

## คำสั่ง

| คำสั่ง | ทำอะไร |
|---|---|
| `python aff.py doctor` | ตรวจว่าเครื่องพร้อม |
| `python aff.py import` | นำเข้าไฟล์ที่ scout เขียนไว้ใน `data/inbox/` |
| `python aff.py todo` | สินค้าที่ยังขาดข้อมูล |
| `python aff.py daily` | คัด 10 ชิ้น เขียนคอนเทนต์ ตรวจ ทำคลิปและภาพ ลง `out/<วันที่>/` |
| `python aff.py approve all` | บันทึกการอนุมัติ |
| `python aff.py posted 3 shopee_video <ลิงก์>` | บันทึกว่าโพสต์แล้ว และลง tracker |
| `python aff.py stat <id> facebook clicks=10 commission_net=25` | ใส่ยอดลง tracker |
| `python aff.py report` | สรุปผล |

ปรับจำนวนต่อวัน เวลาโพสต์ และเกณฑ์ค่าคอมได้ที่ `affiliate/config.py`
เพลงประกอบ (ไม่บังคับ): วางไฟล์ .mp3 ที่ได้สิทธิ์ใช้ เช่น จาก YouTube Audio Library ใน `assets/music/` ระบบจะสุ่มใส่เบา ๆ ใต้เสียงพูด
ทดสอบ: `python -m unittest tests/test_pipeline.py`

## โครงสร้าง

```
aff.py                 คำสั่งทั้งหมด
affiliate/             config, store (สินค้า), content (Gemini + ตรวจกฎ), captions (ซับไทยทีละคำ), render (คลิป/ภาพ), planner, tracker
assets/fonts/          ฟอนต์ Kanit Bold (SIL OFL)
prompts/               prompt เขียนคอนเทนต์ (มุมขาย + กฎความจริง)
data/products/         สินค้า 1 ไฟล์ต่อชิ้น (ย้ายมาจาก AURIX 48 ชิ้น)
data/inbox/            scout วางไฟล์ที่นี่ (ดู TEMPLATE.txt, LINKS_TO_SCOUT.md)
data/tracker/posts.csv บันทึกผล 41 คอลัมน์
media/, out/           รูปที่ดาวน์โหลด และงานประจำวัน (ไม่ขึ้น git)
```
