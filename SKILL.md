---
name: hk9interview
description: Edits phone-shot referral or testimonial interview footage (one interview clip plus b-roll clips) into a finished 60-105 s referral film, vertical 9:16, horizontal 16:9 or both. It first asks four quick questions (length, format, how it opens, who picks the answers), then cuts out the interviewer's voice, picks the strongest answers, covers each line with matching action b-roll framed on the subject, removes "uh"/"um", cleans the background noise and lays a quiet synthesised music bed under the voice, in one house style with no captions or graphics. Use this whenever someone has interview + b-roll footage of a handler, client, officer or customer and wants a referral, testimonial or review video, or asks to cut the interviewer out, match b-roll to what is said, clean up a phone-mic interview, remove filler words, or make vertical or horizontal versions, even if they never say "referral". Built on K-9 handler referrals and works for any spoken testimonial.
---

# HK9 interview: referral film from interview footage

You are making the kind of referral film the client approved: the person speaks, the viewer watches the dog (or the
work) do exactly what is being described. No captions, no graphics, no name plates; the story is told by the voice
and by action shots. Full detail of the look and sound is in `references/style.md`. Read it before choosing shots.

The whole edit lives in one Python "edit file" (copy `assets/edit_template.py`); `scripts/build.py` renders it.
That makes every revision cheap: change a number, run `--dry` (seconds), render, check.

## First, ask (before touching the footage)

Ask these four in one go: with the AskUserQuestion tool when you have it (recommended option first), otherwise as
a short numbered list. Skip any the request already answers.

1. **Length**: "How long should the film be?"
   - About 90 s (Recommended): the full story arc
   - About 60 s: who he is, why this dog/vendor, the dog, the proof, the recommendation
   - Up to 1:45: the full arc with the longer answers (the style's ceiling)
   - (Other: an exact length)
2. **Format**: "Which format?"
   - Both vertical and horizontal (Recommended): same cut, identical audio
   - Vertical 9:16 only: Reels, TikTok, Shorts
   - Horizontal 16:9 only: YouTube, website, a TV screen
3. **Opening**: "How should it open?"
   - Action cold open (Recommended): 6-8 s of natural sound (the warning, the send, the bite) before he speaks
   - Straight on camera: he introduces himself from the first frame
4. **Answers**: "Who picks the answers?"
   - You pick the strongest (Recommended)
   - I'll choose: after transcribing, show the answers as a short numbered list (one line each, with source times)
     and let them pick

Also needed, and usually in the request already: the footage folder (ask in plain words if missing). The interviewer
is found automatically by pitch; ask only if two voices are hard to tell apart.

Everything else is the house style: no captions or graphics, action b-roll, fillers removed, background cleaned,
quiet music bed. Do not ask about it; follow it unless the user volunteers a change (for example "no music" means
`MUSIC = False` in the edit file).

Write the answers into the edit file: `TARGET_LENGTH` (seconds), `FORMATS` (`("vertical", "horizontal")`,
`("vertical",)` or `("horizontal",)`), and `COLD` (`None` for straight on camera). `--dry` then warns if the cut is
more than 10% off the length asked for.

## Setup

Check the tools once: `ffmpeg -version` (8.x; on a Mac it uses the hardware HEVC encoder, elsewhere libx265),
`python3 -c "import numpy, scipy, PIL"`, `whisper-cli --help` with a model at `~/.whisper-models/ggml-small.en.bin`
(or `WHISPER_MODEL=...`). If something is missing, tell the user what to install (README.md) rather than improvising.

Work in a folder next to the footage (e.g. `<footage>/../_edit/`). Never write into or modify the source clips.
Delegate bulk mechanical reading (long transcripts, many contact sheets) to a cheaper sub-agent if you have one,
and keep the judgement calls (which answer, which shot) yourself.

## Workflow

`S` below means this skill's `scripts/` folder.

**1. Inventory.** `python3 S/inventory.py FOOTAGE OUT` lists every clip (duration, played size, HDR, rotation flag,
audio) and writes contact sheets. Look at the sheets: note what each b-roll clip shows and when. A landscape clip with
a 90/270 rotation flag that looks wrong goes in the edit's `NOROT`.

**2. Transcript and voices.** `python3 S/transcribe.py INTERVIEW OUT` gives the answers with source timestamps.
`python3 S/speakers.py INTERVIEW map` shows pitch/level per second; learn the two voices (on the first interview she
was 180-290 Hz and about 10 dB louder because she held the phone; he was about 105 Hz), then
`speakers.py INTERVIEW runs <threshold>` lists her stretches. Questions and her reactions are never used.

**3. Choose the answers** (or let the user choose, if that was their answer). Build the story in sections, typically: who he is (on camera) → why this vendor / this
dog → how the dog was chosen → the dog's character → "ready to work" → the course → confidence leaving → first
real result on the job (the strongest proof line) → recommendation, closing on camera. Fit the length they asked for: about 60 s keeps
intro, one "why", the dog, the proof and the recommendation; about 90 s is the full arc; never pad with b-roll-only
stretches to reach a length. Cut mid-answer where the sense allows, and drop repeats. Put each piece's in/out in silence: read the level envelope
(`fillers.py formants CLIP A-B` prints level every 30 ms), never Whisper's word times, which drift by 0.2-0.5 s.

**4. Fillers.** Remove the "uh"/"um"s: `fillers.py scan` on a voice track lists candidates (Whisper with a
filler-heavy prompt also invents some, especially at cut points), `fillers.py check INTERVIEW A-B` verifies each
in the source (level, pitch, formants, Whisper on the isolated snippet). Real ones go in `CUTS` or move a piece edge.
A filler on camera is cut and hidden by splitting the on-camera shot and punching in (zoom +0.2) at the cut.
Leave 0.1-0.25 s of natural pause; read the full method in the `fillers.py` docstring.

**5. Cold open** (only if they chose it; otherwise `COLD = None`, see below). Find 6-8 s of natural-sound action in the b-roll (a K-9 warning, the send, the bite; or the
equivalent big moment for another kind of work). Set `COLD` with `hit` on the impact so the music's first downbeat
lands on it. Transcribe the window: if someone else talks in it, shorten it.
Straight on camera instead: the film's first shot is the talking head from output 0, while his first word lands on the
first beat (about 0.5 s in), so its clip_in is the piece's source in-point minus that lead; `--dry` prints the exact
value in its sync warning ("set its clip_in to ...").

**6. Match b-roll to every line.** One shot per line or half-line, chosen for what is being said, and always ACTION:
the dog searching, alerting, biting, trailing, driving forward; the handler working the dog. The client rejected
set-up moments (putting a harness on) and frames where the subject has left the shot (an empty car door). Rules:
- literal where possible ("new cars" → the dog working along a car; "we found drugs" → the alert on the door seam)
- the subject (usually the dog's head) stays inside the crop for the whole shot, including in 9:16
- shots of 2-7 s; a three-shot quick montage (~0.85 s each) for a list ("detection, obedience, apprehension")
- open on camera right after the cold open, return to camera for the closing lines, and only otherwise if no shot fits
- use each moment of b-roll once; prefer clips not used in earlier versions if the user asks for "new" footage

**7. Frame every shot.** `FOOTAGE=... python3 S/frames.py grid OUT.jpg CLIP:START:END:STEP ...` gives source frames
with a 0.1 grid: write `keys` from where the subject is (cx, cy). For the talking head use
`python3 S/headpos.py INTERVIEW A-B` (never assume he is centred). Add slow push-ins (`zk`), a small punch on cuts
into action, whip blur on the hardest cuts. Values the client liked are in `references/style.md`.

**8. Natural sound.** In `nat()`, lay a few tight windows from the b-roll under the voice at -13/-14 dB: barks under
a hold, the decoy's shout at a grip. Each window must be clean of other voices: transcribe it.

**9. Build.** `python3 S/build.py edit.py --dry` prints the timeline (every shot, its source range and its line) and
warnings; fix and repeat until it reads right. Then `python3 S/build.py edit.py` renders the formats chosen:
`OUTPUT_vertical.mp4` (1080x1920) and/or `OUTPUT_horizontal.mp4` (1920x1080), same cut and identical audio.
`--dry` also checks that every on-camera shot is in sync with the voice and none runs across a cut: fix every
warning it prints before rendering.
Look at the "level at each voice piece's edge" lines: any edge marked "on a sound" needs moving.

**10. Check, then report.** `python3 S/qa.py OUTPUT_vertical.mp4 WORK` prints duration, loudness (target -16
LUFS), the transcript, filler candidates and high-pitch runs, and writes a frame strip. Open the strip and confirm
the subject is in frame in every shot (also check the horizontal one). Report to the user: length (against what they asked
for), the shot list (time, what we see, the line), what you could not confirm by ear, and the file path(s). Flag ear-only items
plainly (splices, music level, any remaining background sound); never claim you listened.

## Revisions

- Confirm which file the user means before editing (a screenshot alone does not say which version they watched).
- "Change this shot to action": find the shot in the `--dry` timeline, pick an unused action moment that fits the
  line, measure it on a grid, check rendered frames.
- "Background noise": `DENOISE` in the edit; deeper than gmin -24 dB / beta 1.7 gains little and starts to sound
  processed. The method and its history are in `references/lessons.md`. Never gate the pauses (it pumps).
- Re-render only the versions asked for, under the same names unless told otherwise; sources stay untouched.

## Files

| file | what it is |
|---|---|
| `scripts/build.py` | renders an edit file to vertical + horizontal (voice, denoise, music, natural sound, framing) |
| `scripts/denoise.py` | MMSE log-spectral speech denoiser, noise learned from the interview's own pauses |
| `scripts/inventory.py` | clip list + contact sheets |
| `scripts/transcribe.py` | Whisper transcript with source timestamps |
| `scripts/speakers.py` | interviewer vs interviewee by pitch and level |
| `scripts/fillers.py` | find and verify "uh"/"um" |
| `scripts/frames.py` | gridded source frames for framing; frame strips of a render |
| `scripts/headpos.py` | talking-head x position over time |
| `scripts/qa.py` | final numbers and checks on a render |
| `assets/edit_template.py` | the edit file to copy and fill in |
| `references/style.md` | the approved look and sound, with numbers |
| `references/lessons.md` | what went wrong before and how it was fixed; read when something looks or sounds off |
