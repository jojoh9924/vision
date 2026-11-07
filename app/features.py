"""Turn 21 hand landmarks into the simple features gestures are matched on."""

import math
from dataclasses import dataclass

WRIST = 0
THUMB_IP, THUMB_TIP = 3, 4
INDEX_MCP, INDEX_TIP = 5, 8
MIDDLE_MCP, MIDDLE_TIP = 9, 12
RING_TIP = 16
PINKY_MCP, PINKY_TIP = 17, 20

FINGER_NAMES = ("thumb", "index", "middle", "ring", "pinky")
PINCH_FINGERS = ("index", "middle", "ring", "pinky")
_TIP = {"index": INDEX_TIP, "middle": MIDDLE_TIP, "ring": RING_TIP, "pinky": PINKY_TIP}
_PIP = {"index": 6, "middle": 10, "ring": 14, "pinky": 18}
_MCP = {"index": INDEX_MCP, "middle": MIDDLE_MCP, "ring": 13, "pinky": PINKY_MCP}

PINCH_RATIO = 0.25  # thumb-to-fingertip distance, as a fraction of hand size
PINCH_REACH = 1.05  # pinching fingertip must be this far past its knuckle (wrist-relative)


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


@dataclass(frozen=True)
class HandFeatures:
    fingers: tuple          # 5 bools: thumb, index, middle, ring, pinky extended
    pinch: str | None       # finger pinched against the thumb, or None
    orientation: str        # up | down | left | right
    pointer: tuple          # index fingertip: drives the cursor while pointing
    knuckle: tuple          # index knuckle: stable reference for drags
    pinch_gap: float        # thumb tip to index tip distance / hand size
    bbox: tuple             # (x_min, y_min, x_max, y_max)
    hand_size: float
    gaps: tuple = ()        # thumb-to-fingertip distance / hand size, index middle ring pinky

    @property
    def fingers_str(self) -> str:
        return "".join("1" if f else "0" for f in self.fingers)


def extract(landmarks) -> HandFeatures:
    """landmarks: sequence of 21 (x, y) pixel tuples, image coordinates (y down)."""
    lm = landmarks
    wrist = lm[WRIST]
    hand_size = max(_dist(wrist, lm[MIDDLE_MCP]), 1.0)

    thumb = _dist(lm[THUMB_TIP], lm[PINKY_MCP]) > _dist(lm[THUMB_IP], lm[PINKY_MCP])
    fingers = [thumb]
    for name in PINCH_FINGERS:
        fingers.append(_dist(lm[_TIP[name]], wrist) > _dist(lm[_PIP[name]], wrist))

    # A pinch is the thumb touching exactly one fingertip that reaches past its own
    # knuckle. A thumb resting on curled fingers (fist, or one finger raised) does
    # not count: those fingertips sit closer to the wrist than their knuckle.
    near = [name for name in PINCH_FINGERS
            if _dist(lm[THUMB_TIP], lm[_TIP[name]]) < PINCH_RATIO * hand_size
            and _dist(lm[_TIP[name]], wrist) > PINCH_REACH * _dist(lm[_MCP[name]], wrist)]
    if len(near) >= 3:
        pinch = "all"          # fingertips bunched on the thumb
    elif len(near) == 1:
        pinch = near[0]
    else:
        pinch = None

    dx = lm[MIDDLE_MCP][0] - wrist[0]
    dy = wrist[1] - lm[MIDDLE_MCP][1]  # flip so positive is up
    angle = math.degrees(math.atan2(dy, dx))
    if -45 <= angle < 45:
        orientation = "right"
    elif 45 <= angle < 135:
        orientation = "up"
    elif -135 <= angle < -45:
        orientation = "down"
    else:
        orientation = "left"

    pointer = tuple(lm[INDEX_TIP])
    knuckle = tuple(lm[INDEX_MCP])
    pinch_gap = _dist(lm[THUMB_TIP], lm[INDEX_TIP]) / hand_size
    gaps = tuple(_dist(lm[THUMB_TIP], lm[_TIP[name]]) / hand_size for name in PINCH_FINGERS)

    xs = [p[0] for p in lm]
    ys = [p[1] for p in lm]
    bbox = (min(xs), min(ys), max(xs), max(ys))

    return HandFeatures(tuple(fingers), pinch, orientation, pointer, knuckle, pinch_gap, bbox, hand_size, gaps)
