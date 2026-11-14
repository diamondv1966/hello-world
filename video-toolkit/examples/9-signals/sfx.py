import sys, os, wave, subprocess, numpy as np
D=sys.argv[1]; V=sys.argv[2]; sys.path.insert(0,V); from timeline import *
SR=48000; N=int((TOTAL+0.3)*SR)
U=f"{D}/assets/uisfx/sounds"
def load(path):
    raw=subprocess.run(["ffmpeg","-v","error","-i",path,"-ac","2","-ar",str(SR),"-f","f32le","-"],capture_output=True,check=True).stdout
    x=np.frombuffer(raw,np.float32).reshape(-1,2).astype(np.float64); return x/(np.abs(x).max()+1e-9)*0.9
L={  # uisfx (CC0)
 "u_alert":load(f"{U}/glass/notification.mp3"), "u_press":load(f"{U}/soft/press.mp3"),
 "u_step":load(f"{U}/glass/progress-step.mp3"), "u_select":load(f"{U}/soft/select.mp3"),
 "u_swipe":load(f"{U}/cinematic/swipe.mp3"), "u_open":load(f"{U}/dreamy/open.mp3"),
 "u_success":load(f"{U}/glass/success.mp3"), "u_levelup":load(f"{U}/glass/level-up.mp3"),
 "u_achieve":load(f"{U}/dreamy/achievement.mp3"),
}
for k in ["whoosh_soft","impact_subtle","riser_ambient","shimmer"]:   # original synthesized
    L["s_"+k]=load(f"{V}/SFX_pack/sfx_{k}.wav")
def pitch(x,f):
    n=int(len(x)/f); idx=np.arange(n)*f; i0=idx.astype(int); fr=(idx-i0)[:,None]; i1=np.minimum(i0+1,len(x)-1)
    return x[i0]*(1-fr)+x[i1]*fr
for i in range(9): L["u_step_p%d"%i]=pitch(L["u_step"],1+0.07*i)
_t=np.arange(int(.11*SR))/SR; _b=np.sin(2*np.pi*1046*_t)*np.minimum(1,_t/0.004)*np.exp(-_t/0.05)
L["s_beep"]=np.stack([_b,_b],1)*0.8
S=np.zeros((N,2)); cue=[]
def put(n,t,g,why):
    x=L[n]; i=int(round(t*SR)); j=min(N,i+len(x)); S[i:j]+=x[:j-i]*g; cue.append((t,n,why))
put("s_whoosh_soft",0.0,0.26,"เปิดคลิป")
put("u_alert",0.30,0.42,"'เตือนคุณ!' + ไอคอนไซเรน (สื่อถึงการเตือน)")
put("s_shimmer",0.32,0.14,"ประกายเสริม 'เตือนคุณ!'")
put("u_press",1.70,0.40,"'9 สัญญาณ' ขึ้น")
for k,(n,_,_) in enumerate(ITEMS):
    A=GT[n][0]+0.04
    if n!="9":
        put("u_swipe",A-0.20,0.30,f"ทรานสิชันเข้าข้อ {n}")
        put("s_whoosh_soft",A-0.24,0.10,f"ลมเสริมทรานสิชันข้อ {n}")
    put("u_step",A,0.42,f"เลข {n} + progress bar")
    put("u_select",CARDS[n][0]-0.05,0.26,f"กล่องสาเหตุข้อ {n} (wipe)")
    put("s_whoosh_soft",CARDS[n][0]-0.08,0.12,f"การ์ดภาพประกอบข้อ {n} เลื่อนเข้า")
put("s_riser_ambient",GT["9"][0]-1.55,0.26,"บิลด์ก่อนข้อ 9")
put("s_impact_subtle",GT["9"][0]+0.04,0.50,"ข้อ 9 เน้นหนัก")
put("u_levelup",GT["9"][0]+0.95,0.22,"progress bar เต็ม 9/9")
t0,_=GT["teaser"]; c0,c1=GT["cta"]
put("u_swipe",t0-0.22,0.32,"เข้าช่วงเกริ่นตอนต่อไป")
put("u_open",t0+1.7,0.40,"'ดูตอนต่อไป' + ไอคอนหลอดไฟ")
for i in range(9): put("u_step_p%d"%i,t0+0.25+i*0.09,0.20,f"ไอคอนตาราง 3x3 ตัวที่ {i+1}")
for i in range(13): put("u_press",CARDS["9"][0]+0.25+i*0.12,0.10,"เข็มเกจความดันขยับ")
for tb in (0.05,0.33,0.62): put("s_beep",tb,0.16,"เสียงจังหวะหัวใจ ECG")
put("u_success",c0+0.35,0.42,"ปุ่มกดติดตามขึ้น")
put("u_achieve",c1-1.35,0.30,"ปิดท้ายตอนโบกมือ")
s=(np.clip(S,-1,1)*32767).astype("<i2")
with wave.open(f"{V}/sfx_track.wav","wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(s.tobytes())
os.makedirs(f"{V}/SFX_pack",exist_ok=True)
names={"u_alert":"cc0_uisfx_glass_notification","u_press":"cc0_uisfx_soft_press","u_step":"cc0_uisfx_glass_progress-step","u_select":"cc0_uisfx_soft_select",
 "u_swipe":"cc0_uisfx_cinematic_swipe","u_open":"cc0_uisfx_dreamy_open","u_success":"cc0_uisfx_glass_success","u_levelup":"cc0_uisfx_glass_level-up","u_achieve":"cc0_uisfx_dreamy_achievement"}
for k,x in L.items():
    if k.startswith("u_step_p") or k=="s_beep": continue
    nm=names.get(k,"original_"+k[2:]); y=(x*32767).astype("<i2")
    with wave.open(f"{V}/SFX_pack/{nm}.wav","wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(y.tobytes())
with open(f"{V}/SFX_pack/cue_sheet.tsv","w") as f:
    f.write("time_s\tsound\tpurpose\n")
    for t,n,why in sorted(cue): f.write(f"{t:.2f}\t{names.get(n,'original_'+n[2:])}\t{why}\n")
print(len(cue),"cues")
