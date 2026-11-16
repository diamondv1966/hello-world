# Knowledge Base — ระบบ AI Video Production (สำหรับปรับรากฐาน/โมเดลงาน)

> สถานะ ณ 2026-11-16 · commit ล่าสุด `d61bcdb` (branch `claude/thai-vertical-video-edit-pyav26`, **ยังไม่ได้ push — GitHub 403**)
> ทุกตัวเลขในเอกสารนี้มาจากระบบจริง/การทดสอบจริงในเซสชันนี้ ส่วนที่ "ยังไม่ได้พิสูจน์" ระบุไว้ชัด

---

## 1. สถาปัตยกรรม 6 ชั้น

| ชั้น | อยู่ที่ | หน้าที่ |
|---|---|---|
| 1. กติกา | `CLAUDE.md` | ลำดับบังคับ, มาตรฐาน, โหมดหลัก — โหลดทุกเซสชัน |
| 2. ทีม | `.claude/agents/*.md` (10) | บทบาท + ขอบเขต + สกิลที่ใช้ (เรียกเป็น subagent ได้) |
| 3. ความรู้ | `.claude/skills/*/SKILL.md` (9) + `references/` | สูตร ค่าตัวเลข ขั้นตอน ผลค้นคว้า |
| 4. สไตล์ | `video-toolkit/presets/*.json` (5) | พารามิเตอร์ทั้งหมดของ "หน้าตา" คลิป |
| 5. เครื่องมือ | `video-toolkit/tools/` | edit_like → auto_edit / analyze_ref + เครื่องมือย่อย |
| 6. ทรัพยากร | `video-toolkit/assets/` (gitignored, สร้างด้วย setup.sh) | โมเดล 241MB, ฟอนต์ 92KB, SFX 13MB |

ข้อมูลต่อคลิปอยู่ใน `video-toolkit/projects/<name>/` (gitignored) + registry SHA-256 ที่ `projects/.registry.tsv`

### โค้ด (บรรทัด)
auto_edit.py 396 · vt_lib.py 255 · analyze_ref.py 131 · examples/9-signals (gfx 234, sound 152, video 85, sfx 61, timeline 32) · shell tools ~80 · รวม ~1,500 บรรทัด

---

## 2. สภาพแวดล้อม (ข้อเท็จจริงที่กำหนดการออกแบบ)

| เรื่อง | ความจริง | ผลต่อการออกแบบ |
|---|---|---|
| เครื่อง | คลาวด์ 4 CPU, RAM 15GB, ไม่มี GPU | Whisper **small int8** (CPU) แทน large; render ใช้ CPU |
| อายุเครื่อง | ชั่วคราว ล้างได้เมื่อเซสชันจบ; scratchpad ล้างได้ | ทุกอย่างต้องอยู่ใน repo + `setup.sh` สร้าง assets ใหม่ได้ใน ~15 วิ |
| เครือข่าย **เข้าได้** | npm, PyPI, apt mirrors, GitHub (อ่าน), WebSearch | ดึงโมเดล/ฟอนต์/เสียงจาก npm, ไลบรารีจาก PyPI |
| เครือข่าย **ถูกบล็อก** | HuggingFace, Pexels, Pixabay, Mixkit, Freesound, YouTube/TikTok, WebFetch ส่วนใหญ่ | ไม่มี B-roll stock / โหลดคลิปเรฟจากลิงก์ไม่ได้ → การ์ดวาดเอง, ให้ผู้ใช้แนบไฟล์ |
| GitHub เขียน | **403 — ไม่มีสิทธิ์ push** | งานค้างในเครื่อง; สำรองด้วย `git bundle` |
| ฟังเสียง | Claude ฟังไม่ได้ | QA เสียงด้วย LUFS/peak/รูปคลื่น + ให้ผู้ใช้ฟังรอบสุดท้าย |
| ดูภาพ | Claude ดูภาพนิ่งได้ (เฟรม/contact sheet) | QA ภาพด้วยเฟรมสุ่ม + qa.jpg ทุกครั้ง |

---

## 3. ทรัพยากรและใบอนุญาต

| ทรัพยากร | แหล่ง | ใบอนุญาต | หมายเหตุ |
|---|---|---|---|
| Whisper small (CTranslate2 int8) | npm `@skillninja/shortmovie-telop-model-p0..p3@1.0.0` (ต่อ 4 ส่วน) | MIT (OpenAI) | ตรวจ SHA-256 `ca732cb1…ce73` ทุกครั้ง |
| Kanit Regular/ExtraBold | npm `@fontsource/kanit@5.3.0` → merge ไทย+ละติน | SIL OFL | PIL ไม่มี glyph ↔ → (ใช้คำแทน) |
| Noto Color Emoji | ระบบ (apt) | OFL | ใช้เป็นภาพประกอบในการ์ด/ไอคอน |
| uisfx 0.4.0 (12 packs × 78 cues) | npm `uisfx` | **CC0** | ใช้เชิงพาณิชย์ได้ ไม่ต้องให้เครดิต |
| snd-lib | npm | ลิขสิทธิ์ยังเป็นของผู้สร้าง | **ไม่ใช้** (ตรวจเงื่อนไขไม่ได้) |
| เพลง/whoosh/riser/impact/shimmer/ECG | สังเคราะห์ใน `vt_lib.py` | สร้างใหม่ | ไม่ติดลิขสิทธิ์ |
| pythainlp 5.4, OpenCV **4.x** (ห้าม 5.x), tesseract 5.3 + tha, espeak-ng | PyPI/apt | โอเพนซอร์ส | OpenCV 5 ไม่มี Haar face detector |

---

## 4. Pipeline หลัก (`edit_like.sh` → `auto_edit.py`)

| ขั้น | วิธี | ค่าเริ่มต้น / หมายเหตุ |
|---|---|---|
| Intake | `new_project.sh`: copy → `src.mp4`, SHA-256, registry เตือนซ้ำ | **ห้ามใช้ `| head`** ต่อท้าย (SIGPIPE ฆ่าก่อน copy) |
| ถอดเสียง | faster-whisper `word_timestamps=True, vad_filter=True, condition_on_previous_text=False` + **coverage fallback** (ช่วงมีเสียง ≥2 วิแต่ไม่มีคำ → ถอดซ้ำเฉพาะช่วง) | ภาษาไทย: token → เวลาต่อตัวอักษร → pythainlp `newmm` → เวลาต่อคำ |
| หาเงียบ | ffmpeg `silencedetect -33dB` d = `max_gap` | แม่นกว่าเวลาคำของ Whisper → ใช้ตัดจริง |
| ตัด | เงียบ ≥ max_gap → ตัดเหลือ pad ทั้งสองข้าง; ต้น/ท้ายคลิปตัดทิ้ง (ท้ายเหลือ end_pad 0.4) | pad 0.06 (pastel) |
| พูดซ้ำ | n-gram ซ้ำ (ไทย 5 คำ / อังกฤษ 4) ห่าง <6 วิ → ตัดเทคแรก | ทดสอบผ่าน (อังกฤษ) |
| ตัดเพิ่ม | `config.skip` = ช่วงที่ Claude เลือก (คำผิด/ไม่จำเป็น) | |
| ซูม | ต่อช่วง: สลับ `levels`, drift ภายในช่วง, +`emphasis_punch` หลังคำเน้น | zoompan บนภาพขยาย 2160x3840 (ลื่น) |
| จัดเฟรม | OpenCV Haar หาใบหน้าทุก 0.5 วิ → median ต่อช่วง → วางหน้าที่ `face_y` (40%) | ไม่เจอหน้า → `anchor` 0.38; แนวนอน → crop 9:16 ตามหน้า |
| ซับ | ASS/libass: `karaoke` (คำปัจจุบันไฮไลต์), `pop` (1–2 คำเด้ง), `phrase` (วลี fade) | ตัดชุดที่ max_words/max_chars/เว้น>0.6 วิ/จบประโยค (. ! ? ค่ะ ครับ…) |
| หลบสิ่งกีดขวาง | ช่วงการ์ด/B-roll pip/CTA → ซับย้ายขึ้น `alt_y` 380 | ตรวจทับซ้อนทั้งช่วง ไม่ใช่แค่จุดเริ่ม |
| คำเน้น | `config.emphasis` → สี emphasis + เสียง + ซูม punch | ต้องสะกดตรง words.json |
| การ์ด | PIL วาดทุกเฟรม → pipe rawvideo RGBA → overlay | กลาง (540,1215), 760x400 ×0.9, อีโมจิเด้งทีละชิ้น |
| B-roll | ไฟล์ผู้ใช้: `pip` (720x420 มุมมน ที่ y=1000) / `full` | ยังไม่ได้ทดสอบกับไฟล์จริง |
| เสียงพูด | afftdn → HPF 85 → EQ 220+1.5 / 3.2k+2 / 10k shelf+1.5 → deesser → comp 3:1 | |
| SFX | whoosh ที่จุดตัด (ห่าง ≥1.4 วิ), hook, คำเน้น, การ์ด, CTA | ระดับตาม preset |
| เพลง | สังเคราะห์ตาม mood (bright/calm/energetic/serious) + BPM; ช่วงก่อน drop ทึบ; drop = จบ hook | ducking sidechain th 0.03 ratio 3 |
| Master | loudnorm 2 รอบ (I -14, TP -1.5, linear) + alimiter 0.86 | ผลจริง -14.0 ถึง -14.7 LUFS, peak -1.4 |
| QA | qa.jpg (เฟรม 6–8 จุด), report.md, cue_sheet.tsv, captions.srt, plan.json | Claude ต้องดู qa.jpg ทุกครั้ง |

### config.json (Claude เขียนใน creative pass)
`language` · `hook.lines[]` · `emphasis[]` · `cards[{at,dur,title,items[[emoji,label]],note}]` · `broll[{at,file,dur,mode}]` · `cta{text,sub}` · `disclaimer` · `skip[[a,b]]` · override ได้ทุกคีย์ของ preset (`captions`, `music`, `zoom`, `cut`, `sfx`, `grade`, `hook`)

---

## 5. Presets (ค่าจริง)

| preset | max_gap | zoom levels / mode | ซับ style / size / คำ / ไฮไลต์ | เพลง mood / BPM / ระดับ | whoosh ที่คัต |
|---|---|---|---|---|---|
| clean-pastel | 0.25 | 1.0–1.10 alternate | karaoke / 84 / 4 / #F9A8D4 | bright / 96 / 0.095 | cinematic/swipe |
| bold-hormozi | 0.18 | 1.0–1.18 alternate | pop / 104 / 2 / #FFE600 (เน้น #3BFF6B) | serious / 90 / 0.06 | ไม่มี |
| calm-abdaal | 0.30 | 1.0–1.05 slow | karaoke / 76 / 6 / #FFD84D (past #BFC5CF), sat 0.75 | calm / 84 / 0.08 | ไม่มี |
| codie-bold | 0.22 | 1.0–1.08 alternate | phrase / 92 / 5 / ขาวไม่มีขอบ เงา 6, warm +0.04 | energetic / 104 / 0.07 | ไม่มี |
| minimal-aesthetic | 0.35 | 1.0–1.03 slow | phrase / 58 Regular / 7 | calm / 80 / 0.085 | ไม่มี |

ระดับเพลง 0.095 ≈ เพลงต่ำกว่าเสียงพูด ~17–20 dB ก่อน ducking

---

## 6. วิเคราะห์เรฟ (`analyze_ref.py`) — ความแม่นที่วัดได้

| ค่า | วิธี | ผลทดสอบ (เรฟที่รู้ค่าจริง) |
|---|---|---|
| จำนวนคัต / shot length | scene score ทุกเฟรม → peak > max(0.08, median×8) | 10/10 ✅ |
| คำต่อซับ | OCR tesseract (tha+eng) → กลุ่มบรรทัด → บรรทัดใหญ่สุด | 2/2 ✅ |
| style ซับ | คำบนจอ ≤2.2 + เปลี่ยน ≥1.2/วิ → pop; ≤5 → karaoke; อื่น → phrase | pop ✅ |
| สีไฮไลต์ | สีพิกเซลสว่างในกล่องข้อความ (quantize 32) | #F0F010 ≈ #FFE600 ✅ |
| ตำแหน่งซับ y | median กลางบรรทัด | 1175 vs 1220 ✅ (ใกล้) |
| ขนาดฟอนต์ | ความสูงกล่อง OCR × 2.0 (en) / 1.55 (th) | เดิม 72 vs 104 ❌ → แก้ตัวคูณแล้ว **ยังไม่ทดสอบซ้ำ** |
| ซูม | ขนาดหน้า (Haar) ทุก 0.25 วิ → เปลี่ยน >8% = punch | ทดสอบกับภาพทดสอบไม่ได้ (ไม่มีหน้าคน) |
| เพลง | ระดับเสียงในช่วงหยุดพูด > -42 dB และแทบไม่มีความเงียบ | ประมาณการ |
| preset ใกล้สุด | กฎ: cut+zoom ≥25/นาที หรือ pop → bold; ฟอนต์ <64 → minimal; sat <0.18 → calm; อื่น → pastel | bold-hormozi ✅ |
| max_gap | median pause × 1.2 (0.15–0.35) | สมเหตุสมผล |

---

## 7. เวลา render (เครื่องนี้)

| งาน | เวลา |
|---|---|
| setup.sh จากศูนย์ | ~12–15 วิ |
| ถอดเสียง 60 วิ (ช่วงซ้อน) | ~1–1.5 นาที |
| auto_edit plan-only (cache แล้ว) | ~15 วิ |
| auto_edit เต็ม (17 วิ + การ์ด 1) | ~50 วิ |
| analyze_ref (16 วิ) | ~55 วิ |
| pipeline ตัวอย่าง 9-signals (52 วิ + การ์ด 9 + กราฟิกเต็ม) | ~9 นาที |

---

## 8. บทเรียนจากงานจริง (bug → วิธีแก้) — สำคัญสำหรับรากฐาน

1. **Whisper ข้ามช่วงกลางคลิป** (26–56 วิ หายตอนถอดรอบเดียว) → ถอดแบบช่วงซ้อน / VAD + coverage fallback
2. **Whisper small ภาษาไทยสะกดผิด** (เช่น "ตะคิว", "แม็กมิเศียม") → Claude ต้องแก้ words.json ก่อน render เสมอ
3. **ไฟล์ "ใหม่" ที่ผู้ใช้ส่งมา 3 ครั้ง เป็นไฟล์เดียวกันทุกไบต์** → ระบบ SHA-256 registry
4. **libass แตกกล่องสีเมื่อเปลี่ยนสีกลางบรรทัด** (BorderStyle 3) → สีเดียวทั้งกล่อง
5. **PIL ไม่มี glyph ↔ → ใน Kanit** → ใช้คำไทยแทน (libass ใช้ fallback ได้ แต่ PIL ไม่ได้)
6. **การ์ดบังหน้าเมื่อซูมแรง/ผู้พูดโน้มตัว** → ยก anchor (0.38→0.75) / ตอนนี้ใช้ face tracking อัตโนมัติ
7. **การ์ดเลยลงไปในโซน UI ล่างของ TikTok** (y 1574) → มาตรฐานใหม่ y ≤1440 (จากการค้นคว้า safe zone)
8. **ซับชนการ์ด/CTA** เพราะเช็กแค่เวลาเริ่ม → เช็กการทับซ้อนทั้งช่วง
9. **ซับคร่อมประโยค** → ตัดชุดที่ . ! ? และคำลงท้ายไทย
10. **คำหายจากซับ** เพราะเวลาคำของ Whisper คลาดเข้าไปในช่วงเงียบที่ถูกตัด → ทิ้งเฉพาะคำในช่วง "พูดซ้ำ/skip", คำอื่นดึงเข้าขอบ
11. **ECG/กราฟิกทับพาดหัว** → ตรวจ preview ทุกการ์ดก่อน render เต็ม
12. **OpenCV 5 ไม่มี CascadeClassifier** → pin `opencv-python-headless<5`
13. **espeak ภาษาไทย Whisper ฟังไม่ออก** → ทดสอบกลไกด้วยอังกฤษ; ภาษาไทยต้องทดสอบกับเสียงคนจริง
14. **background job ถูกฆ่าเมื่อคำสั่งจบ** → render แบบ foreground (timeout ≥10 นาที)
15. **footer `position:fixed` ใน PDF วางทับหัวข้อ** → ห้ามใช้; `h2 {break-after: avoid}`
16. **`rm` กับตัวแปร** ถูกบล็อกโดย safety check → ใช้ `"${P:?}"` หรือ path ตรง
17. **loudnorm linear บางครั้งได้ -14.5 ถึง -14.7** (ไม่ถึง -14 เป๊ะ) → ยอมรับได้ (TikTok ทำ normalization เอง)

---

## 9. สิ่งที่ "ยังไม่ได้พิสูจน์" (ความเสี่ยงของรากฐาน)

| เรื่อง | สถานะ | วิธีพิสูจน์ |
|---|---|---|
| `auto_edit` กับ **เสียงพูดไทยจริง** | ❌ ยังไม่ได้ทดสอบ (ทดสอบแค่อังกฤษสังเคราะห์) | รันกับคลิปจริง 1 คลิป (เช่นคลิป 9 สัญญาณ ถ้าอนุญาต) |
| ตัดคำไทย + เวลาต่อคำ (char-interpolation) | ตรรกะผ่าน แต่ความแม่นของเวลาไฮไลต์คาราโอเกะยังไม่วัด | ดูเฟรมไฮไลต์เทียบเสียง |
| Face tracking กับคนจริง | ❌ (ภาพทดสอบไม่มีหน้า) | คลิปจริง |
| ตรวจพูดซ้ำภาษาไทย (5-gram) | ❌ | คลิปที่มีเทคซ้ำจริง |
| B-roll ไฟล์ผู้ใช้ (pip/full) | ❌ | แนบภาพ/คลิปทดสอบ |
| ขนาดฟอนต์จาก OCR (ตัวคูณใหม่) | ❌ | analyze_ref ซ้ำ |
| ตรวจเพลงในเรฟ | ประมาณการ | เรฟที่มี/ไม่มีเพลง |
| Preset สไตล์ครีเอเตอร์ | อิงบทความ vendor ไม่ใช่การวัดคลิปจริง | วิเคราะห์คลิปเรฟจริงของครีเอเตอร์ |

---

## 10. มาตรฐานและที่มา

| มาตรฐาน | ค่า | ที่มา |
|---|---|---|
| Hook | ข้อความขึ้น ≤0.3 วิ, คนตัดสินใจ ~2 วิ | Opus/CapCut 2026 (vendor) |
| ตัดเงียบ | ≥0.2–0.3 วิ เหลือ ~0.1 วิ | ความต้องการผู้ใช้ + ทดลองจริง |
| ความยาว | 35–55 วิ | ความต้องการผู้ใช้ |
| Safe zone | บน 130 · ล่าง y≤1440 · ขวา x≤930 | ค่าอนุรักษ์นิยมจาก 4+ แหล่ง (ไม่มีสเปกทางการ) |
| Loudness | -14 LUFS, TP ≤ -1.5 | ค่าที่ใช้กันมาก (TikTok ไม่ประกาศ) |
| เพลง vs เสียงพูด | -17 ถึง -20 dB + ducking | แหล่งให้ 12–18 dB → เลือกปลอดภัยกว่าสำหรับคลิปพูด |
| ซับ | คำต่อคำ/คาราโอเกะ, เน้น 1–3 คำ, คำ punchline | บทความ caption 2026 |
| สี | ฟ้าอ่อน #7DD3FC → น้ำเงิน #1E46B8 → ชมพูอ่อน #F9A8D4, navy #122A6B | ความต้องการผู้ใช้ |

---

## 11. ปุ่มที่ปรับได้ (สำหรับผู้ใช้ตัดสินใจ)

1. **Preset เริ่มต้น** (ตอนนี้ clean-pastel) — อยากให้ค่าเริ่มต้นเป็นสไตล์ไหน?
2. **ความถี่การตัด** `cut.max_gap` (0.18 เร็วมาก ↔ 0.35 ธรรมชาติ)
3. **ความแรงซูม** `zoom.levels`, `emphasis_punch`
4. **ซับ**: style / ขนาด / จำนวนคำ / ตัดคำลงท้าย (`drop_particles`: ค่ะ ครับ นะ)
5. **เสียง**: whoosh ทุกคัตหรือไม่, ระดับ SFX, pack เสียง
6. **เพลง**: เปิด/ปิด, mood, BPM, ระดับ
7. **สี**: เกรด (contrast/saturation/warmth) หรือให้ตามเรฟ
8. **ระดับอัตโนมัติ**: (a) อัตโนมัติเต็ม ไม่มี creative pass, (b) มาตรฐานปัจจุบัน — Claude แก้ซับ+hook+การ์ด, (c) ส่งแผน 12 หัวข้อให้อนุมัติก่อน render
9. **สิ่งที่ส่งมอบ**: MP4 อย่างเดียว / + SRT, ปก, แคปชั่น, cue sheet, แผน 12 หัวข้อ
10. **ภาษา**: ไทยอย่างเดียว / ไทย+อังกฤษ (ซับสองภาษา ยังไม่มี)

---

## 12. ข้อเสนอพัฒนาต่อ (เรียงตามผลต่อคุณภาพ)

| # | งาน | ทำไม | ความยาก |
|---|---|---|---|
| 1 | **ทดสอบ/จูนกับคลิปพูดไทยจริง 3–5 คลิป** | รากฐานยังไม่ถูกพิสูจน์กับภาษาไทยจริง | ต่ำ (ต้องมีคลิป) |
| 2 | **แก้สิทธิ์ GitHub แล้ว push** | งานทั้งหมดเสี่ยงหายเมื่อเซสชันปิด | ผู้ใช้ทำ |
| 3 | โมเดลถอดเสียงใหญ่ขึ้น (medium/large-v3) ถ้าหาแหล่งบน npm/PyPI ได้ | ความแม่นภาษาไทย = คุณภาพซับ | กลาง |
| 4 | คลังเรฟ: วิเคราะห์คลิปเรฟจริงที่ผู้ใช้ชอบ → สร้าง preset ส่วนตัว | ได้สไตล์ "ของผู้ใช้" แทนสไตล์ฝรั่ง | ต่ำ |
| 5 | การ์ดแบบอื่นใน auto_edit (กราฟ, เกจ, A→B, ตัวเลขนับ) ย้ายจาก 9-signals มาเป็น generic | ภาพอธิบายหลากหลายขึ้น | กลาง |
| 6 | ซับลบคำฟุ่มเฟือย (เอ่อ อ่า แบบว่า) อัตโนมัติ | กระชับขึ้น | ต่ำ |
| 7 | Beat-sync: วางคัต/การ์ดให้ตรงจังหวะเพลง | ความรู้สึกพรีเมียม | กลาง |
| 8 | ทำหลายเวอร์ชันอัตโนมัติ (สั้น 30 วิ / ยาว / ไม่มีเพลง) | ทดสอบ A/B บนแพลตฟอร์ม | ต่ำ |
| 9 | Face mesh/MediaPipe แทน Haar | หน้าเอียง/หันข้าง แม่นกว่า | กลาง |
| 10 | ปก (thumbnail) อัตโนมัติ: เฟรมหน้าชัด + ข้อความ hook | ส่งมอบครบในคลิกเดียว | ต่ำ |

---

## 13. คำสั่งอ้างอิงด่วน

```bash
cd video-toolkit && ./setup.sh && ./check_system.sh                     # เตรียมระบบ (12/12)
tools/edit_like.sh <clip> <ref|preset|hormozi|abdaal|codie|minimal|pastel> <name> th --plan-only
python3 -I tools/auto_edit.py projects/<name> --preset <p> [--ref projects/<name>/ref/style_profile.json]
python3 -I tools/analyze_ref.py <ref.mp4> <out_dir> --lang th
tools/measure.sh <video> · tools/silences.sh <video> · tools/contact_sheet.sh <video> <out.jpg> 2
node tools/make_pdf.js docs/system_guide.html docs/AI-Video-Production-System.pdf
git bundle create video-production-system.bundle 496bb6d..HEAD           # สำรองเมื่อ push ไม่ได้
```

---

## 14. Tier 0 foundation (2026-11-16) — routing, contracts, settings

- **Cascading Model Routing**: Tier 0 = เซสชันหลัก (architect + dispatcher) · Tier 1 opus = `01-director-orchestrator`, `02-visual-qa-critic` · Tier 2 sonnet = `03-asr-thai-transcriber`, `04-thai-dedup-cutter`, `05-cv-face-tracker`, `06-graphics-broll-compositor`, `07-ffmpeg-render-engineer` · Tier 3 haiku = `Explore`, `09-test-runner`, `10-bundle-guardian`
- **spawn depth = 1** (`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`): subagent สั่ง subagent ต่อไม่ได้ → Tier 0 dispatch ทุก tier เอง; Opus ให้ "แผนแก้" กลับมา
- agent ใหม่ใน `.claude/agents/` ถูกโหลดตอนเริ่มเซสชันเท่านั้น → ในเซสชันที่สร้างไฟล์ ใช้ `general-purpose` + `model` + ให้อ่านไฟล์ role เอง
- Escalation: Sonnet ล้ม 2 รอบติด · `collision_count > 0` หลังแก้ 1 รอบ · ปัญหาข้ามโมดูล
- สัญญาโมดูล: `docs/INTERFACES.md` (asr / dedup / face / layout / qa_visual / auto_edit) · ข้อมูลส่งต่อ: `pipeline_manifest.json` (`docs/schemas/`)
- `presets/user_settings.json`: automation_level 1/2/3 (ค่าเริ่มต้น 2), default_preset `thai-clear`, knobs 10 ตัว, qa thresholds (margin 24 px, face pad 35 %, ASR gap -35 dBFS ≥2 s)
- Visual QA Protocol: `artifacts/qa/audio_diagnostics.png` + `contact_sheet.png` ทุก render
- preset ส่วนตัว: `tools/make_user_preset.py <ref.mp4> <name>` → `presets/user/<name>.json` → ใช้ `edit_like.sh <clip> user/<name> <project>`
