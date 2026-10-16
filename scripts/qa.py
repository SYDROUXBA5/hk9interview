#!/usr/bin/env python3
"""Final checks on a render. Report the numbers; flag what only a human ear can judge.

Usage:  python3 qa.py VIDEO WORK_DIR [OUT.jpg]
  VIDEO     a rendered mp4 (vertical or horizontal)
  WORK_DIR  the build's WORK folder (holds voice.wav)
Prints: size, duration, integrated loudness (target -16 LUFS) and true peak, the plain Whisper transcript of the
voice track (compare with the edit's lines), filler candidates (fillers.py scan), high-pitch runs in the voice track
(the interviewer must never be audible), and writes a strip of one frame every ~4 s to OUT.jpg (default: next to VIDEO).
"""
import json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_mono, to_wav16, whisper
sys.stdout.reconfigure(line_buffering=True)            # keep our lines in order with the sub-tools' output

if len(sys.argv) < 3: sys.exit(__doc__)
video, work = sys.argv[1], sys.argv[2]
out = sys.argv[3] if len(sys.argv) > 3 else os.path.splitext(video)[0] + "_qa.jpg"
here = os.path.dirname(os.path.abspath(__file__))

info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height,codec_name,color_transfer",
                                  "-of", "json", video], capture_output=True, text=True).stdout)
v = next(s for s in info["streams"] if "width" in s); dur = float(info["format"]["duration"])
print(f"video: {v['width']}x{v['height']} {v['codec_name']} {v.get('color_transfer', '')}, {dur:.2f} s")
lo = subprocess.run(["ffmpeg", "-nostats", "-i", video, "-map", "0:a", "-af", "ebur128=peak=true", "-f", "null", "-"],
                    capture_output=True, text=True).stderr.splitlines()
print("loudness:", " ".join(l.strip() for l in lo if l.strip().startswith(("I:", "Peak:"))))

voice = os.path.join(work, "voice.wav")
if os.path.exists(voice):
    wd = tempfile.mkdtemp(prefix="hk9i_"); x = load_mono(voice, 16000)
    print("\ntranscript of the voice track:\n" + whisper(to_wav16(x, 16000, os.path.join(wd, "v.wav"))))
    print("\nfiller candidates (verify each; Whisper invents some at cut points):")
    subprocess.run([sys.executable, os.path.join(here, "fillers.py"), "scan", voice])
    print("\nhigh-pitch runs in the voice track (interviewer check; short blips can be vowels or birds):")
    subprocess.run([sys.executable, os.path.join(here, "speakers.py"), voice, "runs"])
times = [f"{t:.1f}" for t in [0.5 + i * 4.0 for i in range(int(dur // 4.0) + 1)] if t < dur]
subprocess.run([sys.executable, os.path.join(here, "frames.py"), "strip", out, video, *times])
print("\nFor a human to check by ear: every splice (no clipped word or breath), the music level under the voice, "
      "and that no other voice is audible in the natural-sound moments.")
