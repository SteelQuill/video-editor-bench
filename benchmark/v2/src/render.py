#!/usr/bin/env python3
"""v2 benchmark renderer: PIL frames -> libx264 mp4 + synthesized SFX AAC mux."""
import os, sys, math, wave, subprocess, random
from PIL import Image, ImageDraw, ImageFont
import timeline as T

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
OUT_MP4 = os.path.join(ROOT, "benchmark.mp4")
TMP_MP4 = "/tmp/opencode/v2_video_tmp.mp4"
TMP_WAV = "/tmp/opencode/v2_audio.wav"
FONT_DIR = "/usr/share/fonts/truetype/dejavu"

_fcache = {}
def font(size, bold=True):
    size = int(round(size))
    if size not in _fcache:
        name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        _fcache[size] = ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    return _fcache[size]

# ---------------------------------------------------------------- assets ----
_imgs = {}
def load(name):
    if name not in _imgs:
        im = Image.open(os.path.join(ASSETS, name)).convert("RGB")
        if name == "asset_004.jpg":
            pass  # flip decided per segment
        _imgs[name] = im
    return _imgs[name]

_flip_cache = {}
def load_flipped(name):
    if name not in _flip_cache:
        _flip_cache[name] = load(name).transpose(Image.FLIP_LEFT_RIGHT)
    return _flip_cache[name]

# ------------------------------------------------------------- cover crop ---
def photo_frame(seg, absf, zoom_mult=1.0):
    src = load_flipped(seg["asset"]) if seg.get("flip_h") else load(seg["asset"])
    sw, sh = src.size
    t = absf - seg["body"][0]
    m = T._motion(seg, t)
    z = m["z"] * zoom_mult
    s0 = max(T.W / sw, T.H / sh)
    win_w = T.W / (s0 * z)
    win_h = T.H / (s0 * z)
    cx = sw / 2.0 + m["ox"] / (s0 * z)
    cy = sh / 2.0 + m["oy"] / (s0 * z)
    if win_w >= sw:
        cx = sw / 2.0
    else:
        cx = min(max(cx, win_w / 2.0), sw - win_w / 2.0)
    if win_h >= sh:
        cy = sh / 2.0
    else:
        cy = min(max(cy, win_h / 2.0), sh - win_h / 2.0)
    box = (cx - win_w / 2.0, cy - win_h / 2.0, cx + win_w / 2.0, cy + win_h / 2.0)
    box = (max(0.0, box[0]), max(0.0, box[1]), min(float(sw), box[2]), min(float(sh), box[3]))
    return src.resize((T.W, T.H), Image.BILINEAR, box=box)

# ---------------------------------------------------------------- cards -----
def card_frame(seg, absf, text_scale_mult=1.0):
    bg = Image.new("RGB", (T.W, T.H), (16, 16, 20))
    d = ImageDraw.Draw(bg)
    t = absf - seg["body"][0]
    m = T._motion(seg, t)
    sc = m["text_scale"] * text_scale_mult
    name = seg["name"]
    if name == "title_card":
        f1, f2 = font(150 * sc), font(48 * sc)
        s1, s2 = "WEEKEND CUT", "sat — sun"
        w = d.textlength(s1, font=f1)
        d.text(((T.W - w) / 2, 430), s1, font=f1, fill=(235, 235, 235))
        w2 = d.textlength(s2, font=f2)
        d.text(((T.W - w2) / 2, 640), s2, font=f2, fill=(150, 150, 155))
    elif name == "meanwhile_card":
        f1, f2 = font(130 * sc), font(44 * sc)
        s1, s2 = "MEANWHILE", "back at the desk"
        w = d.textlength(s1, font=f1)
        d.text(((T.W - w) / 2, 450), s1, font=f1, fill=(235, 235, 235))
        w2 = d.textlength(s2, font=f2)
        d.text(((T.W - w2) / 2, 650), s2, font=f2, fill=(150, 150, 155))
    elif name == "fin_card":
        f1, f2 = font(170 * sc), font(44 * sc)
        s1, s2 = "FIN", "weekend cut"
        w = d.textlength(s1, font=f1)
        d.text(((T.W - w) / 2, 420), s1, font=f1, fill=(235, 235, 235))
        w2 = d.textlength(s2, font=f2)
        d.text(((T.W - w2) / 2, 660), s2, font=f2, fill=(150, 150, 155))
    else:
        raise KeyError(name)
    return bg

# -------------------------------------------------------------- overlays ----
def apply_overlays(seg, frame, absf):
    if seg["name"] != "creator":
        return frame
    ov = frame.convert("RGBA")
    # lower third
    lo, hi = T.OVERLAYS[0]["frames"]
    if lo <= absf <= hi:
        p = 1.0 if absf >= T.OVERLAYS[0]["slide_frames"][1] else \
            (absf - T.OVERLAYS[0]["slide_frames"][0] + 1) / 6.0
        bar_w, bar_h = 660, 110
        x = int(80 - bar_w * (1 - p))
        strip = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
        sd = ImageDraw.Draw(strip)
        sd.rectangle([0, 0, bar_w, bar_h], fill=(10, 10, 12, 175))
        sd.rectangle([0, 0, 12, bar_h], fill=(255, 160, 0, 255))
        sd.text((40, 28), "the cut — 23:10", font=font(46), fill=(240, 240, 240, 255))
        ov.paste(strip, (x, 880), strip)
    # REC blink
    rlo, rhi = T.OVERLAYS[1]["frames"]
    if rlo <= absf <= rhi:
        period, on = T.OVERLAYS[1]["period"], T.OVERLAYS[1]["on"]
        if (absf - rlo) % period < on:
            strip = Image.new("RGBA", (220, 70), (0, 0, 0, 0))
            sd = ImageDraw.Draw(strip)
            sd.ellipse([10, 20, 50, 60], fill=(230, 40, 40, 255))
            sd.text((68, 18), "REC", font=font(42), fill=(245, 245, 245, 255))
            ov.paste(strip, (60, 50), strip)
    return ov.convert("RGB")

# ------------------------------------------------------------ seg render ----
def render_seg(seg, absf, zoom_mult=1.0, text_mult=1.0):
    if seg["kind"] == "card":
        img = card_frame(seg, absf, text_mult)
    else:
        img = photo_frame(seg, absf, zoom_mult)
    # fades
    fr = T.FADES.get(seg["id"], {})
    mult = 1.0
    if "out" in fr:
        a, b = fr["out"]
        if a <= absf <= b:
            mult = (b - absf) / float(b - a) if b > a else 0.0
            if absf == a:
                mult = 1.0
    if "in" in fr:
        a, b = fr["in"]
        if a <= absf <= b:
            mult = (absf - a) / float(b - a)
            if absf == b:
                mult = 1.0
            else:
                mult = max(mult, 1.0 / (b - a + 1))
    if mult < 1.0:
        img = Image.blend(Image.new("RGB", img.size, (0, 0, 0)), img, mult)
    img = apply_overlays(seg, img, absf)
    return img

# ------------------------------------------------------------ frame comp ----
BLACK = Image.new("RGB", (T.W, T.H), (0, 0, 0))

def flash_frame(kind):
    name = T.A["onion" if kind == "onion" else "book"]
    src = load(name)
    sw, sh = src.size
    s0 = max(T.W / sw, T.H / sh)
    win_w, win_h = T.W / s0, T.H / s0
    box = ((sw - win_w) / 2.0, (sh - win_h) / 2.0, (sw + win_w) / 2.0, (sh + win_h) / 2.0)
    return src.resize((T.W, T.H), Image.BILINEAR, box=box)

def render_frame(absf):
    # full-frame flash inserts
    for kind, (a, b) in T.FLASH_FRAMES.items():
        if kind == "onion" and a <= absf <= b:
            return flash_frame(kind)
    for bl in T.RENDER_BLENDS:
        a, b = bl["frames"]
        if a <= absf <= b:
            if "flash_mid" in bl:
                _, fa, fb = bl["flash_mid"]
                if fa <= absf <= fb:
                    return flash_frame("book")
            k = absf - a
            d = b - a + 1
            p = (k + 1) / float(d)
            seg_out = T.seg_by_name(bl["out"])
            seg_in = T.seg_by_name(bl["in"])
            if bl["type"] == "dissolve":
                fo = render_seg(seg_out, absf)
                fi = render_seg(seg_in, absf)
                return Image.blend(fo, fi, p)
            if bl["type"] == "zoom":
                fo = render_seg(seg_out, absf, zoom_mult=1.0 + 0.25 * p)
                fi = render_seg(seg_in, absf, zoom_mult=1.25 - 0.25 * p)
                return Image.blend(fo, fi, p)
            if bl["type"] == "wipe":
                fo = render_seg(seg_out, absf)
                fi = render_seg(seg_in, absf)
                x = int(round(p * T.W))
                if bl["dir"] == "L->R":
                    fo.paste(fi.crop((0, 0, x, T.H)), (0, 0))
                else:
                    fo.paste(fi.crop((T.W - x, 0, T.W, T.H)), (T.W - x, 0))
                return fo
            if bl["type"] == "dip":
                if k < 3:
                    alpha = 1.0 - (k + 1) / 3.0
                    return Image.blend(BLACK, render_seg(seg_out, absf), alpha)
                else:
                    alpha = (k - 2) / 3.0
                    return Image.blend(BLACK, render_seg(seg_in, absf), alpha)
            if bl["type"] == "slide":
                fo = render_seg(seg_out, absf)
                fi = render_seg(seg_in, absf)
                off = int(round((1 - p) * T.H))
                fo.paste(fi, (0, off))
                return fo
            raise ValueError(bl["type"])
    # plain segment frame
    for seg in T.SEGMENTS:
        a, b = seg["display"]
        if a <= absf <= b:
            return render_seg(seg, absf)
    raise RuntimeError("no segment covers frame %d" % absf)

# ---------------------------------------------------------------- audio -----
SR = 44100
def _env(n, attack, release):
    e = []
    for i in range(n):
        t = i / float(n)
        if t < attack:
            v = t / attack
        elif t > 1 - release:
            v = (1 - t) / release
        else:
            v = 1.0
        e.append(v * v * (3 - 2 * v))
    return e

def synth(events, dur):
    rnd = random.Random(1234)
    buf = [0.0] * int(dur * SR)
    def mix(start_s, samples, gain):
        i0 = int(start_s * SR)
        for j, s in enumerate(samples):
            i = i0 + j
            if 0 <= i < len(buf):
                buf[i] += s * gain
    for kind, t in events:
        if kind == "click":
            n = int(0.025 * SR); out = []
            for i in range(n):
                tt = i / float(SR)
                f = 2000 * math.exp(-tt * 90) + 300
                out.append(math.sin(2 * math.pi * f * tt) * math.exp(-tt * 160))
            mix(t, out, 0.5)
        elif kind == "whoosh":
            n = int(0.32 * SR); out = []
            e = _env(n, 0.35, 0.65)
            lp = 0.0
            for i in range(n):
                w = rnd.uniform(-1, 1)
                lp += 0.25 * (w - lp)
                out.append(lp * e[i])
            mix(t, out, 0.55)
        elif kind == "swell":
            n = int(0.55 * SR); out = []
            e = _env(n, 0.5, 0.5)
            lp = 0.0
            for i in range(n):
                w = rnd.uniform(-1, 1)
                lp += 0.12 * (w - lp)
                out.append(lp * e[i])
            mix(t, out, 0.5)
        elif kind == "thud":
            n = int(0.28 * SR); out = []
            for i in range(n):
                tt = i / float(SR)
                out.append(math.sin(2 * math.pi * 70 * tt) * math.exp(-tt * 14) + 0.3 * rnd.uniform(-1, 1) * math.exp(-tt * 40))
            mix(t, out, 0.55)
    return buf

def make_audio():
    f = T.FPS
    events = [
        ("swell", 50 / f), ("swell", 60 / f),
        ("click", 180 / f),
        ("swell", 330 / f),
        ("click", 480 / f),
        ("whoosh", 630 / f),
        ("whoosh", 780 / f),
        ("thud", 930 / f),
        ("click", 1080 / f), ("click", 1081 / f),
        ("click", 1082 / f),
        ("whoosh", 1142 / f),
        ("swell", 1320 / f),
        ("swell", 1480 / f),
        ("whoosh", 1590 / f),
        ("click", 1740 / f),
        ("swell", 1850 / f),
        ("swell", 1860 / f),
    ]
    buf = synth(events, T.TOTAL / f)
    peak = max(0.0001, max(abs(x) for x in buf))
    scale = 0.75 / peak
    with wave.open(TMP_WAV, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        frames = bytearray()
        for v in buf:
            s = int(max(-1, min(1, v * scale)) * 32767)
            frames += s.to_bytes(2, "little", signed=True) * 2
        w.writeframes(bytes(frames))

# ----------------------------------------------------------------- main -----
def main():
    check = T.check_invariants()
    # coverage check
    covered = [0] * T.TOTAL
    for seg in T.SEGMENTS:
        for i in range(seg["display"][0], seg["display"][1] + 1):
            covered[i] += 1
    for a, b in T.FLASH_FRAMES.values():
        for i in range(a, b + 1):
            covered[i] += 1
    missing = [i for i, c in enumerate(covered) if c == 0]
    assert not missing, "uncovered frames: %s" % missing[:20]

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (T.W, T.H),
           "-r", str(T.FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", TMP_MP4]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(T.TOTAL):
        img = render_frame(f)
        proc.stdin.write(img.tobytes())
        if f % 300 == 0:
            print("frame", f, flush=True)
    proc.stdin.close()
    assert proc.wait() == 0
    print("video frames done")

    make_audio()
    print("audio done")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-i", TMP_MP4, "-i", TMP_WAV,
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                    "-shortest", OUT_MP4], check=True)
    print("wrote", OUT_MP4)

if __name__ == "__main__":
    main()
