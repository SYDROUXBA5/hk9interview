#!/usr/bin/env python3
"""Find and verify "uh"/"um" fillers.

Usage:  python3 fillers.py scan VOICE_WAV                  candidates in an edited voice track (e.g. WORK/voice.wav)
        python3 fillers.py check SOURCE_CLIP A-B [A-B ...]  verify source ranges: voiced segments, pitch, Whisper on each
        python3 fillers.py formants SOURCE_CLIP A-B         30 ms level + F1/F2 track, to place a cut exactly

Method (it is the only one that worked reliably):
 1. `scan` runs Whisper word-by-word with a filler-heavy prompt, which makes it write fillers down. It also INVENTS
    fillers at cut points and in pauses, and its times are 0.2-0.5 s off. Treat every hit as a candidate only.
 2. Map each candidate to source time (the build's --dry timeline gives piece in/out points), then `check` a window
    of about 1 s around it. A real filler is a voiced segment that Whisper, on the isolated snippet, hears as
    "Um"/"Uh"/"on"/"Oh" and whose formants are a steady F1 ~500-700 / F2 ~1100-1300 vowel, often ending in a nasal
    (F1 ~250). "I'm" looks similar but its F2 rises toward ~1800-2000.
 3. Cut it out (edit CUTS, or move a piece edge), leaving 0.1-0.25 s of natural pause. Never cut a word you need:
    Whisper the joined phrase if unsure. On camera, hide the cut with a punch-in (split the shot, zoom +0.2).
 4. Re-render the voice and `scan` again until it lists nothing real.
"""
import os, sys, tempfile
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import FILLER_PROMPT, FILLERS, envelope, formants, load_mono, pitch, snippet_text, to_wav16, whisper

SR = 48000


def scan(path):
    x = load_mono(path, SR); wd = tempfile.mkdtemp(prefix="hk9i_")
    w = whisper(to_wav16(x, SR, os.path.join(wd, "v16.wav")), prompt=FILLER_PROMPT, words=True)
    hits = [i for i, (_, _, t) in enumerate(w) if t.strip(" ,.?!").lower() in FILLERS]
    for i in hits:
        ctx = " ".join(t for _, _, t in w[max(0, i - 4):i]) + f" [[{w[i][2]}]] " + " ".join(t for _, _, t in w[i + 1:i + 5])
        print(f"{w[i][0]:7.2f}  {ctx}")
    print(f"{len(hits)} candidates in {len(w)} words")


def segments(x, a, b, floor=-44.0):
    e = envelope(x, SR, a, b); on = e > floor; out, i = [], 0
    while i < len(on):
        if on[i]:
            j = i
            while j < len(on) and (on[j] or on[j:j + 6].any()): j += 1
            if j - i >= 8: out.append((a + i * 0.01, a + j * 0.01 + 0.02, float(e[i:j].max())))
            i = j
        else: i += 1
    return out


def check(path, ranges):
    x = load_mono(path, SR); wd = tempfile.mkdtemp(prefix="hk9i_")
    for rg in ranges:
        a, b = map(float, rg.split("-"))
        for s0, s1, lv in segments(x, a, b):
            print(f"{rg}  {s0:.2f}-{s1:.2f}  {lv:.0f} dB  {pitch(x, SR, s0, s1):.0f} Hz  F={formants(x, SR, s0, min(s1, s0 + 0.12))}"
                  f"  whisper: {snippet_text(x, SR, s0, s1, wd)}")


def formant_track(path, rg):
    x = load_mono(path, SR); a, b = map(float, rg.split("-")); t = a
    while t < b:
        print(f"{t:.2f}  {envelope(x, SR, t, t + 0.03, 0.03, 0.03)[0]:5.0f} dB  F={formants(x, SR, t, t + 0.03)}"); t += 0.03


if __name__ == "__main__":
    if len(sys.argv) < 3: sys.exit(__doc__)
    {"scan": lambda: scan(sys.argv[2]), "check": lambda: check(sys.argv[2], sys.argv[3:]),
     "formants": lambda: formant_track(sys.argv[2], sys.argv[3])}.get(sys.argv[1], lambda: sys.exit(__doc__))()
