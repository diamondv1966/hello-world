import subprocess, sys
D=sys.argv[1]; V=sys.argv[2]
sys.path.insert(0,V); from timeline import *
def ts(x): return f"{int(x//3600)}:{int(x%3600//60):02d}:{x%60:05.2f}"
# palette (ASS = &HAABBGGRR)
NAVY="&H006B2A12&"; NAVY0="&H006B2A12"; BLUE="&H00F6823B&"; SKY="&H00FCD37D&"; PINK="&H00D4A8F9&"; PINK2="&H00E8CFFB&"; WHITE="&H00FFFFFF&"
hdr=f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Big,KanitXB,112,&H00FFFFFF,&H00FFFFFF,{NAVY0},&H785A1E0A,0,0,0,0,100,100,1,0,1,7,6,8,60,60,250,1
Style: BigPink,KanitXB,150,&H00D4A8F9,&H00FFFFFF,{NAVY0},&H785A1E0A,0,0,0,0,100,100,1,0,1,8,7,8,60,60,250,1
Style: Num,KanitXB,210,&H00D4A8F9,&H00FFFFFF,{NAVY0},&H785A1E0A,0,0,0,0,100,100,0,0,1,9,7,7,70,60,150,1
Style: Sym,KanitXB,112,&H00FFFFFF,&H00FFFFFF,{NAVY0},&H785A1E0A,0,0,0,0,100,100,1,0,1,7,6,7,70,60,150,1
Style: Cause,KanitXB,80,&H00FFFFFF,&H00FFFFFF,&H00B8461E,&H00000000,0,0,0,0,100,100,1,0,3,16,0,7,70,60,150,1
Style: Head,KanitXB,46,&H00FCD37D,&H00FFFFFF,{NAVY0},&H785A1E0A,0,0,0,0,100,100,2,0,1,4,3,8,60,60,160,1
Style: Disc,KanitXB,34,&H00FFFFFF,&H00FFFFFF,{NAVY0},&H785A1E0A,0,0,0,0,100,100,0,0,1,3,2,7,70,60,60,1
Style: CTA,KanitXB,88,&H00FFFFFF,&H00FFFFFF,{NAVY0},&H785A1E0A,0,0,0,0,100,100,1,0,1,7,6,2,60,60,640,1
Style: CTAbox,KanitXB,78,&H00FFFFFF,&H00FFFFFF,&H00F6823B,&H00000000,0,0,0,0,100,100,1,0,3,18,0,2,60,60,520,1
Style: Shape,KanitXB,10,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
ev=[]
def add(st,a,b,txt,layer=0): ev.append(f"Dialogue: {layer},{ts(a)},{ts(b)},{st},,0,0,0,,{txt}")
# premium entrance: slide-up + fade + slight blur-to-sharp
def rise(dy=40,dur=260): return r"{\fad(%d,0)\blur6\t(0,%d,\blur0.6)\fscx92\fscy92\t(0,%d,0.6,\fscx100\fscy100)}"%(dur//2,dur,dur)
def movein(x,y,dy=36,dur=280,an=7): return r"{\an%d\move(%d,%d,%d,%d,0,%d)}"%(an,x,y+dy,x,y,dur)
h0,h1=GT["hook"]
add("Big",h0,h0+1.7, movein(540,250,an=8)+rise()+"ร่างกายกำลัง")
add("BigPink",h0+0.3,h1-0.02, movein(540,385,an=8)+rise(dur=320)+"เตือนคุณ!",1)
add("Big",h0+1.7,h1-0.02, r"{\an8\pos(540,250)}"+r"{\alpha&HFF&\t(0,90,\alpha&H00&)}9 สัญญาณ {\alpha&HFF&\t(170,260,\alpha&H00&)}ที่ห้าม{\alpha&HFF&\t(340,430,\alpha&H00&)}มองข้าม")
i0=GT["1"][0]; i9e=GT["9"][1]
add("Head",i0,i9e,r"{\fad(200,0)}9 สัญญาณร่างกายเตือน")
# progress bar background
BARX,BARY,BARW,BARH=120,232,840,10
add("Shape",i0,i9e,r"{\an7\pos(%d,%d)\p1\1c&HFFFFFF&\1a&H90&\bord0\shad0\fad(200,0)}m 0 0 l %d 0 %d %d 0 %d"%(BARX,BARY,BARW,BARW,BARH,BARH),3)
for k,(n,sym,cause) in enumerate(ITEMS):
    A,B=GT[n]; A+=0.04
    x0=BARX+BARW*k/9; x1=BARX+BARW*(k+1)/9
    col=PINK if k%2==0 else SKY
    add("Shape",A,B,r"{\an7\pos(%d,%d)\p1\1c%s\bord0\shad0\clip(%d,0,%d,1920)\t(0,320,\clip(%d,0,%d,1920))}m 0 0 l %d 0 %d %d 0 %d"%(BARX,BARY,PINK2,0,int(x0),0,int(x1),BARW,BARW,BARH,BARH),4)
    # soft flash on item change
    add("Shape",A,A+0.22,r"{\an7\pos(0,0)\p1\1c&HFFFFFF&\1a&HC8&\bord0\shad0\fad(0,200)}m 0 0 l 1080 0 1080 1920 0 1920",9)
    add("Num",A,B, r"{\an5\pos(135,378)\fscx0\fscy0\frz-12\t(0,170,\fscx118\fscy118\frz3)\t(170,260,\fscx100\fscy100\frz0)}"+n,5)
    add("Sym",A+0.08,B, movein(265,300,dy=30)+rise()+sym,5)
    CS=CARDS[n][0]-0.05
    add("Cause",CS,B, r"{\an7\pos(265,455)\clip(240,0,240,1920)\t(0,320,\clip(240,0,1080,1920))}"+"→ "+cause,5)
add("Disc",GT["1"][0],i9e,r"{\an7\pos(70,600)\fad(300,0)\1a&H30&}ข้อมูลเบื้องต้น ไม่ใช่การวินิจฉัย  มีอาการต่อเนื่องควรพบแพทย์")
t0,t1=GT["teaser"]
add("Big",t0,t1, movein(540,240,an=8)+rise()+"อยากรู้วิธีป้องกัน?")
add("BigPink",t0+1.7,t1, movein(540,380,an=8)+rise(dur=320)+"ดูตอนต่อไป",1)
c0,c1=GT["cta"]
add("CTA",c0,c1, rise()+"ข้อไหนเป็นอยู่? คอมเมนต์บอกหน่อย")
add("CTAbox",c0+0.35,c1, r"{\fscx60\fscy60\t(0,200,\fscx110\fscy110)\t(200,300,\fscx100\fscy100)\t(700,1000,\fscx106\fscy106)\t(1000,1300,\fscx100\fscy100)\t(1700,2000,\fscx106\fscy106)\t(2000,2300,\fscx100\fscy100)\t(2700,3000,\fscx106\fscy106)\t(3000,3300,\fscx100\fscy100)}"+"กดติดตาม ไม่พลาดตอน 2")
open(f"{V}/supers.ass","w").write(hdr+"\n".join(ev)+"\n")

fc=[]; n=len(SEGS)
for i,(a,b,oa,za,zb) in enumerate(SEGS):
    fr=max(1,round((b-a)*30))
    fc.append(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS,fps=30,scale=2160:3840:flags=lanczos,"
              f"zoompan=z='{za:.4f}+({zb-za:.4f})*on/{fr}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)*{(0.75 if GT["9"][0]-0.01<=oa<GT["9"][1]-0.01 else 0.38)}':d=1:s=1080x1920:fps=30,setsar=1[v{i}]")
    fc.append(f"[1:a]atrim={a}:{b},asetpts=PTS-STARTPTS,afade=t=in:d=0.012,afade=t=out:st={b-a-0.015:.3f}:d=0.015[a{i}]")
fc.append("".join(f"[v{i}][a{i}]" for i in range(n))+f"concat=n={n}:v=1:a=1[cv][ca]")
ICONS=[]
fc.append(f"[cv]curves=all='0/0 0.25/0.24 0.5/0.48 0.85/0.80 1/0.94',eq=contrast=1.07:saturation=1.10:brightness=-0.01,colorbalance=bs=0.04:bm=0.012:rs=-0.01:rh=0.012,"
          f"vignette=angle=PI/7,unsharp=5:5:0.55,ass={V}/supers.ass:fontsdir={D}/assets/fonts,format=rgba[base0]")
last="base0"
for k,(nm,S,E) in enumerate(ICONS):
    fc.append(f"[{2+k}:v]format=rgba,fade=in:st={S:.3f}:d=0.28:alpha=1,fade=out:st={E-0.18:.3f}:d=0.18:alpha=1[ic{k}]")
    fc.append(f"[{last}][ic{k}]overlay=x=800:y='640+34*max(0\\,1-(t-{S:.3f})/0.3)+7*sin(2*PI*(t-{S:.3f})/2.4)':enable='between(t,{S:.3f},{E:.3f})':eval=frame[o{k}]")
    last=f"o{k}"
fc.append(f"[{last}]format=yuv420p[vo]")
fc.append("[ca]afftdn=nf=-48,highpass=f=85,equalizer=f=220:t=q:w=1.0:g=1.5,equalizer=f=3200:t=q:w=1.2:g=2.0,equalizer=f=10000:t=h:w=0.7:g=1.5,"
          "deesser=i=0.35,acompressor=threshold=-22dB:ratio=3:attack=6:release=90:makeup=2,aresample=48000[ao]")
cmd=["ffmpeg","-v","error","-y","-i",f"{V}/src.mp4","-i",f"{V}/src.mp4",*sum([["-loop","1","-framerate","30","-t",f"{E+0.1:.2f}","-i",f"{V}/icons/{nm}.png"] for nm,S,E in ICONS],[]),"-filter_complex",";".join(fc),"-map","[vo]","-map","[ao]",
     "-c:v","libx264","-preset","slow","-crf","18","-profile:v","high","-pix_fmt","yuv420p","-r","30","-c:a","pcm_s16le",f"{V}/video_voice.mov"]
subprocess.run(cmd,check=True)
print("TOTAL",round(TOTAL,2)); print({k:(round(a,2),round(b,2)) for k,(a,b) in GT.items()})
