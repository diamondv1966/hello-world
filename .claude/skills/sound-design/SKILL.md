---
name: sound-design
description: Sound design for short vertical videos — choose and place SFX (whoosh, soft click/pop, subtle impact, ambient riser, soft notification, shimmer, ticks) synced to cuts and animations, with levels relative to voice, voice cleanup chain and CC0 sourcing from the bundled uisfx library. Use when planning or rendering audio effects.
---
# Sound Design

## คลังเสียง (CC0 / สร้างเอง)
`video-toolkit/assets/uisfx/sounds/<pack>/<cue>.mp3` — 12 packs (soft, glass, dreamy, cinematic, studio, minimal, organic, zen, rubber, mechanical, arcade, scifi) × 78 cues
| บทบาท | แนะนำ | ทางเลือก |
|---|---|---|
| ทรานสิชัน | cinematic/swipe + whoosh สังเคราะห์ | dreamy/swipe |
| เลขข้อ / progress | glass/progress-step | soft/press |
| ไฮไลต์ข้อความ | soft/select | glass/select |
| คำเตือน / Hook | glass/notification + shimmer | glass/warning |
| ปิดครบชุด | glass/level-up | glass/achievement |
| CTA | glass/success | cinematic/reward |
| ปิดท้าย | dreamy/achievement | — |
whoosh, riser, impact, shimmer, ECG beep = สังเคราะห์ (`examples/9-signals/sound.py`, `sfx.py`)
เลือก pack เดียว–สอง pack ต่อคลิปให้โทนเป็นชุดเดียว (พรีเมียม = glass + soft)

## ระดับเทียบเสียงพูด
| ประเภท | dB |
|---|---|
| Impact ไคลแมกซ์ | -6 |
| Notification / CTA | -8 |
| Click เลขข้อ | -9 |
| Pop / Select / Whoosh | -10 ถึง -12 |
| Riser | -12 |
| ซ้ำถี่ (ticks, grid pops, card whoosh) | -14 ถึง -16 |
กติกา: เสียงที่ซ้ำทุกข้อ = เบา; ดังจริงเฉพาะไคลแมกซ์และ CTA; ไม่วางทับพยางค์เน้นของเสียงพูด

## จังหวะวาง
whoosh เริ่มก่อนภาพเปลี่ยน 0.2 วิ · click ตรงเฟรมเลขขึ้น · riser 1.5 วิก่อนไคลแมกซ์ แล้ว impact ตรงเฟรม · ticks ตามตัวนับ ทุก 0.12 วิ · grid pops ไล่ pitch +7%/ตัว

## Voice chain (FFmpeg)
`afftdn=nf=-48,highpass=f=85,equalizer=f=220:g=1.5,equalizer=f=3200:g=2,equalizer=f=10000:t=h:g=1.5,deesser=i=0.35,acompressor=threshold=-22dB:ratio=3:attack=6:release=90:makeup=2`
CapCut: Enhance voice + Reduce noise + Normalize loudness
ส่งมอบ: SFX_pack (wav) + cue_sheet.tsv (เวลา/เสียง/เหตุผล) + LICENSE
