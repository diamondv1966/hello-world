---
name: music-direction
description: Music direction for short-form vertical video — pick mood, genre and tempo from the clip's content, set level vs voice with ducking, map where music rises, dips, filters or goes silent, and generate copyright-free original background music. Use when planning or rendering background music.
---
# Music Direction

## เลือกอารมณ์/จังหวะจากเนื้อหา
| เนื้อหา | Mood | แนว | BPM |
|---|---|---|---|
| ความรู้/สุขภาพ/ลิสต์ | สดใส ห่วงใย | lo-fi pop, chill motivational, EP/เปียโนนำ | 90–105 |
| สร้างแรงบันดาลใจ | Motivational | cinematic pop, piano+strings | 85–100 |
| รีวิว/ขายของ | Energetic | upbeat pop, future bass เบา | 110–125 |
| เล่าเรื่อง/ปริศนา | Mysterious | ambient, pulse bass | 70–90 |
| ตลก/ไวรัล | Playful | ukulele, pizzicato, bouncy | 100–120 |

## ระดับ
เพลงต่ำกว่าเสียงพูด **17–20 dB** (CapCut 8–12%) + ducking ลดอีก 3–5 dB ตอนพูด (`sidechaincompress=threshold=0.03:ratio=3:attack=25:release=400`)
มาสเตอร์รวม -14 LUFS, true peak ≤ -1.5 dBFS (loudnorm 2 รอบ + alimiter)

## ไดนามิกตามโครงสร้าง
| ช่วง | เพลง |
|---|---|
| Hook | low-pass (ทึบ) ไม่มีกลอง → เปิดฟิลเตอร์ 1.2 วิก่อนข้อแรก |
| ข้อแรก | **drop** กลองเข้าตรงเฟรม |
| ก่อนไคลแมกซ์ | riser; **เงียบ 0.3 วิ** แล้วกลับพร้อม impact |
| เกริ่นตอนต่อไป | breakdown (ทึบลง ไม่มีกลอง) |
| CTA | กลองกลับ → fade 2 วิท้าย |

## เพลงต้นฉบับ (ไม่ติดลิขสิทธิ์)
`examples/9-signals/sound.py` — 96 BPM, Fmaj7–G6–Em7–Am7, EP+pad+sub+kick/rim/shaker, stereo + reverb; ปรับ BPM/คอร์ด/เครื่องดนตรีได้ในไฟล์
ถ้าผู้ใช้อยากใช้เพลงฮิต TikTok → ส่งเวอร์ชันไม่มีเพลง แล้วแนะนำแนว/BPM ให้เลือกในแอป
