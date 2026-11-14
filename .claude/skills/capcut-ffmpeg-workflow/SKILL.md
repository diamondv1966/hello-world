---
name: capcut-ffmpeg-workflow
description: Turn an editing plan into precise CapCut steps (project setup, split, voice enhance, keyframe zoom, adjust, text templates and animations, overlays with mask, stickers, SFX, music ducking, safe-zone check, export) and the equivalent FFmpeg render pipeline in video-toolkit. Use when writing section 11 of a plan or when rendering the final file.
---
# CapCut / FFmpeg Workflow

## CapCut (ใส่ค่าจริงจากแผน)
1. New project → นำเข้า → Canvas 9:16 · Resolution 1080p
2. Split ตามตารางจุดตัด → ลบช่วงเงียบ (หรือ Auto cut → Remove pauses แล้วตรวจกับตาราง)
3. คลิป → Audio: Enhance voice ✓ · Reduce noise ✓ · Normalize loudness ✓
4. Keyframe zoom ต้น/ท้ายทุกช่วง (เช่น 100→106%); ตัดกลางประโยค → Scale +6% ทันที
5. Adjust (ค่าจากหัวข้อ 10) → Apply to all
6. Text → ฟอนต์ Kanit/Prompt → สี+ขอบตาม palette → Animation In (Pop/Slide/Typewriter/Wipe 0.2–0.3s) → Save as template ใช้ซ้ำ
7. Progress bar: Overlay → Shape → keyframe ความกว้างทีละ 1/N
8. B-roll: Overlay → Mask Rectangle (มุมมน) → Stroke ขาว 8 → Shadow → In: Slide right + Zoom in · Out: Fade
9. ไอคอน: Sticker → In: Pop · Loop: Float
10. SFX: Audio → Sound effects → วางตาม cue sheet, Volume 20–45%
11. Music → Volume ~10% → Auto ducking ✓ → Fade out 2s
12. เปิด Safe zone (TikTok) ตรวจข้อความ/การ์ดไม่ทับ UI
13. Export 1080p · 30fps · bitrate สูง · ตั้งปกเป็นเฟรม Hook

## FFmpeg (video-toolkit)
```bash
tools/render_example.sh projects/<name>     # ต้องมี src.mp4 + timeline.py
```
ลำดับภายใน: trim+zoompan ต่อช่วง → concat → curves/eq/colorbalance/vignette/unsharp → libass (ASS) → overlay RGBA จาก gfx.py (pipe rawvideo) → voice chain → sidechain ducking → loudnorm 2 รอบ → alimiter → AAC 256k
QA: `tools/measure.sh FINAL.mp4` (-14 LUFS, peak ≤ -1.4) + ดึงเฟรมกลางทุกการ์ด/จุดตัดดูด้วยตา
ปัญหาที่เจอบ่อย: background job ถูกฆ่า → รัน render แบบ foreground (timeout ≥10 นาที); `rm` กับตัวแปร → ใช้ `"${P:?}"`
