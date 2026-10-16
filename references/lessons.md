# Lessons from the first film

Read the section that matches the problem in front of you.

## Voice and the interviewer
- The interviewer held the phone, so she was about 10 dB louder than him and 180-290 Hz against his ~105 Hz. A
  per-frame autocorrelation pitch + level pass (`speakers.py`) finds her exactly. Short high blips inside his phrases
  were his own vowels, a beep or birds; check those with Whisper on the isolated snippet before cutting.
- Place cuts in measured silence. The build prints the level at every piece edge; above about -40 dB means the cut
  lands on a sound. A cut once left half a word audible, and a piece once started on his "uh".
- Whisper word times are 0.2-0.5 s off around pauses, and `-dtw` with a prompt garbled an edited track. Use Whisper
  for words, the level envelope for times. To learn what one short sound is, transcribe just that snippet padded
  with silence: the most reliable test found.

## Fillers
- Whisper drops fillers unless prompted with a filler-heavy prompt; prompted, it also invents them in pauses and at
  splices and mistimes them. Treat its list as candidates, verify each in the source (`fillers.py check`).
- "I'm" and "um" can look alike: in "um" F1 drops straight from ~750 to ~250 (nasal) with F2 flat near 1200; in
  "I'm" F2 rises toward 1800-2000 first. If unsure, cutting it is usually harmless to the sense; Whisper the joined
  phrase to be sure no needed word went with it (a short "the" right after an "uh" nearly went with it).
- On camera a cut shows as a jump: split the shot and punch in at the cut.

## Background noise
- Phone-mic outdoor interview: ambience around -45 dBFS plus a hum line. ffmpeg `afftdn` barely touched it.
- A first fix (notch + afftdn + `agate` expander) sounded WORSE to the client: the gate cut noise 9 dB in the pauses
  but only 0.4 dB under speech, so the background pumped in and out. A pause-only noise metric hid this. Always
  measure the noise under speech as well as in the pauses.
- What works (`denoise.py`): MMSE log-spectral amplitude (Ephraim-Malah) with a decision-directed a-priori SNR, the
  noise profile learned from the interview's own speech-free stretches, a gain floor and no gating, so the
  background drops by the same amount everywhere. gmin -18 dB gives about -14 dB with speech and consonants intact;
  the build uses -24 dB / beta 1.7 (about -17 dB) because the music covers side effects. Deeper gains little: what
  remains is moving sound (birds, rustle). The next step beyond that is an AI voice isolator (ffmpeg `arnndn` with
  an RNNoise model, or an external service): ask the user before downloading or uploading anything.

## Picture
- Measure, never assume: a centred crop put the talking head visibly off-centre, the first thing the client
  noticed. Use `headpos.py` (skin-tone centroid; sunlight skewed it ~0.025 toward the lit side) and check a frame.
- Read b-roll keys off gridded frames, then check frames of the RENDER: with a handheld camera, keys read off the
  source were up to 300 px off in places, and a crop once panned onto an empty door after the dog had left it.
- iPhone clips re-exported with a wrong rotation flag play sideways; read them with `-noautorotate` (`NOROT`).
- 16:9 needs less zoom on the talking head than 9:16: the same push-in cut the top of his head.
- In HLG footage, white graphics/text belong at ~86% (RGB 219) or they glare; this style has none, but keep it in
  mind if a user asks for text.

## Natural sound
- B-roll audio is full of other people: a trainer's comment, praise at the bite, someone talking right after.
  Cut windows tight around the event and transcribe each. A shout or bark from another take of the same scene is
  fine when the clip's own sound is unusable.

## Working with the client
- Confirm which version a note is about before editing; once a fix went into the wrong version.
- They prefer action b-roll over set-up moments, and a clean film over captions and graphics.
- Report what only an ear can judge, plainly, every time.
