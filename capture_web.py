#!/usr/bin/env python3
"""capture_web.py — real screen recording pipeline.

Xvfb :99 + ffmpeg x11grab captures the whole screen while Playwright drives
headed Chromium through a scripted scroll with the 0.8s/1.2s cadence.

    python3 capture_web.py --url https://github.com/OWNER/REPO \
        --out /root/assets/06_github/repo.mp4 --duration 14

Outputs an h264/yuv420p mp4 (universal editor format) plus 2 poster frames.
Requires: Xvfb, ffmpeg, playwright chromium, xdotool (optional).
"""
import argparse
import os
import signal
import subprocess
import sys
import time

W, H = 1920, 1080
DISPLAY = ":99"


def x_running():
    try:
        subprocess.run(["xdpyinfo", "-display", DISPLAY],
                       check=True, capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def ensure_xvfb():
    if x_running():
        print(f"[x] Xvfb {DISPLAY} already running")
        return None
    p = subprocess.Popen(
        ["Xvfb", DISPLAY, "-screen", "0", f"{W}x{H}x24", "-nolisten", "tcp"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        if x_running():
            print(f"[x] Xvfb {DISPLAY} up (pid {p.pid})")
            return p
        time.sleep(0.25)
    sys.exit("Xvfb failed to start")


def start_ffmpeg(out):
    cmd = ["ffmpeg", "-y", "-f", "x11grab", "-video_size", f"{W}x{H}",
           "-framerate", "30", "-i", DISPLAY,
           "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    # x11grab needs the display ready before it records frames
    time.sleep(1.5)
    if p.poll() is not None:
        err = p.stderr.read().decode(errors="replace")
        sys.exit(f"ffmpeg died at start:\n{err[-800:]}")
    print(f"[f] recording {out}")
    return p


def stop_ffmpeg(p):
    p.send_signal(signal.SIGINT)  # graceful: writes moov atom
    try:
        p.wait(timeout=30)
    except subprocess.TimeoutExpired:
        p.kill()
    err = p.stderr.read().decode(errors="replace")
    if p.returncode not in (0, 255, -2):
        print(f"[f] warn rc={p.returncode}: {err[-400:]}")


def capture(url, out, duration, scroll, wait_after):
    from playwright.sync_api import sync_playwright

    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    ensure_xvfb()
    env = dict(os.environ, DISPLAY=DISPLAY)

    ff = start_ffmpeg(out)
    ok = False
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=False,
                args=["--no-sandbox", "--disable-gpu",
                      "--disable-dev-shm-usage",
                      f"--window-size={W},{H}"],
                env=env)
            ctx = browser.new_context(
                viewport={"width": W, "height": H},
                user_agent=("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"))
            page = ctx.new_page()
            print(f"[p] goto {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            time.sleep(2.0)  # let layout/paint settle before scroll

            if scroll:
                # pickup cadence: 0.8s per step, 1.2s breath at intervals
                end = time.time() + duration
                step = 0
                while time.time() < end:
                    page.mouse.wheel(0, 260)
                    step += 1
                    time.sleep(1.2 if step % 4 == 0 else 0.8)
            else:
                time.sleep(duration)

            time.sleep(wait_after)
            browser.close()
            ok = True
    except Exception as e:
        print(f"[!] {type(e).__name__}: {e}")
    finally:
        stop_ffmpeg(ff)

    if not ok:
        sys.exit(1)
    # poster frames for instant verification
    base, _ = os.path.splitext(out)
    for tag, frac in (("a", 0.15), ("b", 0.75)):
        subprocess.run(["ffmpeg", "-y", "-ss", str(duration * frac),
                        "-i", out, "-frames:v", "1", "-q:v", "3",
                        f"{base}_{tag}.jpg"],
                       capture_output=True)
    subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                    "format=duration,size", "-of", "default=nw=1", out],
                   check=False)
    print(f"done: {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--duration", type=float, default=14,
                    help="seconds of scrolling (before settle)")
    ap.add_argument("--wait-after", type=float, default=1.5)
    ap.add_argument("--no-scroll", action="store_true")
    a = ap.parse_args()
    capture(a.url, a.out, a.duration, not a.no_scroll, a.wait_after)
