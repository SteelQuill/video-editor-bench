#!/usr/bin/env python3
"""capture_tui.py — record a real OpenCode TUI exchange in Xvfb.

Asset 03: user types "generate video brah", the assistant answers for real.

Sequence (recording starts only once the TUI is on screen -> no black lead-in):
  xterm + opencode TUI up -> ffmpeg x11grab -> type prompt -> Enter ->
  wait until the screen goes static (reply finished) -> stop -> poster frames.

    python3 capture_tui.py --out /root/assets/03_opencode/clip.mp4 \
        [--prompt "generate video brah"] [--model ...]
"""
import argparse
import hashlib
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import time

W, H = 1920, 1080
DISPLAY = ":99"


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, **kw)


def x_running():
    return sh(["xdpyinfo", "-display", DISPLAY]).returncode == 0


def ensure_xvfb():
    if x_running():
        return None
    p = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", f"{W}x{H}x24",
                          "-nolisten", "tcp"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        if x_running():
            return p
        time.sleep(0.25)
    sys.exit("Xvfb failed")


def grab(path="/tmp/_tui_grab.jpg"):
    sh(["ffmpeg", "-y", "-f", "x11grab", "-video_size", f"{W}x{H}",
        "-i", DISPLAY, "-frames:v", "1", "-q:v", "5", path])
    return path


def changed_ratio(prev_path, cur_path):
    """Fraction of pixels that visibly changed between two frames."""
    from PIL import Image, ImageChops
    if not prev_path or not os.path.exists(prev_path):
        return 1.0
    a = Image.open(prev_path).convert("L")
    b = Image.open(cur_path).convert("L")
    if a.size != b.size:
        return 1.0
    diff = ImageChops.difference(a, b).point(lambda p: 255 if p > 14 else 0)
    hist = diff.histogram()
    return hist[255] / (a.size[0] * a.size[1])


def wait_static(min_wait, max_wait, quiet_ratio=0.0006):
    """Wait until the screen stops changing (model reply finished)."""
    prev = None
    t0 = time.time()
    stable = 0
    while time.time() - t0 < max_wait:
        time.sleep(3.0)
        g = grab()
        r = changed_ratio(prev, g)
        prev = g
        elapsed = time.time() - t0
        if r < quiet_ratio and elapsed >= min_wait:
            stable += 1
            if stable >= 2:
                return elapsed
        else:
            stable = 0
    return time.time() - t0


def wait_assistant_reply(t0, max_wait, db="/home/rec/.local/share/opencode/opencode.db"):
    """Ground truth: poll the session db until a NEW assistant message exists.

    Pixel-diff settling is wrong for this TUI — the model 'reasoning' phase
    renders nothing (one take fooled the diff detector, we stopped 10s before
    the reply). The db doesn't lie.
    """
    t0_ms = int(t0 * 1000)
    t_start = time.time()
    while time.time() - t_start < max_wait:
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
            n = con.execute(
                "select count(*) from session_message "
                "where type='assistant' and time_created >= ?",
                (t0_ms,)).fetchone()[0]
            con.close()
            if n:
                return time.time() - t_start
        except Exception as e:
            print(f"[t] db poll: {e}")
        time.sleep(2.0)
    return time.time() - t_start


def start_ffmpeg(out):
    p = subprocess.Popen(
        ["ffmpeg", "-y", "-f", "x11grab", "-video_size", f"{W}x{H}",
         "-framerate", "30", "-i", DISPLAY,
         "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", out],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    time.sleep(1.5)
    if p.poll() is not None:
        sys.exit("ffmpeg died: " + p.stderr.read().decode()[-500:])
    return p


def stop_ffmpeg(p):
    p.send_signal(signal.SIGINT)
    try:
        p.wait(timeout=30)
    except subprocess.TimeoutExpired:
        p.kill()


def capture(out, prompt, reply_wait_max):
    ensure_xvfb()
    os.environ["DISPLAY"] = DISPLAY  # xdotool in sh() needs it, else every
    # window search silently returns empty ("window not found")
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)

    # 1. xterm with the real opencode TUI (window persists after opencode exits).
    #    C.UTF-8  -> TUI glyphs render right (else logo shows as "aaaa")
    #    fresh XDG_DATA_HOME -> no old session names leak into the tab bar
    # isolated identity (rec) -> fresh session list, so the user's old
    # session tabs never appear on camera; --standalone -> private server,
    # so we don't collide with the root background service on :49374
    # cwd /tmp/lolno -> AGENTS.md rule ("edit video" -> "lol no")
    subprocess.run(["pkill", "-u", "rec"])  # orphaned TUIs from prior takes
    time.sleep(1)
    shutil.rmtree("/home/rec/.local/share/opencode", ignore_errors=True)
    env = dict(os.environ, DISPLAY=DISPLAY)
    inner = ("cd /tmp/lolno && LANG=C.UTF-8 LC_ALL=C.UTF-8 "
             "opencode --standalone; exec bash")
    xterm = subprocess.Popen(
        ["xterm", "-T", "opencode", "-fa", "DejaVu Sans Mono", "-fs", "18",
         "-geometry", "160x42+0+0", "-bg", "black", "-fg", "#d0d0d0",
         "-e", "su", "-", "rec", "-c", inner],
        env=env)
    time.sleep(15)  # TUI boot (standalone server + prompt box)
    wid = []
    for cand in sh(["xdotool", "search", "--onlyvisible", "--class", "xterm"]
                   ).stdout.decode().split():
        # only trust the window that belongs to OUR xterm pid
        if sh(["xdotool", "getwindowpid", cand]).stdout.decode().strip() == str(xterm.pid):
            wid = [cand]
            break
    if not wid:
        wid = sh(["xdotool", "search", "--name", "OpenCode"]).stdout.decode().split()
    if not wid:
        xterm.terminate()
        sys.exit("opencode window not found")
    win = wid[-1]
    sh(["xdotool", "windowfocus", "--sync", win])
    sh(["xdotool", "windowraise", win])
    time.sleep(1.0)
    print(f"[t] window {win} focused, TUI ready")

    # 2. record only now -> footage opens on a visible terminal
    ff = start_ffmpeg(out)
    time.sleep(1.6)

    # 3. real typing, human-ish cadence
    t0 = time.time()
    sh(["xdotool", "type", "--delay", "85", "--window", win, prompt])
    time.sleep(0.8)
    sh(["xdotool", "key", "--window", win, "Return"])
    print(f"[t] typed: {prompt!r} + Enter")

    # 4. wait for the REAL reply (db), then hold the finished frame
    settled = wait_assistant_reply(t0, max_wait=reply_wait_max)
    print(f"[t] assistant reply confirmed after {settled:.1f}s")
    time.sleep(3.5)

    stop_ffmpeg(ff)
    xterm.terminate()

    base, _ = os.path.splitext(out)
    for tag, sec in (("a", 0.5), ("b", settled + 6)):
        sh(["ffmpeg", "-y", "-ss", str(sec), "-i", out, "-frames:v", "1",
            "-q:v", "3", f"{base}_{tag}.jpg"])
    sh(["ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1", out])
    print(f"done: {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--prompt", default="generate video brah")
    ap.add_argument("--max-wait", type=float, default=60)
    a = ap.parse_args()
    capture(a.out, a.prompt, a.max_wait)
