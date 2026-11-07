"""Canonical 21-landmark hand model: builds synthetic landmarks for a gesture.

Used by the icon renderer and by tests. Model space: wrist at (0, 0), y up,
wrist-to-middle-MCP distance = 1, hand pointing up.
"""

import math

# (x, y) per landmark, open hand pointing up
OPEN_HAND = [
    (0.00, 0.00),                                              # 0 wrist
    (-0.35, 0.30), (-0.65, 0.60), (-0.85, 0.85), (-1.00, 1.05),  # thumb 1-4
    (-0.35, 1.00), (-0.40, 1.40), (-0.42, 1.65), (-0.44, 1.90),  # index 5-8
    (0.00, 1.00), (0.00, 1.45), (0.00, 1.75), (0.00, 2.00),      # middle 9-12
    (0.30, 0.95), (0.33, 1.35), (0.35, 1.60), (0.37, 1.85),      # ring 13-16
    (0.55, 0.85), (0.60, 1.15), (0.63, 1.35), (0.66, 1.55),      # pinky 17-20
]

FINGER_JOINTS = {"thumb": (1, 2, 3, 4), "index": (5, 6, 7, 8), "middle": (9, 10, 11, 12),
                 "ring": (13, 14, 15, 16), "pinky": (17, 18, 19, 20)}
FINGER_ORDER = ("thumb", "index", "middle", "ring", "pinky")

PINCH_POINT = {"index": (-0.50, 1.50), "middle": (-0.25, 1.55),
               "ring": (-0.05, 1.45), "pinky": (0.15, 1.30), "all": (-0.15, 1.45)}

BONES = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9), (9, 10),
         (10, 11), (11, 12), (9, 13), (13, 14), (14, 15), (15, 16), (13, 17), (0, 17),
         (17, 18), (18, 19), (19, 20)]

ROTATION_DEG = {"any": 0, "up": 0, "left": 90, "down": 180, "right": -90}


def rotate(p, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


def model_points(fingers: str = "11111", pinch: str | None = None) -> list[tuple]:
    """Landmarks in model space. '*' is drawn extended."""
    pts = list(OPEN_HAND)
    for name, ch in zip(FINGER_ORDER, fingers):
        if ch != "0" or name == pinch or (pinch == "all" and name != "thumb"):
            continue
        mcp, pip, dip, tip = FINGER_JOINTS[name]
        if name == "thumb":
            pts[dip] = (-0.40, 0.75)
            pts[tip] = (-0.15, 0.85)
            continue
        m = pts[mcp]
        d = (0.0, 1.0)
        pts[pip] = (m[0] + 0.35 * d[0], m[1] + 0.35 * d[1])
        bend1 = rotate(d, 110)
        bend2 = rotate(d, 160)
        pts[dip] = (pts[pip][0] + 0.2 * bend1[0], pts[pip][1] + 0.2 * bend1[1])
        pts[tip] = (pts[dip][0] + 0.2 * bend2[0], pts[dip][1] + 0.2 * bend2[1])
    if pinch:
        meet = PINCH_POINT[pinch]
        t_mcp = pts[2]
        pts[3] = (t_mcp[0] + 0.55 * (meet[0] - t_mcp[0]) - 0.15, t_mcp[1] + 0.55 * (meet[1] - t_mcp[1]))
        pts[4] = meet
        fingers_to_meet = ("index", "middle", "ring", "pinky") if pinch == "all" else (pinch,)
        for name in fingers_to_meet:
            _, pip, dip, tip = FINGER_JOINTS[name]
            p = pts[pip]
            pts[dip] = (p[0] + 0.5 * (meet[0] - p[0]) + 0.05, p[1] + 0.5 * (meet[1] - p[1]) + 0.05)
            pts[tip] = meet
    return pts


def landmarks(fingers="11111", pinch=None, orientation="up", scale=60.0, center=(320, 240)):
    """Synthetic landmarks in image coordinates (y down), hand rotated for orientation."""
    out = []
    for p in model_points(fingers, pinch):
        r = rotate(p, ROTATION_DEG[orientation])
        out.append((center[0] + scale * r[0], center[1] - scale * r[1]))
    return out
