"""EDIT FILE: the whole film as data. Copy this next to the footage (or anywhere), fill it in, then:
    python3 <skill>/scripts/build.py edit.py --dry      # timeline + warnings, seconds; run after every change
    python3 <skill>/scripts/build.py edit.py            # renders OUTPUT_vertical.mp4 and/or OUTPUT_horizontal.mp4 (FORMATS)

Times are in seconds. "Source" times are positions inside a clip; "output" times are positions in the film.
Every number below is a placeholder showing the shape; replace all of them with measured values.
"""

# ---------------------------------------------------------------- FILES
FOOTAGE = "/path/to/footage"          # folder holding the interview and the b-roll (only read, never written)
OUT_DIR = FOOTAGE                     # where the two mp4s go
OUTPUT = "Referral_Lastname_Agency"   # -> Referral_Lastname_Agency_vertical.mp4 / _horizontal.mp4
INTERVIEW = "IMG_0001"                # the interview clip (file name, stem, or a unique tail such as "0001")
ROOM_TONE = 14.90                     # start of >= 0.6 s in the interview where nobody speaks (fills gaps in the voice)
NOROT = ()                            # clips with a wrong rotation flag (upright only with -noautorotate), e.g. ("0012",)

# ---------------------------------------------------------------- THE USER'S ANSWERS (asked before editing)
TARGET_LENGTH = 90                    # seconds they asked for (about 60 / 90 / up to 105); --dry warns if 10% off
FORMATS = ("vertical", "horizontal")  # or ("vertical",) or ("horizontal",)
MUSIC = True                          # the house style has a quiet music bed; False only if they ask for none

# ---------------------------------------------------------------- SOUND
BPM = 112                             # music tempo; sections start on beats
DENOISE = dict(gmin_db=-24.0, beta=1.7)   # background reduction on the interview (~-17 dB); see references/lessons.md
# Cold open: a few seconds of natural-sound action before he speaks (a warning, the send, the bite...).
# hit = source time of the impact moment; the music's first downbeat lands exactly there.
# None = straight on camera: then the first (on-camera) shot's clip_in = piece in-point minus ~0.5 s (--dry says exactly).
COLD = dict(clip="IMG_0002", cin=5.35, cout=12.45, hit=11.25)
# Music energy per section: 1 = plucks only, 2 = + bass, hats, kick, 3 = + off-beat kick (the action sections).
ENERGY = {"intro": 1, "why": 2, "select": 2, "dog": 1, "ready": 3, "school": 2, "conf": 2, "proof": 3, "rec": 2}
CLOSE_BACKOFF = ("r3", 2.2)           # (piece, s): music drops to energy 1 this long into the closing on-camera piece
END_CARD = 2.6                        # seconds of picture after the last word

# ---------------------------------------------------------------- VOICE: (section, [(piece, source_in, source_out), ...])
# Each piece is one stretch of the interview. Pieces in a section play back to back (20 ms crossfades);
# ("gap", s) inserts silence-with-room-tone. Put every in/out point in measured silence: --dry is quick, and the
# full build prints the level at every edge ("<-- on a sound" means move it). Never include the interviewer.
SECTIONS = [
    ("intro",  [("in1", 5.30, 13.55)]),                                  # name, rank, agency, what they have
    ("why",    [("w1", 19.61, 23.80), ("w2", 25.27, 27.06)]),            # why this vendor / this kind of dog
    ("select", [("sa", 57.62, 58.12), ("sb", 59.53, 62.96)]),            # how the dog was chosen
    ("dog",    [("d1", 144.60, 146.46), ("d2", 147.90, 152.27)]),        # the dog's character
    ("ready",  [("d5", 174.20, 176.95)]),                                # "when it's time to work..." line
    ("school", [("h1", 89.64, 93.90), ("gap", 0.15), ("h2", 100.74, 104.20)]),   # handler course
    ("conf",   [("c1", 121.40, 126.46)]),                                # confidence leaving
    ("proof",  [("p1", 128.74, 135.50)]),                                # first real result on the job
    ("rec",    [("r1", 182.30, 183.84), ("r2", 185.36, 186.10), ("r3", 194.00, 201.72)]),   # recommendation, on camera
]
# Fillers ("uh", "um") inside pieces: (source_in, source_out) ranges removed from whatever piece contains them.
# Find and verify them with scripts/fillers.py; leave 0.1-0.25 s of natural pause around each cut.
CUTS = [
    (7.86, 8.28),        # in1 "... [um] ..."  (on camera: hidden by a punch-in, see CAM1a/CAM1b below)
]

# ---------------------------------------------------------------- PICTURE
def shots(e):
    """Return the shots in order. e.S(label, clip, clip_in, OUTPUT end time, keys, zk=, punch=, whip=, line=)
      label    first word is the shot id (used by nat() below), the rest describes it
      end      an OUTPUT time, from the voice: e.m(piece, source_t), e.start(piece), e.end(piece), e.nxt(section)
               (start of the next section), e.SEC[section], e.VOICE_END, e.TOTAL. A shot starts where the last ended.
      keys     [(clip_t, cx, cy)]: where the SUBJECT is in the 16:9 source (0-1). The crop follows it smoothly.
               Measure with scripts/frames.py grid (b-roll) and scripts/headpos.py (talking head, cy ~0.36).
      zk       [(clip_t, zoom)]: 1.0 = full height; slow push-ins 1.0 -> 1.10-1.20; talking head 1.15 -> 1.25
      punch    extra zoom that settles in 0.1 s after the cut (0.04-0.08; skip on calm shots)
      whip     "i" = motion blur on the first frames (use on high-energy cuts)
    An on-camera shot must read the interview at the same source time as the voice: start it at a piece's source
    in-point and end it at that piece's output end (or at a CUT, then continue in a new shot, punched in, to hide it).
    """
    return [
        e.S("COLD  warning, send, bite", "IMG_0002", 5.35, e.SEC["intro"],
            [(5.35, .20, .65), (8.4, .44, .60), (10.9, .62, .58), (13.0, .80, .64)],
            zk=[(5.35, 1.05), (8.1, 1.20), (8.5, 1.0), (11.3, 1.15), (13.0, 1.22)], line="[natural sound]"),
        e.S("CAM1a on camera", INTERVIEW, 5.30, e.m("in1", 7.86),
            [(5.3, .452, .36), (7.9, .443, .36)], zk=[(5.3, 1.15), (7.86, 1.19)], punch=.05, line="Name, rank, agency."),
        e.S("CAM1b on camera, punched in over the cut filler", INTERVIEW, 8.28, e.m("in1", 9.25),
            [(8.28, .441, .34), (9.3, .437, .34)], zk=[(8.28, 1.38), (9.25, 1.40)], line="One of the two"),
        e.S("B1    handler and dog at heel", "IMG_0003", 15.50, e.nxt("intro"),
            [(15.5, .62, .5), (20.5, .53, .5)], zk=[(15.5, 1.0), (20.5, 1.07)], line="...handlers in the agency."),
        # ... one shot per line, each matched to what he is saying, action over set-up ...
        e.S("CAM2  on camera", INTERVIEW, 196.24, e.VOICE_END,
            [(196.0, .400, .36), (201.8, .385, .36)], zk=[(196.24, 1.15), (201.72, 1.26)], punch=.05, line="Closing lines."),
        e.S("END   dog facing camera", "IMG_0004", 11.20, e.TOTAL, [(11.2, .47, .45)], line="[music out]"),
    ]



# ---------------------------------------------------------------- NATURAL SOUND
def nat(e, SH):
    """(clip, source_in, source_out, OUTPUT time, gain dB). SH["B9"]["t0"] = output start of shot B9.
    Keep windows tight around the event and transcribe each one: b-roll audio is full of other people talking."""
    return [
        ("IMG_0002", 5.35, 7.95, 0.0, 0.0),                    # the cold open's own sound (warning ... "Go!")
        ("IMG_0005", 0.62, 1.00, SH["B1"]["t0"] + 0.12, -13.0),  # e.g. a bark or the decoy's shout, under a shot
    ]
