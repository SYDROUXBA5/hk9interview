#!/usr/bin/env python3
"""Where the talking head is: x of the face/head (fraction of source width) over source time ranges.

Usage:  python3 headpos.py INTERVIEW_CLIP A-B [A-B ...]
Prints smoothed "(t, x)" pairs every 0.4 s: paste them as the on-camera shot's keys [(t, x, cy)] with cy ~0.36.

Why: never assume the subject is in the middle. On the first interview he stood at 0.44 and drifted to 0.38 between
answers, and a centred crop put him off-centre (it was the first thing the client noticed). Skin-tone centroid of
the upper 62% of the frame. Sunlight skews it: on the first interview it read ~0.025 left of the head centre (0.42 vs 0.445), so check one rendered frame and offset the keys.
"""
import subprocess, sys
import numpy as np

W, H, FR = 480, 270, 5


def track(src, a, b):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(a), "-t", str(b - a), "-i", src, "-vf", f"fps={FR},scale={W}:{H}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3).astype(np.float32); out = []
    for i, f in enumerate(fr):
        top = f[:int(H * 0.62)]; R, G, B = top[..., 0], top[..., 1], top[..., 2]
        m = (R > 105) & (R > G) & (G > B) & (R - B > 28) & (G / np.maximum(R, 1) < 0.90)
        xs = np.nonzero(m)[1]
        out.append((a + i / FR, float(np.median(xs)) / W if len(xs) > 400 else np.nan))
    return out


if __name__ == "__main__":
    if len(sys.argv) < 3: sys.exit(__doc__)
    for rg in sys.argv[2:]:
        a, b = map(float, rg.split("-")); t = track(sys.argv[1], a, b); x = np.array([v[1] for v in t])
        if np.isnan(x).all(): print(f"{rg}: no skin-tone area found; read it off `frames.py grid` instead"); continue
        x = np.where(np.isnan(x), np.nanmedian(x), x)
        k = np.exp(-0.5 * (np.arange(-6, 7) / 3.0) ** 2); k /= k.sum(); xs = np.convolve(np.pad(x, 6, mode="edge"), k, "valid")
        print(f"{rg}: " + ", ".join(f"({t[i][0]:.1f}, {xs[i]:.3f})" for i in range(0, len(t), 2)))
