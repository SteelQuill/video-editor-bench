#!/usr/bin/env python3
"""Compose a scrolling "wall of slop" from downloaded thumbnails.

Tiles every thumbnail into a 4-column grid, then produces a slow vertical
scroll over the whole grid. Purpose: make the repetition painfully obvious.

env:
  THUMBDIR   dir of NNN.jpg thumbs (default /tmp/slop/full)
  OUT        output mp4 (default slop_scroll.mp4)
  DURATION   seconds of scroll (default 50)
  COLS       grid columns (default 4)
  FPS        (default 30)
  WIDTH      output width (default 1920)
"""
import glob
import os
import subprocess

THUMBDIR = os.environ.get("THUMBDIR", "/tmp/slop/full")
OUT = os.environ.get("OUT", "/tmp/slop/slop_scroll.mp4")
DURATION = int(os.environ.get("DURATION", "50"))
COLS = int(os.environ.get("COLS", "4"))
FPS = int(os.environ.get("FPS", "30"))
WIDTH = int(os.environ.get("WIDTH", "1920"))

CW = WIDTH // COLS          # cell width
CH = CW * 9 // 16           # cell height, keeps 16:9


def main():
    from PIL import Image

    files = sorted(glob.glob(os.path.join(THUMBDIR, "*.jpg")))
    if not files:
        raise SystemExit("no thumbs in %s" % THUMBDIR)

    rows = (len(files) + COLS - 1) // COLS
    gw, gh = COLS * CW, rows * CH
    print("thumbs=%d  cell=%dx%d  grid=%dx%d  rows=%d"
          % (len(files), CW, CH, gw, gh, rows), flush=True)

    grid = Image.new("RGB", (gw, gh), (8, 8, 8))
    for i, path in enumerate(files):
        im = Image.open(path).convert("RGB").resize((CW, CH), Image.LANCZOS)
        grid.paste(im, ((i % COLS) * CW, (i // COLS) * CH))
    grid_path = OUT + ".grid.png"
    grid.save(grid_path, optimize=True)
    print("wrote %s (%.1f MB)" % (grid_path, os.path.getsize(grid_path) / 1e6), flush=True)

    travel = gh - 1080
    if travel <= 0:
        raise SystemExit("grid shorter than 1080 -- use more thumbs")
    speed = travel / float(DURATION)
    print("scroll travel=%dpx over %ds = %.1f px/s (%.2fs per row)"
          % (travel, DURATION, speed, CH / speed), flush=True)

    # crop window glides down the tall grid -> looks like scrolling a page
    vf = ("crop=w=%d:h=1080:x=0:y='(ih-1080)*t/%d',"
          "format=yuv420p" % (WIDTH, DURATION))
    cmd = ["ffmpeg", "-y", "-loop", "1", "-i", grid_path,
           "-t", str(DURATION), "-vf", vf,
           "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-r", str(FPS), "-movflags", "+faststart", OUT]
    print(" ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration,size", "-of", "default=nw=1", OUT],
        capture_output=True, text=True).stdout.strip()
    print("done: %s\n%s" % (OUT, probe), flush=True)


if __name__ == "__main__":
    main()
