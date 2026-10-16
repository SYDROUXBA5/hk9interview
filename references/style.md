# The approved style

This is the edit the client signed off ("the type of edit I like"): a 92 s K-9 handler referral, delivered
vertical and horizontal. Reproduce its feel; the numbers are starting points that worked, not laws.

## Shape

| part | length | what happens |
|---|---|---|
| cold open | ~7.5 s | natural sound only: the handler's warning, "Go!", the dog running, the bite; music rises into the bite and its first downbeat lands on it |
| intro, on camera | ~3.5 s | name, rank, agency; one punch-in if a filler was cut |
| body | ~70 s | one action shot per line; sections: why this vendor/dog, selection, the dog's character, "ready to work", the course, confidence, first real result |
| close, on camera | ~5.5 s | the recommendation's last lines, to camera |
| end | ~2.6 s | the dog facing camera, music rings out |

Total 60-105 s; never over 1:45. Each section starts on a music beat, with at least 0.15 s of air before it.

## Picture

- No captions, no name tags, no graphics, no end-card text. (Graphics/caption versions existed; the client preferred
  this "clean" one.)
- Source is 16:9 phone footage (1080p or 4K, iPhone HLG HDR kept as HDR). 9:16 = a 1080x1920 crop of the source
  scaled to 1920 high (the crop is 0.316 of the source width); 16:9 = the whole frame.
- Shots 2-7 s, hard cuts. A list in the voice gets a three-shot montage (~0.85 s each).
- Every shot is ACTION matched to the line: searching, alerting, biting, trailing, driving forward. Rejected by the
  client: set-up moments (harnessing the dog) and frames where the subject has left (empty car panel).
- Camera on every shot, smoothed (~0.18 s gaussian on the path):
  - follow the subject: `keys` at least every 0.5 s while it moves; the dog's head never touches the crop edge
  - slow push-in: zoom 1.0 → 1.07-1.20 over the shot
  - punch on cuts into action: 0.04-0.08 extra zoom settling in 0.1 s; whip blur ("i") on the 2-3 hardest cuts
- Talking head: measured x (he stood at 0.42-0.45 of the frame and drifted), cy 0.36, zoom 1.15 → 1.25 in 9:16.
  In 16:9 the same shots are pulled back by 0.15 zoom (the source has little headroom; the 9:16 push-in cut his head).
- A filler cut on camera: split the shot at the cut and jump to a tighter framing (zoom about 1.38-1.40), then cut
  to b-roll soon after.

## Sound

| layer | level | notes |
|---|---|---|
| voice | -16 LUFS integrated, peaks under -1.5 dBFS | denoised (about -17 dB on the background, steady, no gating), 80 Hz high-pass, 20 ms crossfades at every splice, room tone in every gap |
| music | -15 dB under the speech level while he talks, a further 5 dB duck on words, -8 dB where there is no voice | synthesised in the build: D major I-vi-IV-V, 112 bpm, plucks with ping-pong echo, bass, soft kick/hats; energy 1-3 per section; riser and impact for the cold open; final chord rings under the end |
| natural sound | cold open at 0 dB; under the body at -13/-14 dB | tight windows only (barks, the decoy's shout, a yelp at the grip); transcribed to be sure no one else is talking |

Voice over music+natural sound measured about 18 dB median while he speaks (worst 5% about 6 dB): the voice is
always on top.

## Delivery

Two files with the same cut, timing and identical audio: `<name>_vertical.mp4` (1080x1920) and
`<name>_horizontal.mp4` (1920x1080), HEVC 10-bit, HLG tags when the source is HLG, 30 fps, AAC 192k.
