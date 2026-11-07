"""Renders a hand diagram for any Gesture, or loads a recorded snapshot for a mapping."""

from pathlib import Path

from PIL import Image, ImageDraw

from .gestures import Gesture
from .handmodel import BONES, FINGER_JOINTS, FINGER_ORDER, ROTATION_DEG, model_points, rotate
from .profiles import ROOT

EXTENDED = (46, 160, 67)      # green
CURLED = (120, 120, 120)
WILDCARD = (190, 190, 190)
PINCH = (235, 140, 20)        # orange
PALM = (90, 90, 90)
JOINT = (40, 40, 40)

_cache: dict[tuple, Image.Image] = {}


def render(gesture: Gesture, size: int = 96) -> Image.Image:
    key = (gesture, size)
    if key in _cache:
        return _cache[key]

    pts = [rotate(p, ROTATION_DEG[gesture.orientation]) for p in model_points(gesture.fingers, gesture.pinch)]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 1e-6)
    scale = size * 0.8 / span
    cx = (max(xs) + min(xs)) / 2
    cy = (max(ys) + min(ys)) / 2
    px = [(size / 2 + (x - cx) * scale, size / 2 - (y - cy) * scale) for x, y in pts]

    s = 4  # supersample for smoother lines
    img = Image.new("RGBA", (size * s, size * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    P = [(x * s, y * s) for x, y in px]

    finger_of = {}
    for name, joints in FINGER_JOINTS.items():
        for j in joints:
            finger_of[j] = name
    colors = {}
    for name, ch in zip(FINGER_ORDER, gesture.fingers):
        colors[name] = EXTENDED if ch == "1" else CURLED if ch == "0" else WILDCARD
    if gesture.pinch == "all":
        colors = {name: PINCH for name in colors}
    elif gesture.pinch:
        colors["thumb"] = PINCH
        colors[gesture.pinch] = PINCH

    width = max(2, size // 16) * s
    for a, b in BONES:
        fa, fb = finger_of.get(a), finger_of.get(b)
        if fa and fb and fa == fb:
            color = colors[fa]
        else:
            color = PALM
        d.line([P[a], P[b]], fill=color, width=width)
    r = max(1.5, size / 28) * s
    for i, (x, y) in enumerate(P):
        d.ellipse([x - r, y - r, x + r, y + r], fill=JOINT)
    if gesture.pinch:
        x, y = P[4]
        rr = size / 7 * s
        d.ellipse([x - rr, y - rr, x + rr, y + rr], outline=PINCH, width=width)
    if gesture.orientation in ("up", "down", "left", "right"):
        _arrow(d, size * s, gesture.orientation, width)

    out = img.resize((size, size), Image.LANCZOS)
    _cache[key] = out
    return out


def _arrow(d, S, orientation, width):
    m = S * 0.1
    tip = {"up": (S - m, m), "down": (S - m, S - m), "left": (m, m), "right": (S - m, m)}[orientation]
    L = S * 0.14
    if orientation == "up":
        tail = (tip[0], tip[1] + L)
        heads = [(tip[0] - L * 0.4, tip[1] + L * 0.4), (tip[0] + L * 0.4, tip[1] + L * 0.4)]
    elif orientation == "down":
        tail = (tip[0], tip[1] - L)
        heads = [(tip[0] - L * 0.4, tip[1] - L * 0.4), (tip[0] + L * 0.4, tip[1] - L * 0.4)]
    elif orientation == "left":
        tail = (tip[0] + L, tip[1])
        heads = [(tip[0] + L * 0.4, tip[1] - L * 0.4), (tip[0] + L * 0.4, tip[1] + L * 0.4)]
    else:
        tail = (tip[0] - L, tip[1])
        heads = [(tip[0] - L * 0.4, tip[1] - L * 0.4), (tip[0] - L * 0.4, tip[1] + L * 0.4)]
    d.line([tail, tip], fill=(30, 100, 220), width=width)
    for h in heads:
        d.line([tip, h], fill=(30, 100, 220), width=width)


def icon_for(mapping, size: int = 96) -> Image.Image:
    """Recorded snapshot if the mapping has one, otherwise a rendered diagram."""
    if mapping.image:
        path = ROOT / mapping.image
        if path.exists():
            try:
                img = Image.open(path).convert("RGBA")
                return _square(img, size)
            except OSError:
                pass
    return render(mapping.gesture, size)


def _square(img: Image.Image, size: int) -> Image.Image:
    w, h = img.size
    side = min(w, h)
    left, top = (w - side) // 2, (h - side) // 2
    return img.crop((left, top, left + side, top + side)).resize((size, size), Image.LANCZOS)


def save_snapshot(frame_bgr, bbox, dest: Path, margin_ratio=0.35) -> None:
    """Crop the hand region of a BGR frame and save it as a PNG."""
    import cv2
    x0, y0, x1, y1 = bbox
    side = max(x1 - x0, y1 - y0) * (1 + margin_ratio)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    h, w = frame_bgr.shape[:2]
    l = int(max(0, cx - side / 2))
    t = int(max(0, cy - side / 2))
    r = int(min(w, cx + side / 2))
    b = int(min(h, cy + side / 2))
    crop = frame_bgr[t:b, l:r]
    if crop.size == 0:
        return
    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    dest.parent.mkdir(parents=True, exist_ok=True)
    _square(Image.fromarray(rgb), 160).save(dest)


def tray_image(size: int = 64) -> Image.Image:
    bg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(bg)
    d.ellipse([0, 0, size - 1, size - 1], fill=(30, 100, 220))
    hand = render(Gesture("11111"), int(size * 0.8))
    # recolor to white for contrast
    white = Image.new("RGBA", hand.size, (255, 255, 255, 0))
    white.putalpha(hand.getchannel("A"))
    off = (size - hand.size[0]) // 2
    bg.alpha_composite(white, (off, off))
    return bg
