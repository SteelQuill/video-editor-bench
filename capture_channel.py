#!/usr/bin/env python3
"""Record a real YouTube channel page scrolling, in a headless Xvfb desktop.

Drives real Chromium + real wheel input (xdotool) so YouTube's infinite scroll
loads naturally. Captures the whole desktop via ffmpeg x11grab so the browser
chrome (tabs, address bar) is visible -> reads as a genuine screen recording.

Cadence is deliberately irregular: first wait 0.8s, one BIG scroll, wait 1.2s,
then continue with varied waits/distances. Fixed-interval scrolling is the
biggest automation tell.

env:
  CHANNEL_URL   (required) e.g. https://www.youtube.com/@name/videos
  OUT           output .webm (default capture.webm)
  STEPS         number of scroll cycles (default 6)
  RES           WxH (default 1920x1080)
  FPS           (default 30)
  DISPM         X display (default :99)
  SETTLE        seconds to wait after page load before recording (default 6)

Output: OUT (webm/vp9) + OUT.json (timing metadata for the verify step)
"""
import json
import os
import shlex
import signal
import subprocess
import sys
import time

DISPM = os.environ.get("DISPM", ":99")
RES = os.environ.get("RES", "1920x1080")
FPS = os.environ.get("FPS", "30")
OUT = os.environ.get("OUT", "capture.webm")
STEPS = int(os.environ.get("STEPS", "6"))
SETTLE = float(os.environ.get("SETTLE", "6"))
CHANNEL_URL = os.environ.get("CHANNEL_URL", "")

# Wait, scroll distance in "wheel clicks" -- tuned so the big first scroll
# shows many thumbnails at once, then smaller ones keep the motion alive.
CYCLES = [(0.8, 14), (1.2, 6), (0.6, 5), (1.0, 7), (0.7, 4), (1.1, 8), (0.9, 6)]

W, H = RES.split("x")


def sh(cmd, **kw):
    return subprocess.run(shlex.split(cmd), **kw)


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def main():
    if not CHANNEL_URL:
        sys.exit("set CHANNEL_URL")

    procs = []
    def cleanup(*_):
        for p in procs:
            if alive(p.pid):
                try:
                    p.send_signal(signal.SIGTERM)
                except OSError:
                    pass
        subprocess.run(["pkill", "-f", "ffmpeg -f x11grab"], capture_output=True)
        subprocess.run(["pkill", "-f", "[c]hromium"], capture_output=True)
        subprocess.run(["pkill", "-f", "[X]vfb"], capture_output=True)
    signal.signal(signal.SIGTERM, lambda *a: (cleanup(), sys.exit(1)))

    # 1. Xvfb desktop
    sh("Xvfb %s -screen 0 %sx%sx24 -nolisten tcp" % (DISPM, W, H))
    time.sleep(1.5)
    os.environ["DISPLAY"] = DISPM

    # 2. real Chromium, normal window size, no automation flags
    chrome = subprocess.Popen(shlex.split(
        "chromium-browser --no-sandbox --disable-gpu --disable-dev-shm-usage "
        "--window-size=%s,%s --start-maximized --autoplay-policy=no-user-gesture-required "
        "--lang=en-US --accept-lang=en-US --disable-features=TranslateUI "
        "--user-data-dir=/tmp/yt-profile %s" % (W, H, CHANNEL_URL)))
    procs.append(chrome)
    print("chromium pid=%d, settling %.1fs" % (chrome.pid, SETTLE), flush=True)
    time.sleep(SETTLE)

    # 3. centre the pointer, clear any hover state
    sh("xdotool mousemove %d %d" % (int(W) // 2, int(H) // 2))

    # 4. start recording
    rec = subprocess.Popen(shlex.split(
        "ffmpeg -y -f x11grab -video_size %s -framerate %s -i %s "
        "-c:v libvpx-vp9 -crf 33 -b:v 0 -row-mt 1 -cpu-used 4 -deadline realtime "
        "-pix_fmt yuv420p %s" % (RES, FPS, DISPM, OUT)))
    procs.append(rec)
    time.sleep(1.0)

    # 5. scroll with irregular cadence
    events = []
    t0 = time.time()
    for i, (wait, clicks) in enumerate(CYCLES[:STEPS]):
        time.sleep(wait)
        # real wheel events -> YouTube's lazy loader fires naturally
        sh("xdotool click 5 repeat-time 30 click --repeat %d 5" % clicks)
        events.append({"t": round(time.time() - t0, 2), "wheel_clicks": clicks})
        print("  cycle %d: waited %.1fs, scrolled %d clicks @t=%.1fs"
              % (i + 1, wait, clicks, events[-1]["t"]), flush=True)

    time.sleep(1.5)

    # 6. stop capture
    rec.send_signal(signal.SIGINT)
    for _ in range(40):
        if not alive(rec.pid):
            break
        time.sleep(0.25)
    cleanup()

    meta = {"channel_url": CHANNEL_URL, "res": RES, "fps": FPS,
            "settle_s": SETTLE, "scroll_events": events,
            "wall_s": round(time.time() - t0, 2), "out": OUT}
    with open(OUT + ".json", "w") as fh:
        json.dump(meta, fh, indent=1)
    print("wrote %s and %s.json" % (OUT, OUT), flush=True)


if __name__ == "__main__":
    main()
