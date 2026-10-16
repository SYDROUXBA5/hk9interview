#!/usr/bin/env python3
"""Inventory a footage folder: one line per clip (duration, size as played, HDR, rotation flag) plus contact sheets.

Usage:  python3 inventory.py FOOTAGE_DIR OUT_DIR
Writes OUT_DIR/inventory.txt and OUT_DIR/sheet1.jpg, sheet2.jpg ... (6x6 thumbnails, labelled "clip @time").
The longest clip with continuous speech is usually the interview; everything else is b-roll.
A clip whose stored size is landscape but which carries a 90/270 rotation flag usually has a WRONG flag on
iPhone footage that was re-exported: look at its thumbnail; if it is upright when read with -noautorotate,
put it in the edit's NOROT.
"""
import glob, json, math, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont

VIDEO = (".mov", ".mp4", ".m4v", ".avi", ".mkv")
TW, TH = 320, 180


def probe(p):
    s = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height,color_transfer:stream_side_data=rotation",
                                   "-of", "json", p], capture_output=True, text=True).stdout)
    v = next((x for x in s.get("streams", []) if x.get("codec_type") == "video"), {})
    rot = next((int(d.get("rotation", 0)) for d in v.get("side_data_list", []) if "rotation" in d), 0)
    audio = any(x.get("codec_type") == "audio" for x in s.get("streams", []))
    return float(s["format"].get("duration", 0)), v.get("width", 0), v.get("height", 0), rot, v.get("color_transfer", ""), audio


def main(src, out):
    os.makedirs(out, exist_ok=True)
    clips = sorted(p for p in glob.glob(os.path.join(src, "*")) if p.lower().endswith(VIDEO))
    lines, jobs = [], []
    for p in clips:
        d, w, h, rot, trc, audio = probe(p)
        hdr = {"arib-std-b67": "HLG", "smpte2084": "PQ"}.get(trc, "SDR")
        lines.append(f"{os.path.basename(p):24s} {d:7.1f}s  {w}x{h}  rot {rot:4d}  {hdr}  {'audio' if audio else 'no audio'}")
        if d < 0.5: continue
        n = max(2, min(12, round(d / 4.5)))
        jobs += [(p, d * (i + 0.5) / n, rot) for i in range(n)]
    open(os.path.join(out, "inventory.txt"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))

    def grab(j):
        p, t, rot = j; o = os.path.join(out, f"t_{os.path.basename(p)}_{t:.1f}.jpg")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", p, "-frames:v", "1",
                        "-vf", f"scale={TW}:{TH}:force_original_aspect_ratio=decrease", "-q:v", "4", o])
        return o
    with ThreadPoolExecutor(8) as ex: thumbs = list(ex.map(grab, jobs))
    font = ImageFont.load_default()
    for k in range(math.ceil(len(jobs) / 36)):
        im = Image.new("RGB", (6 * TW, 6 * TH)); d = ImageDraw.Draw(im)
        for i, ((p, t, _), o) in enumerate(zip(jobs[k * 36:(k + 1) * 36], thumbs[k * 36:(k + 1) * 36])):
            x, y = (i % 6) * TW, (i // 6) * TH
            if os.path.exists(o):
                q = Image.open(o); im.paste(q, (x + (TW - q.width) // 2, y + (TH - q.height) // 2)); os.remove(o)
            d.rectangle([x, y, x + 150, y + 16], fill="black"); d.text((x + 3, y + 2), f"{os.path.splitext(os.path.basename(p))[0]} @{t:.0f}s", fill="yellow", font=font)
        im.save(os.path.join(out, f"sheet{k + 1}.jpg"), quality=70)
    print(f"{len(jobs)} thumbnails -> {out}/sheet*.jpg")


if __name__ == "__main__":
    if len(sys.argv) != 3: sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
