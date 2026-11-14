# AI Video Editor research — 2026-11-14

## เครื่องมือ AI ตัดคลิปในตลาด (ใช้เป็น benchmark ฟีเจอร์)
- **OpusClip / Vizard**: long→short อัตโนมัติ, ซับ, รีเฟรม — จุดแข็งคือ "clip finding" จากคลิปยาว
- **CapCut**: มือถือ, auto captions, เทมเพลตเทรนด์ (beat sync, speed ramp)
- **Descript**: ตัดต่อจากข้อความ (แก้ transcript = ตัดวิดีโอ), ลบ filler words
- **Submagic / SendShort / Quso / Choppity**: preset สไตล์ครีเอเตอร์ (Hormozi, Ali Abdaal, Codie Sanchez…), word-by-word captions, auto zoom
- **invideo agent / ChatCut**: "match a reference video" — จับจังหวะตัด สไตล์ซับ ตำแหน่ง แล้ว map ไปยังจังหวะที่เทียบเท่า (ไม่ใช่ timestamp เดิม)
→ ระบบเราทำ: preset สไตล์ + วิเคราะห์เรฟเชิงตัวเลข + creative pass โดย Claude (สิ่งที่เครื่องมืออัตโนมัติขาด: hook/การ์ดอธิบายเนื้อหา)

## สไตล์ครีเอเตอร์ (ข้อมูลจากบทความ breakdown — vendor, ใช้เป็นแนวทาง)
- **Alex Hormozi**: talking head กล้องเดียว, ซับคำต่อคำตัวใหญ่ ไฮไลต์เหลือง (บางแหล่ง: พื้นเข้ม), jump cut ทุก 1–3 วิ, punch zoom, B-roll เสริมความหมาย, SFX: แหล่งขัดกัน (บางแหล่งว่าไม่ใส่ whoosh เพราะเสียงพูดนำ, เพลงเบา) → preset `bold-hormozi`
- **Ali Abdaal**: เกรดจืด/ขาวดำ + สีเน้นเหลือง, ซับคำต่อคำที่พูดแล้วจาง, โทนอ่านง่าย → `calm-abdaal`
- **Codie Sanchez**: ตัวหนา sans-serif สีขาว ไม่มีขอบ ใหญ่ กลาง-ล่าง, hook เป็นข้อความหนัก, ฉากอบอุ่น → `codie-bold`

## หลักที่ได้ (ใช้ใน presets/skills)
- ซับคำต่อคำ/คาราโอเกะ = สไตล์หลักของ short-form; เน้นไม่เกิน 1–3 คำต่อจังหวะ; เน้นคำ punchline ไม่ใช่คำเกริ่น
- Hook 2–5 คำบนจอ; ปกติ 3–7 คำ/บรรทัด; ซับห้ามบังหน้า/มือ/วัตถุสำคัญ
- คอนเทนต์สอน → ซับเป็นวลี (เข้าใจทั้งประโยค) ดีกว่าคำเดี่ยว
- Pattern interrupt (zoom/cut/SFX/text pop) — แหล่งให้ช่วง 2–3 วิ ถึง 5–7 วิ; อย่าตัดตามนาฬิกา ให้ตามจังหวะเนื้อหา
- B-roll ควรอธิบายสิ่งที่พูด และใช้ปิด jump cut ได้
- Pipeline โอเพนซอร์สที่คนใช้: faster-whisper word timestamps + silencedetect/Silero VAD + FFmpeg burn captions (ตรงกับระบบเรา)
- การวัดเรฟ: PySceneDetect/scene score → shot length, cuts/min (ไม่มีมาตรฐานอุตสาหกรรม → วัดจากเรฟจริงแต่ละตัว)

## Sources
https://vizard.ai/blog/best-ai-video-editors-2 · https://www.opus.pro/blog/best-ai-video-editors · https://magichour.ai/blog/best-ai-video-editing-tools-for-short-form-content · https://blog.videogen.io/ai-video-editors-compared-2026-videogen-vs-capcut-vs-descript/ ·
https://riverside.com/blog/hormozi-style-videos · https://www.choppity.com/tools/recreate-video-editing-style/alex-hormozi/ · https://gotranscript.com/public/mastering-youtube-shorts-capcut-tutorial-for-ali-abdaal-alex-hormozi-and-cody-sanchez-styles · https://www.submagic.co/blog/make-captions-like-ali-abdaal · https://www.choppity.com/tools/recreate-video-editing-style/codie-sanchez/ ·
https://invideo.io/blog/match-reference-video-editing-style-chatgpt/ · https://chatcut.io/blog/how-to-recreate-a-viral-video-style · https://sharedcontext.ai/skills/external/Surojit16/video-editing-2 · https://flaviocopes.com/cut-silence-videos ·
https://fluxnote.io/guides/faceless-shorts-text-overlay-tips-2026 · https://eliro.pro/blog/12-caption-styles-increase-watch-time · https://subscribr.ai/youtube-strategy/editing-youtube-shorts-more-engagement · https://www.scenedetect.com/docs/cli.html · https://www.capcut.com/help/latest-capcut-editing-trends
(หมายเหตุ: หน้า YouTube/gotranscript/choppity/skool เปิดอ่านตรงไม่ได้จากเครื่องคลาวด์ — ใช้สรุปจากผลค้นหา)
