#!/usr/bin/env python3
"""Tell the interviewee from the person holding the phone (the interviewer), by pitch and level.

Usage:  python3 speakers.py CLIP_OR_WAV map [WINDOW_S]        per-window median pitch / level: "t:Hz/dB ..."
        python3 speakers.py CLIP_OR_WAV runs [MIN_HZ]         runs of voiced speech above MIN_HZ (default 165)
        python3 speakers.py CLIP_OR_WAV check A-B [A-B ...]   same runs, only inside the listed source ranges

On the interview this was built on, the interviewer was 180-290 Hz and ~10 dB louder (she held the phone),
the interviewee ~105 Hz. Read `map` first to learn the two voices, then use `runs` with a threshold between them.
Short high-pitch blips (< 0.3 s) inside his phrases were his own vowels or birds, not her: confirm by ear or with
`fillers.py check` (Whisper on the isolated snippet). Every voice piece and every natural-sound window must be clear
of her; run `check` on the final voice track (WORK/voice.wav) too.
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_mono

SR, HOP, FL = 16000, 160, 640


def analyse(x):
    lo, hi = int(SR / 350), int(SR / 70); n = (len(x) - FL) // HOP
    f0, rms, w = np.zeros(n), np.zeros(n), np.hanning(FL)
    for i in range(n):
        fr = x[i * HOP:i * HOP + FL]; rms[i] = np.sqrt((fr ** 2).mean() + 1e-12)
        fr = (fr - fr.mean()) * w; ac = np.correlate(fr, fr, "full")[FL - 1:]
        if ac[0] <= 0: continue
        ac /= ac[0]; k = lo + np.argmax(ac[lo:hi])
        if ac[k] > 0.55 and rms[i] > 0.004: f0[i] = SR / k
    return f0, rms


def runs(f0, rms, thr, t0=0.0, t1=None):
    hi, out, i = f0 > thr, [], int(t0 * SR / HOP)
    end = len(hi) if t1 is None else min(len(hi), int(t1 * SR / HOP))
    while i < end:
        if hi[i]:
            j = i
            while j < end and (hi[j] or (j + 1 < end and hi[j + 1])): j += 1
            d = (j - i) * HOP / SR
            if d >= 0.12: out.append(f"{i * HOP / SR:.2f}+{d:.2f}s {np.median(f0[i:j][f0[i:j] > 0]):.0f}Hz {20 * np.log10(rms[i:j].mean()):.0f}dB")
            i = j
        else: i += 1
    return out


if __name__ == "__main__":
    if len(sys.argv) < 3: sys.exit(__doc__)
    f0, rms = analyse(load_mono(sys.argv[1], SR)); mode = sys.argv[2]
    if mode == "map":
        per = int(float(sys.argv[3] if len(sys.argv) > 3 else 1.0) * SR / HOP); rows = []
        for s in range(0, len(f0), per):
            v = f0[s:s + per]; v = v[v > 0]; db = 20 * np.log10(np.sqrt((rms[s:s + per] ** 2).mean()) + 1e-9)
            rows.append(f"{s * HOP / SR:.0f}:{np.median(v) if len(v) >= 8 else 0:.0f}/{db:.0f}")
        print(" ".join(rows))
    elif mode == "runs":
        r = runs(f0, rms, float(sys.argv[3]) if len(sys.argv) > 3 else 165); print(len(r), "runs:"); print("\n".join(r))
    elif mode == "check":
        for rg in sys.argv[3:]:
            a, b = map(float, rg.split("-")); r = runs(f0, rms, 165, a, b)
            print(f"{rg}: " + ("clear" if not r else " | ".join(r)))
    else: sys.exit(__doc__)
