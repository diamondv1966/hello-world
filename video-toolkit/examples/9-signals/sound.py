import sys, os, wave, numpy as np
D=sys.argv[1]; V=sys.argv[2]; sys.path.insert(0,V); from timeline import *
SR=48000; N=int((TOTAL+0.3)*SR); T=np.arange(N)/SR
rng=np.random.default_rng(11)
def lp(x,fc):
    X=np.fft.rfft(x); f=np.fft.rfftfreq(len(x),1/SR); return np.fft.irfft(X/np.sqrt(1+(f/fc)**4),len(x))
def hp(x,fc):
    X=np.fft.rfft(x); f=np.fft.rfftfreq(len(x),1/SR); r=(f/fc)**2; return np.fft.irfft(X*r/np.sqrt(1+r**2),len(x))
def bp(x,lo,hi): return hp(lp(x,hi),lo)
def env(n,a,d): t=np.arange(n)/SR; return np.minimum(1,t/max(a,1e-4))*np.exp(-t/d)
def conv(x,ir):
    n=len(x)+len(ir)-1; L=1<<(n-1).bit_length()
    return np.fft.irfft(np.fft.rfft(x,L)*np.fft.rfft(ir,L),L)[:len(x)]
def make_ir(sec,seed):
    r=np.random.default_rng(seed); n=int(sec*SR); t=np.arange(n)/SR
    ir=r.standard_normal(n)*np.exp(-t/(sec/6.5)); ir=lp(ir,6000); ir[:int(.012*SR)]=0; return ir/np.sqrt(np.sum(ir**2))
IRL,IRR=make_ir(2.2,1),make_ir(2.2,2)
def verb(st,wet=0.25):   # st: (N,2)
    return st+wet*np.stack([conv(st[:,0],IRL),conv(st[:,1],IRR)],1)
def pan(x,p): # p -1..1
    a=(p+1)*np.pi/4; return np.stack([x*np.cos(a),x*np.sin(a)],1)
def place(buf,sig,t,g=1.0):
    i=int(round(t*SR)); 
    if i<0: sig=sig[-i:]; i=0
    j=min(len(buf),i+len(sig)); 
    if i<len(buf): buf[i:j]+=sig[:j-i]*g
def mf(n): return 440*2**((n-69)/12)
def norm(x,p=0.9): return x/(np.max(np.abs(x))+1e-9)*p

# ================= SFX library =================
def sfx_whoosh(d=0.55):
    n=int(d*SR); t=np.arange(n)/SR; x=rng.standard_normal(n)
    y=np.zeros(n); seg=1024
    for i in range(0,n,seg):  # time-varying bandpass via blocks
        c=400+5000*np.sin(np.pi*min(1,(i/n)))**2
        blk=x[max(0,i-512):i+seg+512]
        yy=bp(blk,c*0.5,c*1.6); off=i-max(0,i-512); y[i:i+seg]=yy[off:off+seg][:len(y[i:i+seg])]
    e=np.sin(np.pi*t/d)**3; y=y*e
    st=np.stack([y*np.linspace(1,0.3,n),y*np.linspace(0.3,1,n)],1)  # L->R sweep
    return norm(st,0.8)
def sfx_click():
    n=int(.05*SR); t=np.arange(n)/SR
    x=np.sin(2*np.pi*2400*t)*env(n,.0003,.006)+0.4*lp(rng.standard_normal(n),5000)*env(n,.0002,.002)
    return norm(pan(lp(x,7000),0),0.7)
def sfx_pop():
    n=int(.12*SR); t=np.arange(n)/SR
    fr=380+620*(1-np.exp(-t/0.018)); x=np.sin(2*np.pi*np.cumsum(fr)/SR)*env(n,.0015,.03)
    return norm(pan(lp(x,3500),0),0.7)
def sfx_impact():
    n=int(1.6*SR); t=np.arange(n)/SR
    sub=np.sin(2*np.pi*np.cumsum(42+55*np.exp(-t/0.06))/SR)*env(n,.003,.38)
    body=lp(rng.standard_normal(n),700)*env(n,.002,.06)*1.5
    x=pan(sub+body,0); x=verb(x,0.35); return norm(x,0.9)
def sfx_riser(d=1.6):
    n=int(d*SR); t=np.arange(n)/SR; p=(t/d)
    noise=sum(bp(rng.standard_normal(n),f0,f0*2)*np.clip((p-k*0.25)*4,0,1) for k,f0 in enumerate([500,1200,2600,5000]))
    tones=sum(np.sin(2*np.pi*np.cumsum(mf(m)*(1+0.5*p**2))/SR) for m in (76,83,88))/3
    x=(0.5*noise+0.35*tones)*p**2.2*(1-np.exp(-(d-t)/0.01))
    st=np.stack([x,np.roll(x,int(.011*SR))],1); return norm(verb(st,0.3),0.85)
def bell(m,d=1.2):
    n=int(d*SR); t=np.arange(n)/SR; f=mf(m)
    return (np.sin(2*np.pi*f*t+1.2*np.exp(-t/0.15)*np.sin(2*np.pi*f*3.5*t)))*env(n,.004,.35)
def sfx_notify():
    n=int(1.6*SR); x=np.zeros(n)
    a=bell(88); b=bell(95); x[:len(a)]+=a; i=int(.13*SR); x[i:i+len(b)]+=b[:n-i]
    st=np.stack([x,np.roll(x,int(.006*SR))],1); return norm(verb(st,0.4),0.8)
def sfx_shimmer():
    n=int(1.4*SR); x=np.zeros((n,2))
    for k,m in enumerate([84,88,91,96,100]):
        b=bell(m,1.0)*0.6; i=int(k*0.045*SR); x[i:i+len(b)]+=pan(b,-0.6+0.3*k)[:n-i]
    return norm(verb(x,0.5),0.8)
LIB={"whoosh_soft":sfx_whoosh(),"click_soft":sfx_click(),"pop_soft":sfx_pop(),"impact_subtle":sfx_impact(),
     "riser_ambient":sfx_riser(),"notification_soft":sfx_notify(),"shimmer":sfx_shimmer()}
os.makedirs(f"{V}/SFX_pack",exist_ok=True)
def wav(path,st):
    s=(np.clip(st,-1,1)*32767).astype("<i2")
    with wave.open(path,"wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(s.tobytes())
for k,v in LIB.items(): wav(f"{V}/SFX_pack/sfx_{k}.wav",v)

# ================= SFX placement =================
S=np.zeros((N,2)); cue=[]
def put(name,t,g,why):
    place(S,LIB[name],t,g); cue.append((t,name,g,why))
h0,h1=GT["hook"]
put("whoosh_soft",0.0,0.30,"เปิดคลิป ดึงสายตา")
put("shimmer",0.30,0.32,"คำว่า 'เตือนคุณ!' เด้งขึ้น")
put("pop_soft",1.70,0.40,"ข้อความ '9 สัญญาณ' ขึ้น")
for k,(n,_,_) in enumerate(ITEMS):
    A=GT[n][0]+0.04
    if n!="9": put("whoosh_soft",A-0.22,0.17,f"เปลี่ยนเข้าข้อ {n}")
    put("click_soft",A,0.45,f"เลข {n} ขึ้น + progress bar")
    put("pop_soft",A+0.85,0.30,f"กล่องสาเหตุข้อ {n} ขึ้น")
put("riser_ambient",GT["9"][0]-1.55,0.28,"บิลด์อารมณ์ก่อนข้อ 9 (ข้อหนักสุด)")
put("impact_subtle",GT["9"][0]+0.04,0.55,"ข้อ 9 เน้นหนัก")
t0,_=GT["teaser"]
put("whoosh_soft",t0-0.25,0.25,"เข้าช่วงเกริ่นตอนต่อไป")
put("pop_soft",t0+1.7,0.40,"'ดูตอนต่อไป' ขึ้น")
c0,c1=GT["cta"]
put("notification_soft",c0+0.35,0.45,"ปุ่มกดติดตามขึ้น")
put("shimmer",c1-1.2,0.25,"ปิดท้ายตอนโบกมือ")

# ================= MUSIC (original, 96 BPM, Fmaj7-G6-Em7-Am7) =================
BPM=96; beat=60/BPM; bar=4*beat
drop=GT["1"][0]+0.04; T0=drop-2*bar
prog=[(41,[57,60,64,65]),(43,[59,62,64,67]),(40,[55,59,62,64]),(45,[55,60,64,67])]
EP=np.zeros((N,2)); PAD=np.zeros((N,2)); BASS=np.zeros(N); DR=np.zeros((N,2)); SP=np.zeros((N,2))
def ep_note(m,d,vel):
    n=int(d*SR); t=np.arange(n)/SR; f=mf(m)
    x=np.sin(2*np.pi*f*t+1.8*np.exp(-t/0.25)*np.sin(2*np.pi*f*t))*env(n,.004,.9)*(1-np.exp(-(d-t)/.05))
    return x*vel*(1+0.15*np.sin(2*np.pi*4.5*t))
def saw(f,n): t=np.arange(n)/SR; return 2*((t*f)%1)-1
kick=np.sin(2*np.pi*np.cumsum(48+70*np.exp(-np.arange(int(.35*SR))/SR/0.03))/SR)*env(int(.35*SR),.002,.16)
rim=bp(rng.standard_normal(int(.08*SR)),1500,6000)*env(int(.08*SR),.0005,.012)+np.sin(2*np.pi*1700*np.arange(int(.08*SR))/SR)*env(int(.08*SR),.0005,.01)*0.5
shk=hp(rng.standard_normal(int(.07*SR)),6000)*env(int(.07*SR),.006,.02)
teaser=GT["teaser"][0]; cta=GT["cta"][0]; i9=GT["9"][0]
for b in range(-3,40):
    bt=T0+b*bar
    if bt>TOTAL: break
    root,ch=prog[b%4]; full=(drop-0.01<=bt<teaser-0.05) or (bt>=cta-bar*0.5 and bt<TOTAL-1.5)
    n=int(bar*SR)
    pad=sum(saw(mf(m)*(1+d),n) for m in ch for d in (-0.004,0.004))/8
    pad=pad*np.minimum(1,np.arange(n)/SR/0.6)*np.minimum(1,(n-np.arange(n))/SR/0.3)
    place(PAD,pan(pad,-0.3),bt,0.5); place(PAD,pan(np.roll(pad,300),0.3),bt,0.5)
    # EP: chord on 1, soft re-strike on 2&, top-note melody on 3 / 4&
    for off,vel,notes in ((0,1.0,ch),(1.5*beat,0.55,ch[1:]),(2.5*beat,0.5,[ch[-1]+12]),(3.5*beat,0.45,[ch[-2]+12])):
        for m in notes: place(EP,pan(ep_note(m,1.3,vel*0.25),(m-62)/30),bt+off)
    for off,d in ((0,1.2*beat),(1.5*beat,0.4*beat),(2*beat,1.3*beat),(3.5*beat,0.4*beat)):
        nn=int(d*SR); tt=np.arange(nn)/SR
        place(BASS,np.sin(2*np.pi*mf(root)*tt)*np.minimum(1,tt/0.01)*np.exp(-tt/0.6)*(1-np.exp(-(d-tt)/0.02)),bt+off)
    if full:
        for k in range(4):
            place(DR,pan(kick,0),bt+k*beat,0.0 if k in (1,3) else 0.9)
            if k in (1,3): place(DR,pan(rim,0.15),bt+k*beat,0.32)
        place(DR,pan(kick,0),bt+2.5*beat,0.45)
        for s in range(16):
            sw=0.018 if s%2 else 0
            place(DR,pan(shk,0.35),bt+s*beat/4+sw,0.14 if s%2 else 0.08)
    if b%2==0 and bt>=-0.1:  # sparkle arp every 2 bars
        for k,m in enumerate([ch[0]+24,ch[2]+24,ch[3]+24]):
            place(SP,pan(bell(m,0.9)*0.10,-0.5+0.5*k),bt+3*beat+k*beat/3)
BASS=lp(BASS,400); PADf=np.stack([lp(PAD[:,0],1600),lp(PAD[:,1],1600)],1)
mus=verb(EP*0.9+PADf*0.22+SP,0.28)+pan(BASS,0)*0.55+DR*0.85
# intro filter-sweep opening into drop, breakdown filter at teaser
w=np.clip((T-(drop-1.2))/1.2,0,1); w2=1-np.clip((T-teaser)/0.4,0,1)*np.clip((cta-0.3-T)/0.3,0,1)*0.6
dark=np.stack([lp(mus[:,0],900),lp(mus[:,1],900)],1)
mix_w=(w*w2)[:,None]
mus=dark*(1-mix_w)+mus*mix_w
mus*=(np.minimum(1,T/0.35)*np.clip((TOTAL+0.3-T)/2.0,0,1))[:,None]
wav(f"{V}/music_original.wav",norm(mus,0.9)); wav(f"{V}/sfx_track.wav",norm(S,0.9)*0+np.clip(S,-1,1))
with open(f"{V}/sfx_cues.tsv","w") as fh:
    for t,nm,g,why in sorted(cue): fh.write(f"{t:6.2f}\t{nm}\t{why}\n")
print("ok", len(cue),"cues; drop",round(drop,2))
