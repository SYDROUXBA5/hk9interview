#!/usr/bin/env python3
"""Frames for choosing and framing shots.

Usage:  python3 frames.py grid OUT.jpg CLIP:START:END:STEP [CLIP:START:END:STEP ...]   [--norot CLIP,CLIP]
            Source frames with a 0.1-step x grid (red line = 0.5) and labels "clip time": read the subject's x
            (and y) off it to write a shot's keys [(clip_t, cx, cy)]. Use STEP 0.25-0.5 s where the subject moves.
        python3 frames.py strip OUT.jpg VIDEO T1 T2 T3 ...
            Frames of a RENDER at output times, side by side: check every shot keeps the subject in frame.

Measure on the render when it matters: a handheld camera moves between source samples, so a key read off the
source can still put the subject on the crop edge. In 9:16 the crop is only 0.316 of the source width.
"""
import os, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont


def grab(path, t, w, h, norot, out):
    pre = ["-noautorotate"] if norot else []
    subprocess.run(["ffmpeg", "-v", "error", "-y", *pre, "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1",
                    "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease", "-q:v", "4", out], stderr=subprocess.DEVNULL)
    return out


def clip_path(name, footage):
    if os.path.isfile(name): return name
    for f in sorted(os.listdir(footage)):
        if os.path.splitext(f)[0].endswith(name): return os.path.join(footage, f)
    sys.exit(f"no clip {name} in {footage}")


def grid(out, specs, norot, footage):
    jobs = []
    for s in specs:
        c, a, b, st = s.split(":"); t = float(a)
        while t <= float(b) + 1e-6: jobs.append((c, round(t, 2))); t += float(st)
    TW, TH, C = 384, 216, 5; wd = tempfile.mkdtemp(prefix="hk9i_")
    with ThreadPoolExecutor(8) as ex:
        files = list(ex.map(lambda j: grab(clip_path(j[0], footage), j[1], TW, TH, j[0] in norot, f"{wd}/{j[0]}_{j[1]}.jpg"), jobs))
    im = Image.new("RGB", (C * TW, ((len(jobs) + C - 1) // C) * TH)); d = ImageDraw.Draw(im); f = ImageFont.load_default()
    for k, ((c, t), fp) in enumerate(zip(jobs, files)):
        x, y = (k % C) * TW, (k // C) * TH
        if os.path.exists(fp): q = Image.open(fp); im.paste(q, (x + (TW - q.width) // 2, y + (TH - q.height) // 2))
        for g in range(1, 10):
            gx = x + int(TW * g / 10); d.line([gx, y, gx, y + TH], fill=(255, 0, 0) if g == 5 else (255, 255, 0))
            d.text((gx + 2, y + TH - 14), f".{g}", fill="yellow", font=f)
        d.rectangle([x, y, x + 110, y + 15], fill="black"); d.text((x + 3, y + 2), f"{c} {t}", fill="cyan", font=f)
    im.save(out, quality=72); print(f"{len(jobs)} frames -> {out}")


def strip(out, video, times):
    wd = tempfile.mkdtemp(prefix="hk9i_")
    files = [grab(video, float(t), 240, 240, False, f"{wd}/{i}.jpg") for i, t in enumerate(times)]
    ims = [Image.open(p) for p in files if os.path.exists(p)]
    W = sum(i.width for i in ims); H = max(i.height for i in ims)
    o = Image.new("RGB", (W, H)); d = ImageDraw.Draw(o); x = 0
    for t, i in zip(times, ims): o.paste(i, (x, 0)); d.text((x + 4, 4), t, fill="yellow"); x += i.width
    o.save(out, quality=75); print(f"{len(ims)} frames -> {out}")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    norot = set(sys.argv[sys.argv.index("--norot") + 1].split(",")) if "--norot" in sys.argv else set()
    if "--norot" in sys.argv: a.remove(sys.argv[sys.argv.index("--norot") + 1])
    footage = os.environ.get("FOOTAGE", ".")
    if len(a) >= 3 and a[0] == "grid": grid(a[1], a[2:], norot, footage)
    elif len(a) >= 4 and a[0] == "strip": strip(a[1], a[2], a[3:])
    else: sys.exit(__doc__ + "\nSet FOOTAGE=<folder> so clip names like IMG_0123 or 0123 resolve.")
