"""Background-noise clean-up for a phone-mic interview, used by build.py on the whole interview track.

Typical input: outdoor ambience around -45 dBFS plus a steady hum line, recorded by the phone that films.

Method: MMSE log-spectral amplitude estimator (Ephraim & Malah, 1985) with a decision-directed a-priori SNR, run in
numpy on the whole interview before any piece is cut from it.
  - The noise is learned from every speech-free stretch of the interview (found automatically: >= 0.4 s below
    -42 dBFS), so a hum line is part of the noise model.
  - The background is reduced by the same amount in the pauses and under the words, so it does not breathe or pump.
    (Gating the pauses made the noise come and go and sounded worse than no processing; gating is not used.)
  - A gain floor keeps the noise turned down, never removed to silence, which keeps the voice from sounding watery.
    One gain mask drives both channels; timing is unchanged.
Measured on the first interview at the defaults (floor -18 dB): pauses -14.7 dB, noise under speech -14.5 dB, speech
-0.7 dB, 3-8 kHz consonant band -0.4 dB. build.py defaults to floor -24 dB, beta 1.7 (about -17 dB) because its music
bed covers any side effects; deeper gains almost nothing, as what remains is moving sound (birds, rustle).
"""
import hashlib, os, subprocess, tempfile
import numpy as np
from scipy import signal
from scipy.io import wavfile
from scipy.special import exp1

GMIN_DB, ALPHA, BETA, NFFT, HOP = -18.0, 0.98, 1.4, 1024, 256


def speech_free(mono, sr, below_db=-42.0, min_len=0.4):
    """Stretches where nobody is talking, from a 20 ms RMS envelope (10 ms hop, lightly smoothed)."""
    w, h = int(0.02 * sr), int(0.01 * sr); n = (len(mono) - w) // h
    rms = np.array([np.sqrt((mono[i * h:i * h + w] ** 2).mean()) for i in range(n)])
    env = np.convolve(20 * np.log10(rms + 1e-9), np.ones(5) / 5, "same")
    quiet, spans, i = env < below_db, [], 0
    while i < n:
        if quiet[i]:
            j = i
            while j < n and quiet[j]: j += 1
            if (j - i) * 0.01 >= min_len: spans.append((i * 0.01 + 0.05, j * 0.01 - 0.05))
            i = j
        else: i += 1
    return spans


def mmse_lsa(x, sr, noise_spans, gmin_db=GMIN_DB, beta=BETA):
    mono = x.mean(1)
    kw = dict(window="hann", nperseg=NFFT, noverlap=NFFT - HOP)
    f, t, X = signal.stft(mono, sr, boundary="even", padded=True, **kw)
    m = np.zeros(len(t), bool)
    for a, b in noise_spans: m |= (t - NFFT / 2 / sr >= a) & (t + NFFT / 2 / sr <= b)
    lam = beta * (np.abs(X[:, m]) ** 2).mean(1)
    gam = np.abs(X) ** 2 / lam[:, None]
    gmin = 10 ** (gmin_db / 20); G = np.empty_like(gam); prev = np.ones(len(f))
    for l in range(X.shape[1]):
        g = gam[:, l]
        xi = ALPHA * prev ** 2 * (gam[:, l - 1] if l else g) + (1 - ALPHA) * np.maximum(g - 1, 0)
        xi = np.maximum(xi, 10 ** -2.5)
        v = np.maximum(xi / (1 + xi) * g, 1e-8)
        gl = np.minimum(xi / (1 + xi) * np.exp(0.5 * exp1(v)), 1.0)
        gl = np.convolve(np.pad(gl, 1, mode="edge"), [0.25, 0.5, 0.25], "valid")
        G[:, l] = prev = np.maximum(gl, gmin)
    out = np.empty_like(x)
    for c in range(x.shape[1]):
        _, _, Xc = signal.stft(x[:, c], sr, boundary="even", padded=True, **kw)
        _, y = signal.istft(Xc * G, sr, boundary=True, **kw)
        out[:, c] = y[:len(x)]
    return out


def extract_clean(src, out, sr=48000, gmin_db=GMIN_DB, beta=BETA):
    """Write the cleaned interview track to `out` (stereo 16-bit WAV at sr), same length and timing as the source."""
    key = hashlib.md5(f"{os.path.abspath(src)}|{os.path.getmtime(src)}|{sr}|{gmin_db}|{ALPHA}|{beta}|{NFFT}|{HOP}".encode()).hexdigest()[:12]
    cache = os.path.join(tempfile.gettempdir(), f"hk9_clean_{key}.wav")
    if not os.path.exists(cache):
        raw = cache + ".raw.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-ar", str(sr), "-ac", "2", raw], check=True)
        x = wavfile.read(raw)[1].astype(np.float64) / 32768.0
        y = mmse_lsa(x, sr, speech_free(x.mean(1), sr), gmin_db, beta)
        wavfile.write(cache, sr, (np.clip(y, -1, 1) * 32767).astype(np.int16)); os.remove(raw)
    subprocess.run(["cp", cache, out], check=True)
