# hk9interview

A Claude Code skill that turns phone-shot referral-interview footage (one interview clip plus b-roll clips) into a
finished referral film, delivered vertical 9:16 and horizontal 16:9. It is the method behind a K-9 handler referral
film: interviewer cut out, the best answers, action b-roll matched to every line and framed on the
dog, "uh"/"um" removed, background noise cleaned, a natural-sound cold open and a quiet synthesised music bed. No
captions or graphics.

Your footage never leaves your computer: everything runs locally with ffmpeg, Python and Whisper.

## Install

```bash
git clone https://github.com/SYDROUXBA5/hk9interview.git ~/.claude/skills/hk9interview
```

Then in Claude Code type `/hk9interview` (or just ask for a referral video from your interview footage).
It first asks four quick questions: how long the film should be, vertical / horizontal / both, whether it opens on
an action moment or straight on camera, and whether it picks the answers or you do. The rest is the house style.

## Requirements

- macOS recommended (uses the hardware HEVC encoder; elsewhere it falls back to libx265, slower)
- ffmpeg 8: `brew install ffmpeg`
- Python 3 with numpy, scipy and Pillow: `pip3 install numpy scipy pillow`
- whisper.cpp and an English model:
  ```bash
  brew install whisper-cpp
  mkdir -p ~/.whisper-models
  curl -L -o ~/.whisper-models/ggml-small.en.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.en.bin
  ```
  (or point `WHISPER_MODEL` at a model you already have)

## How it works

The whole edit is one Python file (copy `assets/edit_template.py`): which stretches of the interview play, which
fillers are cut, which shot covers each line and where the subject sits in each frame. `scripts/build.py edit.py`
renders it; `--dry` prints the timeline in seconds, so every change is quick to check. `SKILL.md` is the step-by-step
method Claude follows; `references/style.md` is the look and sound; `references/lessons.md` is what went wrong the
first time and how it was fixed.

The music is synthesised by the build script (no samples, nothing licensed), so the films are safe to post.
