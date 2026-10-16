#!/usr/bin/env python3
"""Render a referral-interview film from an edit file (the whole edit as data), vertical 9:16 and horizontal 16:9.

Usage:  python3 build.py EDIT.py                 render both orientations
        python3 build.py EDIT.py --dry           print the timeline and warnings only (fast; run it after every edit change)
        python3 build.py EDIT.py --vertical      (or --horizontal) render one orientation
Env:    WORK=<dir>  intermediate files (default: work_<edit name>/ next to the edit file)

Needs ffmpeg (8.x tested) and python3 with numpy + scipy. Footage is only read, never written.

What it does
  voice   cuts the interview into the edit's pieces (minus CUTS), joins them with 20 ms crossfades, fills gaps with
          room tone, cleans the background (denoise.py), high-passes at 80 Hz, normalises to -16 LUFS
  music   synthesised bed (no samples, nothing licensed): I-vi-IV-V, section energy from the edit, ducked under speech;
          sections start on beats, and the cold open's hit lands on a downbeat
  nat     short natural-sound windows from the b-roll (barks, shouts), placed by the edit
  picture every shot is a crop of the 16:9 source with a smoothed camera path (subject position keys, zoom keys,
          punch on the cut, optional whip blur); 9:16 crops 1080x1920 out of the source scaled to 1920 high,
          16:9 shows the whole frame and the zoom keys still push in; the interview shots are pulled back in 16:9
"""
import glob, importlib.util, json, math, os, subprocess, sys
import numpy as np
from scipy import signal
from scipy.io import wavfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from denoise import extract_clean

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
if not ARGS: sys.exit(__doc__)
EDIT_PATH = os.path.abspath(ARGS[0])
_spec = importlib.util.spec_from_file_location("edit", EDIT_PATH); E = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(E)
DRY = "--dry" in sys.argv
ORIENTS = [o for o in ("vertical", "horizontal") if f"--{o}" in sys.argv] or ["vertical", "horizontal"]
def opt(name, default): return getattr(E, name, default)

FOOTAGE, OUTPUT = E.FOOTAGE, E.OUTPUT
OUT_DIR = opt("OUT_DIR", FOOTAGE)
WORK = os.environ.get("WORK", os.path.join(os.path.dirname(EDIT_PATH), "work_" + os.path.splitext(os.path.basename(EDIT_PATH))[0]))
FPS, SR, XF = 30, 48000, 0.02                    # frame rate, audio rate, splice crossfade
BPM = opt("BPM", 112); BEAT = 60 / BPM
TONE = E.ROOM_TONE                               # start of >= 0.6 s of speech-free room tone in the interview
NOROT = tuple(opt("NOROT", ()))                  # clips carrying a wrong rotation flag: read with -noautorotate
LUFS, PEAK = opt("LUFS", -16.0), -1.5
MUSIC_UNDER_VOICE, MUSIC_ALONE, DUCK = opt("MUSIC_UNDER_VOICE", -15.0), opt("MUSIC_ALONE", -8.0), opt("DUCK", 5.0)
SECTIONS, ENERGY = E.SECTIONS, E.ENERGY
CUTS = sorted(opt("CUTS", []))
END_CARD = opt("END_CARD", 2.6)                 # picture after the last word (music rings out)
COLD = opt("COLD", None)                        # natural-sound cold open, or None
H_ZOOM_BACK = opt("HORIZONTAL_TALKING_HEAD_ZOOM_BACK", 0.15)
GEOM = {"vertical": dict(W=1080, H=1920, SW=3414), "horizontal": dict(W=1920, H=1080, SW=1920)}   # SW = 16:9 source scaled to H high

def clip(name):
    """A clip by file name or by any unique tail of its stem ("IMG_0001.MOV", "IMG_0001", "0001")."""
    exact = os.path.join(FOOTAGE, name)
    if os.path.isfile(exact): return exact
    hits = sorted(glob.glob(os.path.join(FOOTAGE, glob.escape(name) + ".*")) or glob.glob(os.path.join(FOOTAGE, "*" + glob.escape(name) + ".*")))
    if not hits: raise FileNotFoundError(f"no clip '{name}' in {FOOTAGE}")
    return hits[0]
def run(cmd, **kw): return subprocess.run(cmd, check=True, **kw)
INTERVIEW = clip(E.INTERVIEW)

# ---------------------------------------------------------------- TIMELINE
T_HIT = (COLD["hit"] - COLD["cin"]) if COLD else 0.0     # music grid origin: the cold open's hit lands on a downbeat
T0 = (COLD["cout"] - COLD["cin"]) if COLD else 0.0       # the interview voice starts after the cold open

def split(a, b):
    """Source range minus CUTS, as a list of (a, b) parts."""
    parts = []
    for c0, c1 in CUTS:
        if a < c0 < b: parts.append((a, c0)); a = max(a, c1)
    return parts + [(a, b)]

def timeline():
    """Pieces [(name, src_in, src_out, out_start)], section starts, voice end. Each section starts on a beat."""
    t, tl, sec = T0, [], {}
    for name, pieces in SECTIONS:
        k = math.ceil((t + 0.15 - T_HIT) / BEAT - 1e-6); t = T_HIT + k * BEAT      # next beat, >= 0.15 s of air
        sec[name] = t
        for p in pieces:
            if p[0] == "gap": t += p[1]; continue
            for a, b in split(p[1], p[2]): tl.append((p[0], a, b, t)); t += b - a
    return tl, sec, t
TL, SEC, VOICE_END = timeline()
TOTAL = VOICE_END + END_CARD
ORDER = [s for s, _ in SECTIONS]

def m(name, src):
    """Output time of a source time inside a named voice piece (a time inside a cut maps to the cut point)."""
    seg = [(a, b, o) for n, a, b, o in TL if n == name]
    if not seg: raise KeyError(name)
    assert seg[0][0] - 1e-6 <= src <= seg[-1][1] + 1e-6, (name, src, seg[0][0], seg[-1][1])
    for a, b, o in seg:
        if src <= b + 1e-6: return o + max(src, a) - a
def start(name): return [o for n, a, b, o in TL if n == name][0]
def end(name): return [o + b - a for n, a, b, o in TL if n == name][-1]
def nxt(name):
    """Output time at which the section after `name` begins (the voice end for the last one)."""
    i = ORDER.index(name); return SEC[ORDER[i + 1]] if i + 1 < len(ORDER) else VOICE_END

def S(label, clip_, cin, tend, keys, zk=None, punch=0.0, whip="", line=""):
    """A shot: label (first word = id), clip, clip in-point, OUTPUT time the shot ends, subject keys [(clip_t, cx, cy)],
    zoom keys [(clip_t, z)], punch = extra zoom that decays in 0.1 s after the cut, whip = "i"/"o" blur in/out."""
    return dict(label=label, clip=clip_, cin=cin, tend=tend, keys=keys, zk=zk or [(cin, 1.0)], punch=punch, whip=whip, line=line)

class Api: pass
api = Api()
for k, v in dict(m=m, start=start, end=end, nxt=nxt, S=S, SEC=SEC, VOICE_END=VOICE_END, TOTAL=TOTAL, T_HIT=T_HIT, BEAT=BEAT,
                 COLD=COLD, INTERVIEW=E.INTERVIEW).items(): setattr(api, k, v)
RAW_SHOTS = E.shots(api)

# ---------------------------------------------------------------- PICTURE
def prepare(raw, orient):
    """Frame counts and smooth camera paths (time samples of cx, cy, z)."""
    shots, f0 = [], 0
    for s in raw:
        sh = dict(s)
        if orient == "horizontal" and clip(sh["clip"]) == INTERVIEW:     # 16:9 already frames him; the 9:16 push-in would cut his head
            sh["zk"] = [(t, max(1.0, z - H_ZOOM_BACK)) for t, z in sh["zk"]]
        f1 = round(sh["tend"] * FPS); sh["n"] = f1 - f0; sh["t0"] = f0 / FPS; sh["dur"] = sh["n"] / FPS; f0 = f1
        assert sh["n"] > 0, f"shot {sh['label']} has no frames (ends before the previous one)"
        ts = np.arange(0, sh["dur"] + 0.051, 0.05); src = sh["cin"] + ts
        kt = [k[0] for k in sh["keys"]]
        cx = np.interp(src, kt, [k[1] for k in sh["keys"]]); cy = np.interp(src, kt, [k[2] for k in sh["keys"]])
        z = np.interp(src, [k[0] for k in sh["zk"]], [k[1] for k in sh["zk"]])
        g = np.exp(-0.5 * (np.arange(-8, 9) / 3.5) ** 2); g /= g.sum()          # ~0.18 s gaussian: no hard corners
        sm = lambda v: np.convolve(np.pad(v, 8, mode="edge"), g, "valid")
        sh["path"] = (ts, sm(cx), sm(cy), sm(z) + sh["punch"] * np.exp(-ts / 0.10))
        shots.append(sh)
    assert abs(f0 / FPS - TOTAL) < 0.04, f"last shot ends at {f0 / FPS:.2f}s, film is {TOTAL:.2f}s: end it at api.TOTAL"
    return shots
SHOTS = prepare(RAW_SHOTS, "vertical")
SH = {s["label"].split()[0]: s for s in SHOTS}

def pw(ts, vs, tol):
    """ffmpeg piecewise-linear expression of t through (ts, vs), thinned to within tol."""
    keep = [0]
    for i in range(1, len(ts) - 1):
        a = keep[-1]; pred = vs[a] + (vs[i + 1] - vs[a]) * (ts[i] - ts[a]) / (ts[i + 1] - ts[a])
        if abs(pred - vs[i]) > tol or ts[i] - ts[a] > 1.0: keep.append(i)
    keep.append(len(ts) - 1); e = f"{vs[keep[-1]]:.5f}"
    for a, b in reversed(list(zip(keep, keep[1:]))):
        e = f"if(lt(t,{ts[b]:.3f}),{vs[a]:.5f}+({(vs[b] - vs[a]) / (ts[b] - ts[a]):.6f})*(t-{ts[a]:.3f}),{e})"
    return e

def shot_filter(i, sh, W, H, SW):
    ts, cx, cy, z = sh["path"]; TY = 0.46 * H                 # TY: screen height at which the subject (cy) is held
    ex, ey, ez = pw(ts, cx, 0.0008), pw(ts, cy, 0.0008), pw(ts, z, 0.0015)
    blur = ""
    if "i" in sh["whip"]: blur += "gblur=sigma=42:sigmaV=0:steps=1:enable='lt(t,0.085)',"
    if "o" in sh["whip"]: blur += f"gblur=sigma=42:sigmaV=0:steps=1:enable='gt(t,{sh['dur'] - 0.075:.3f})',"
    return (f"[{i}:v]setpts=PTS-STARTPTS,fps={FPS},format=yuv420p10le,"
            f"scale=w='2*trunc({SW}*({ez})/2)':h='2*trunc({H}*({ez})/2)':eval=frame:flags=bicubic,"
            f"crop={W}:{H}:x='clip(({ex})*iw-{W / 2:.0f},0,iw-{W})':y='clip(({ey})*ih-{TY:.0f},0,ih-{H})',"
            f"{blur}unsharp=5:5:0.35:5:5:0,trim=end_frame={sh['n']},setpts=PTS-STARTPTS,setsar=1[v{i}]")

def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,color_transfer:stream_side_data=rotation", "-of", "json", path],
                         capture_output=True, text=True).stdout
    s = json.loads(out)["streams"][0]; rot = next((int(d.get("rotation", 0)) for d in s.get("side_data_list", []) if "rotation" in d), 0)
    return s["width"], s["height"], rot, s.get("color_transfer", "")

def warnings():
    w = []
    for name in sorted({s["clip"] for s in SHOTS}):
        wd, ht, rot, _ = probe(clip(name))
        if name in NOROT: rot = 0
        if rot % 180: wd, ht = ht, wd
        if abs(wd / ht - 16 / 9) > 0.02: w.append(f"{name}: plays as {wd}x{ht}, not 16:9 landscape (wrong rotation flag? add it to NOROT)")
    for (n, a, b, o) in TL:
        if a < TONE + 0.6 and b > TONE: w.append(f"piece {n} overlaps the room-tone span {TONE}-{TONE + 0.6:.2f}: fine only if that stretch is silent")
    return w

# ---------------------------------------------------------------- SOUND
def stem(src_path, a, b):
    raw = os.path.join(WORK, "tmp.wav")
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", src_path, "-vn", "-ar", str(SR), "-ac", "2", raw])
    return wavfile.read(raw)[1].astype(np.float64) / 32768.0

def build_voice():
    raw = os.path.join(WORK, "interview48.wav")
    extract_clean(INTERVIEW, raw, SR, **opt("DENOISE", dict(gmin_db=-24.0, beta=1.7)))
    x = wavfile.read(raw)[1].astype(np.float64) / 32768.0
    h, nx = XF / 2, int(XF * SR); n = int(TOTAL * SR)
    buf = np.zeros((n + SR, 2)); ramp = np.linspace(0, 1, nx)[:, None]
    def put(a, b, o):
        c = x[int(round((a - h) * SR)):int(round((b + h) * SR))].copy(); c[:nx] *= ramp; c[-nx:] *= ramp[::-1]
        s = int(round((o - h) * SR)); buf[s:s + len(c)] += c
    for (n1, a, b, o), nx_ in zip(TL, TL[1:] + [None]):
        put(a, b, o)
        gap = (nx_[3] - (o + b - a)) if nx_ else 0.0
        t = o + b - a
        while gap > 0.01:                                           # room tone across gaps so the voice bed never drops out
            d = min(gap, 0.55); put(TONE, TONE + d, t); t += d; gap -= d
    mono = x.mean(1)
    def lvl(t): g = mono[int((t - .015) * SR):int((t + .015) * SR)]; return 20 * np.log10(np.sqrt((g ** 2).mean()) + 1e-9)
    edges = [f"{n} {lvl(a):.0f}/{lvl(b):.0f}" + (" <-- on a sound" if max(lvl(a), lvl(b)) > -40 else "") for n, a, b, _ in TL]
    print("level at each voice piece's in/out edge (dB; above about -40 means the cut lands on a sound):\n  " + "\n  ".join(edges))
    sos = signal.butter(2, 80, "hp", fs=SR, output="sos")
    return signal.sosfilt(sos, buf[:n], axis=0)

def build_nat():
    y = np.zeros((int(TOTAL * SR), 2)); f = int(0.03 * SR); ramp = np.linspace(0, 1, f)[:, None]
    for c, a, b, o, g in (E.nat(api, SH) if hasattr(E, "nat") else []):
        s = stem(clip(c), a, b); s[:f] *= ramp; s[-f:] *= ramp[::-1]
        i = int(o * SR); y[i:i + len(s)] += s[:len(y) - i] * 10 ** (g / 20)
    return y

def midi(n): return 440.0 * 2 ** ((n - 69) / 12)
def synth_music(voice_active):
    """Upbeat bed, D major, I-vi-IV-V. Entirely synthesised here; no samples, nothing licensed."""
    n = int(TOTAL * SR); L, R = np.zeros(n + 2 * SR), np.zeros(n + 2 * SR); rng = np.random.default_rng(7)
    def add(t, sig, gain=1.0, pan=0.0):
        i = int(t * SR)
        if i < 0 or i >= n: return
        L[i:i + len(sig)] += sig * gain * (1 - max(0, pan)); R[i:i + len(sig)] += sig * gain * (1 + min(0, pan))
    def env(d, a=0.004): t = np.arange(int(d * SR)) / SR; return t, np.minimum(1, t / a)
    def pluck(f, d=0.5):
        t, a = env(d); return a * sum(np.sin(2 * np.pi * k * f * t) * np.exp(-t * (5 + 3.2 * k)) / k ** 1.15 for k in range(1, 7))
    def bass(f, d=0.26):
        t, a = env(d, 0.006); return a * (np.sin(2 * np.pi * f * t) + .35 * np.sin(4 * np.pi * f * t) + .12 * np.sin(6 * np.pi * f * t)) * np.exp(-t / 0.22)
    def kick():
        t, a = env(0.32, 0.002); ph = 2 * np.pi * np.cumsum(45 + 80 * np.exp(-t / 0.028)) / SR; return a * np.sin(ph) * np.exp(-t / 0.15)
    def noise(d, lo, hi, tau):
        t, a = env(d, 0.002); sos = signal.butter(2, [lo, hi], "bp", fs=SR, output="sos")
        return signal.sosfilt(sos, rng.standard_normal(len(t))) * a * np.exp(-t / tau)
    def pad(notes, d):
        t, _ = env(d); e = np.minimum(1, t / 0.35) * np.minimum(1, (d - t) / 0.45)
        return e * sum(np.sin(2 * np.pi * k * midi(nn) * (1 + det) * t) * np.exp(-k / 2.6) / k
                       for nn in notes for det in (-0.003, 0.003) for k in range(1, 7))
    CH = [(50, 54, 57), (47, 50, 54), (43, 47, 50), (45, 49, 52)]                   # D  Bm  G  A
    ARP = [0, 2, 1, 2, 0, 2, 1, 3]
    back = opt("CLOSE_BACKOFF", None)                                               # (piece, seconds): drop to energy 1 for the close
    def energy(t):
        if t >= VOICE_END: return 0
        if back and t >= start(back[0]) + back[1]: return 1
        e = 0
        for s in ORDER:
            if t >= SEC[s] - 1e-6: e = ENERGY.get(s, 2)
        return e
    if COLD:   # low drone, soft pulse, riser into the hit, impact on the downbeat
        add(0.0, pad((38, 45, 50), T_HIT + 0.4), 0.10)
        for k in range(int(T_HIT / BEAT) + 1): add(T_HIT - k * BEAT - BEAT, kick(), 0.35)
        tr, _ = env(1.6); rise = noise(1.6, 900, 9000, 9.0) * (tr / 1.6) ** 2.2; add(T_HIT - 1.6, rise, 0.16)
        add(T_HIT, kick(), 1.0); add(T_HIT, noise(1.8, 2500, 11000, 0.55), 0.20); add(T_HIT, pad((38, 50, 57, 62), 3.0), 0.16)
    pluck_bus_l, pluck_bus_r = np.zeros_like(L), np.zeros_like(R)
    b0 = math.ceil((SEC[ORDER[0]] - T_HIT) / BEAT - 1e-6); b = b0; prev_e = 0
    while T_HIT + b * BEAT < VOICE_END + 0.01:
        tb = T_HIT + b * BEAT; e = energy(tb); bar = (b - b0) // 4; pos = (b - b0) % 4; ch = CH[bar % 4]
        if pos == 0: add(tb, pad([c + 12 for c in ch], 4 * BEAT + 0.3), 0.050 if e else 0.03)
        if e > prev_e and e >= 2: add(tb, noise(1.2, 3000, 11000, 0.35), 0.10); add(tb, kick(), 0.5)   # lift into a bigger section
        for h8 in range(2):
            t8 = tb + h8 * BEAT / 2; step = (pos * 2 + h8) % 8
            tones = [ch[0] + 24, ch[1] + 24, ch[2] + 24, ch[0] + 36]
            if e >= 1:
                sig = pluck(midi(tones[ARP[step]])) * (0.34 if h8 == 0 else 0.24)
                i = int(t8 * SR); pan = 0.35 if step % 2 else -0.35
                pluck_bus_l[i:i + len(sig)] += sig * (1 - max(0, pan)); pluck_bus_r[i:i + len(sig)] += sig * (1 + min(0, pan))
            if e >= 2 or (e == 1 and h8 == 0 and pos in (0, 2)): add(t8, bass(midi(ch[0] - 12 if (step != 7) else ch[2] - 12)), 0.42)
            if e >= 2: add(t8, noise(0.08, 7000, 14000, 0.018), 0.10 if h8 else 0.05, 0.2)
            if e >= 3: add(t8 + BEAT / 4, noise(0.06, 8000, 14000, 0.012), 0.05, -0.2)
        if e >= 2 and pos in (0, 2): add(tb, kick(), 0.62)
        if e >= 3 and pos in (1, 3): add(tb, kick(), 0.40)
        if e >= 2 and pos in (1, 3): add(tb, noise(0.2, 900, 3600, 0.055), 0.26)
        prev_e = e; b += 1
    dl = int(0.75 * BEAT * SR)                                                      # dotted-eighth ping-pong echo on the plucks
    for k, g in enumerate((0.42, 0.22, 0.10), 1):
        src_l, src_r = (pluck_bus_r, pluck_bus_l) if k % 2 else (pluck_bus_l, pluck_bus_r)
        L[k * dl:] += src_l[:len(L) - k * dl] * g; R[k * dl:] += src_r[:len(R) - k * dl] * g
    L += pluck_bus_l; R += pluck_bus_r
    te = VOICE_END                                                                   # outro: last chord rings out under the end shot
    add(te, pad((50, 57, 62, 66), END_CARD + 0.2), 0.11); add(te, pluck(midi(74), 1.6), 0.5); add(te + BEAT / 2, pluck(midi(78), 1.6), 0.4, 0.3)
    add(te + BEAT, pluck(midi(81), 1.8), 0.4, -0.3); add(te, kick(), 0.6); add(te, noise(1.6, 3000, 11000, 0.5), 0.10)
    y = np.stack([L[:n], R[:n]], 1)
    f = int(0.5 * SR); y[-f:] *= np.linspace(1, 0, f)[:, None]
    # level follows the voice: quiet under speech, a little up in the gaps, up again where there is no voice at all
    k = int(0.02 * SR); act = np.repeat(voice_active, k)[:n].astype(float); act = np.pad(act, (0, n - len(act)))
    a_up, a_dn = math.exp(-1 / (0.06 * SR)), math.exp(-1 / (0.35 * SR))
    sm = signal.lfilter([1 - a_dn], [1, -a_dn], np.maximum(act, signal.lfilter([1 - a_up], [1, -a_up], act)))
    t = np.arange(n) / SR; alone = ((t < SEC[ORDER[0]] - 0.2) | (t > VOICE_END)).astype(float)
    alone = signal.lfilter([1 - a_dn], [1, -a_dn], alone)
    gain_db = MUSIC_UNDER_VOICE - DUCK * np.clip(sm, 0, 1) + (MUSIC_ALONE - MUSIC_UNDER_VOICE) * alone
    return y, gain_db

def build_audio():
    voice = build_voice(); wavfile.write(os.path.join(WORK, "voice_raw.wav"), SR, (np.clip(voice, -1, 1) * 32767).astype(np.int16))
    lo = subprocess.run(["ffmpeg", "-hide_banner", "-i", os.path.join(WORK, "voice_raw.wav"), "-af", "ebur128", "-f", "null", "-"],
                        capture_output=True, text=True).stderr
    vg = 10 ** ((LUFS - float([l for l in lo.splitlines() if l.strip().startswith("I:")][-1].split()[1])) / 20)
    voice *= vg
    k = int(0.02 * SR); fr = voice.mean(1)[:len(voice) // k * k].reshape(-1, k); rms = np.sqrt((fr ** 2).mean(1))
    active = rms > 10 ** (-32 / 20)                                 # speech frames (after gain)
    speech_db = 20 * np.log10(np.sqrt((fr[active] ** 2).mean()))
    music, gdb = synth_music(active)
    ra, rb = opt("MUSIC_REF", (ORDER[min(1, len(ORDER) - 1)], ORDER[-1]))         # the bed's own level is measured over these sections
    ref = np.sqrt((music[int(SEC[ra] * SR):int(SEC[rb] * SR)] ** 2).mean())
    music *= (10 ** (speech_db / 20) / ref) * (10 ** (gdb / 20))[:, None]
    nat = build_nat()
    mix = voice + music + nat
    for nm, s in (("voice", voice), ("music", music), ("nat", nat), ("mix", mix)):
        wavfile.write(os.path.join(WORK, f"{nm}.wav"), SR, s.astype(np.float32))
    bed = music + nat; bfr = bed.mean(1)[:len(bed) // k * k].reshape(-1, k); brms = np.sqrt((bfr ** 2).mean(1)) + 1e-9
    ratio = 20 * np.log10(rms[active] / brms[active])
    print(f"mix: speech {speech_db:.1f} dBFS; voice over music+nat while he speaks: median {np.median(ratio):.1f} dB, "
          f"worst 5% {np.percentile(ratio, 5):.1f} dB; voice gain {20 * np.log10(vg):+.1f} dB")
    return os.path.join(WORK, "mix.wav")

# ---------------------------------------------------------------- RENDER
def encoder_args():
    trc = probe(INTERVIEW)[3]
    if trc == "arib-std-b67": tags = ("bt2020", "arib-std-b67", "bt2020nc")          # iPhone HDR (HLG): keep it HDR
    elif trc == "smpte2084": tags = ("bt2020", "smpte2084", "bt2020nc")
    else: tags = ("bt709", "bt709", "bt709")
    encs = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    if "hevc_videotoolbox" in encs:
        v = ["-c:v", "hevc_videotoolbox", "-profile:v", "main10", "-b:v", "13M"]
    else:
        v = ["-c:v", "libx265", "-preset", "medium", "-crf", "18",
             "-x265-params", f"colorprim={tags[0]}:transfer={tags[1]}:colormatrix={tags[2]}"]
    return v + ["-pix_fmt", "p010le" if "videotoolbox" in v[1] else "yuv420p10le", "-tag:v", "hvc1",
                "-color_primaries", tags[0], "-color_trc", tags[1], "-colorspace", tags[2], "-color_range", "tv"]

def render(orient, mix):
    g = GEOM[orient]; shots = prepare(RAW_SHOTS, orient)
    out = os.path.join(OUT_DIR, f"{OUTPUT}_{orient}.mp4")
    cmd, fc = ["ffmpeg", "-v", "error", "-y"], []
    for i, sh in enumerate(shots):
        cmd += ["-ss", f"{sh['cin']:.3f}", "-t", f"{sh['dur'] + 0.5:.3f}"] + (["-noautorotate"] if sh["clip"] in NOROT else []) + ["-i", clip(sh["clip"])]
        fc.append(shot_filter(i, sh, g["W"], g["H"], g["SW"]))
    na = len(shots)
    fc.append("".join(f"[v{i}]" for i in range(na)) + f"concat=n={na}:v=1:a=0[v]")
    fc.append(f"[{na}:a]alimiter=limit={10 ** (PEAK / 20):.3f}:level=false:attack=5:release=60,aresample=44100[a]")
    script = os.path.join(WORK, f"graph_{orient}.txt"); open(script, "w").write(";\n".join(fc))
    cmd += ["-i", mix, "-/filter_complex", script, "-map", "[v]", "-map", "[a]"] + encoder_args() + [
            "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-movflags", "+faststart", out]
    run(cmd); print("->", out)

def main():
    print(f"{'out':>13}  {'dur':>5}  shot")
    for sh in SHOTS:
        print(f"{sh['t0']:6.2f}-{sh['t0'] + sh['dur']:5.2f}  {sh['dur']:5.2f}  {sh['label']}  [{sh['clip']} {sh['cin']:.2f}-{sh['cin'] + sh['dur']:.2f}]"
              + (f"\n{'':22}{sh['line']}" if sh["line"] else ""))
    print(f"total {TOTAL:.2f}s; sections start on beats: " + ", ".join(f"{k} {v:.2f}" for k, v in SEC.items()))
    for w in warnings(): print("WARNING:", w)
    if DRY: return
    os.makedirs(WORK, exist_ok=True); os.makedirs(OUT_DIR, exist_ok=True)
    mix = build_audio()
    for o in ORIENTS: render(o, mix)

if __name__ == "__main__":
    main()
