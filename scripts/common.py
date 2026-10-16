"""Shared helpers for the hk9interview tools: audio loading, pitch, formants, Whisper."""
import os, subprocess, tempfile
import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter, resample_poly

WHISPER_CLI = os.environ.get("WHISPER_CLI", "whisper-cli")
WHISPER_MODEL = os.path.expanduser(os.environ.get("WHISPER_MODEL", "~/.whisper-models/ggml-small.en.bin"))
FILLER_PROMPT = "Um, uh, so, uh, we, uh, you know, uh, went up there and, um, uh, yeah."
FILLERS = {"uh", "um", "uhm", "ah", "er", "erm", "hmm"}


def load_mono(path, sr=48000):
    """Any audio or video file -> mono float array at sr (via ffmpeg)."""
    tmp = os.path.join(tempfile.gettempdir(), f"hk9i_{os.getpid()}.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-vn", "-ac", "1", "-ar", str(sr), tmp], check=True)
    x = wavfile.read(tmp)[1].astype(np.float64) / 32768.0
    os.remove(tmp)
    return x


def level_db(x, sr, a, b):
    s = x[int(a * sr):int(b * sr)]
    return 20 * np.log10(np.sqrt((s ** 2).mean()) + 1e-9) if len(s) else -120.0


def envelope(x, sr, a, b, step=0.01, win=0.02):
    """Level in dB every `step` seconds from a to b."""
    out, t = [], a
    while t < b - 1e-9:
        out.append(level_db(x, sr, t, t + win)); t += step
    return np.array(out)


def pitch(x, sr, a, b, lo=70, hi=350):
    """Autocorrelation F0 of x[a:b] in Hz, 0 when unvoiced."""
    s = x[int(a * sr):int(b * sr)]
    if len(s) < int(0.04 * sr): return 0.0
    s = (s - s.mean()) * np.hanning(len(s))
    c = np.correlate(s, s, "full")[len(s) - 1:]
    if c[0] <= 0: return 0.0
    k0, k1 = int(sr / hi), int(sr / lo)
    k = k0 + int(np.argmax(c[k0:k1]))
    return sr / k if c[k] > 0.3 * c[0] else 0.0


def formants(x, sr, a, b, order=10):
    """First two formants (Hz) of x[a:b] by LPC at 8 kHz. A steady F1 ~500-700 / F2 ~1100-1300 vowel,
    often followed by a nasal (F1 ~250), is what "uh"/"um" looks like."""
    y = resample_poly(x[int(a * sr):int(b * sr)], 8000, sr); fs = 8000
    if len(y) < order + 2: return []
    f = lfilter([1, -0.95], 1, y) * np.hamming(len(y)); r = np.correlate(f, f, "full")[len(f) - 1:len(f) + order]
    if r[0] <= 0: return []
    A = np.array([1.0]); e = r[0]
    for i in range(1, order + 1):
        k = -(r[i] + np.dot(A[1:], r[i - 1:0:-1])) / e; A = np.concatenate([A, [0]]); A = A + k * A[::-1]; e *= 1 - k * k
    roots = [z for z in np.roots(A) if z.imag > 0]
    fb = sorted((np.angle(z) * fs / 2 / np.pi, -0.5 * fs / np.pi * np.log(abs(z))) for z in roots)
    return [round(fr) for fr, bw in fb if fr > 200 and bw < 400][:2]


def whisper(wav16, prompt=None, words=False, out_stem=None):
    """Run whisper-cli on a 16 kHz mono wav. words=True -> list of (start_s, end_s, word); else plain text."""
    cmd = [WHISPER_CLI, "-m", WHISPER_MODEL, "-f", wav16, "-l", "en", "-np"]
    if prompt: cmd += ["--prompt", prompt]
    if words:
        stem = out_stem or wav16[:-4] + "_words"
        subprocess.run(cmd + ["-ml", "1", "-sow", "-ocsv", "-of", stem], capture_output=True, check=True)
        import csv
        rows = list(csv.reader(open(stem + ".csv")))[1:]
        return [(int(a) / 1000, int(b) / 1000, w.strip()) for a, b, w in rows]
    return subprocess.run(cmd + ["-nt"], capture_output=True, text=True).stdout.strip().replace("\n", " ")


def to_wav16(x, sr, path, pad=0.0, normalise=False):
    """Write x (mono, at sr) as 16 kHz wav, optionally padded with silence and peak-normalised."""
    y = resample_poly(x, 16000, sr)
    if normalise: y = y / max(1e-6, abs(y).max()) * 0.5
    if pad: z = np.zeros(int(pad * 16000)); y = np.concatenate([z, y, z])
    wavfile.write(path, 16000, (np.clip(y, -1, 1) * 32767).astype(np.int16))
    return path


def snippet_text(x, sr, a, b, workdir):
    """Whisper on x[a:b] alone, padded with silence: the reliable way to learn what one short sound is."""
    p = to_wav16(x[int(a * sr):int(b * sr)], sr, os.path.join(workdir, f"snip_{a:.2f}.wav"), pad=0.8, normalise=True)
    return whisper(p)
