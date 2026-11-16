"""Face tracking (OpenCV Haar) + zoom-aware 9:16 windows and face boxes in output pixels.
Source px = original clip pixels; output px = final out_w x out_h."""
import cv2

PAD = 0.35          # total growth of w/h around centre
PAD_UP = 0.15       # extra of h upward (hair / forehead)
ALPHA = 0.35        # EMA
HOLD_S = 1.0


def _cascades():
    d = cv2.data.haarcascades
    return (cv2.CascadeClassifier(d + "haarcascade_frontalface_default.xml"),
            cv2.CascadeClassifier(d + "haarcascade_profileface.xml"))


def _detect(gray, front, prof):
    H, W = gray.shape
    ms = max(24, int(W * 0.12))
    det = front.detectMultiScale(gray, 1.1, 5, minSize=(ms, ms))
    if len(det):
        return [tuple(map(float, b)) for b in det]
    out = [tuple(map(float, b)) for b in prof.detectMultiScale(gray, 1.1, 5, minSize=(ms, ms))]
    if not out:
        fl = cv2.flip(gray, 1)
        out = [(W - x - w, y, w, h) for x, y, w, h in
               (tuple(map(float, b)) for b in prof.detectMultiScale(fl, 1.1, 5, minSize=(ms, ms)))]
    return out


def _pad(b, W, H):
    x, y, w, h = b
    cx, cy = x + w / 2, y + h / 2
    nw, nh = w * (1 + PAD), h * (1 + PAD)
    cy -= PAD_UP * h / 2          # shift so the box grows upward by PAD_UP*h
    nh += PAD_UP * h
    return [cx, cy, nw, nh]


def _to_box(c, W, H):
    cx, cy, w, h = c
    x0, y0 = max(0.0, cx - w / 2), max(0.0, cy - h / 2)
    x1, y1 = min(float(W), cx + w / 2), min(float(H), cy + h / 2)
    return [round(x0, 1), round(y0, 1), round(x1 - x0, 1), round(y1 - y0, 1)]


def track(path, step=0.25):
    cap = cv2.VideoCapture(path)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    dur = n / fps if n > 0 else 0.0
    front, prof = _cascades()
    out, state, last_t = [], None, None   # state = [cx, cy, w, h] smoothed
    t = 0.0
    while t < dur - 1e-6:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ok, fr = cap.read()
        if not ok:
            break
        gray = cv2.equalizeHist(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY))
        dets = _detect(gray, front, prof)
        pick = None
        if dets:
            if state is not None:   # prefer detection close to the current track, else largest
                near = [d for d in dets if abs(d[0] + d[2] / 2 - state[0]) < state[2] * 1.2
                        and abs(d[1] + d[3] / 2 - state[1]) < state[3] * 1.2]
                dets = near or dets
            pick = max(dets, key=lambda d: d[2] * d[3])
        if pick is not None:
            m = _pad(pick, W, H)
            if state is None:
                state = m
            else:
                state = [state[i] + ALPHA * (m[i] - state[i]) for i in range(4)]
            last_t = t
            out.append({"t": round(t, 3), "box": _to_box(state, W, H)})
        elif state is not None and last_t is not None and t - last_t <= HOLD_S + 1e-6:
            out.append({"t": round(t, 3), "box": _to_box(state, W, H)})
        else:
            state = None
            out.append({"t": round(t, 3), "box": None})
        t += step
    cap.release()
    return out


def window_for(face_box, src_w, src_h, zoom, face_y=0.40, out_w=1080, out_h=1920):
    ar = out_w / out_h
    w0 = min(float(src_w), src_h * ar)
    h0 = w0 / ar
    z = max(1.0, float(zoom))
    w, h = w0 / z, h0 / z
    if face_box is None:
        x0 = (src_w - w) / 2
        y0 = (src_h - h) * 0.38
    else:
        cx = face_box[0] + face_box[2] / 2
        cy = face_box[1] + face_box[3] / 2
        x0 = cx - w / 2
        y0 = cy - face_y * h
    x0 = min(max(0.0, x0), src_w - w)
    y0 = min(max(0.0, y0), src_h - h)
    return [x0, y0, w, h]


def to_output(box_src, window, out_w=1080, out_h=1920):
    s = out_w / window[2]
    x0 = (box_src[0] - window[0]) * s
    y0 = (box_src[1] - window[1]) * s
    x1 = (box_src[0] + box_src[2] - window[0]) * s
    y1 = (box_src[1] + box_src[3] - window[1]) * s
    x0, x1 = max(0.0, x0), min(float(out_w), x1)
    y0, y1 = max(0.0, y0), min(float(out_h), y1)
    return [x0, y0, max(0.0, x1 - x0), max(0.0, y1 - y0)]


def segment_face_out(track, a, b, win0, win1, out_w=1080, out_h=1920):
    pts = [p for p in track if a - 1e-9 <= p["t"] <= b + 1e-9 and p["box"] is not None]
    if not pts:
        return None
    mid = (a + b) / 2
    xs0, ys0, xs1, ys1 = [], [], [], []
    for p in pts:
        o = to_output(p["box"], win0 if p["t"] < mid else win1, out_w, out_h)
        if o[2] <= 0 or o[3] <= 0:
            continue
        xs0.append(o[0]); ys0.append(o[1]); xs1.append(o[0] + o[2]); ys1.append(o[1] + o[3])
    if not xs0:
        return None
    x0, y0, x1, y1 = min(xs0), min(ys0), max(xs1), max(ys1)
    return [x0, y0, x1 - x0, y1 - y0]
