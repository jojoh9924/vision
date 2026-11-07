"""Gesture definitions, matching against HandFeatures, and human descriptions."""

from dataclasses import dataclass

from .features import FINGER_NAMES, HandFeatures

ORIENTATIONS = ("any", "up", "down", "left", "right")
PINCHES = (None, "index", "middle", "ring", "pinky", "all")
# A gesture that needs a direction only starts within 40 degrees of it, so a hand near a
# diagonal can't start, say, scrolling when Backspace was meant. Once it is the current
# gesture it keeps matching anywhere in its 45-degree sector (margin 0), so ordinary
# hand wobble doesn't restart its hold timer.
ORIENTATION_MARGIN = 5.0


@dataclass(frozen=True)
class Gesture:
    fingers: str = "*****"      # thumb,index,middle,ring,pinky; each '1' | '0' | '*'
    pinch: str | None = None
    orientation: str = "any"

    def __post_init__(self):
        if len(self.fingers) != 5 or any(c not in "01*" for c in self.fingers):
            raise ValueError(f"bad fingers pattern {self.fingers!r}")
        if self.pinch not in PINCHES:
            raise ValueError(f"bad pinch {self.pinch!r}")
        if self.orientation not in ORIENTATIONS:
            raise ValueError(f"bad orientation {self.orientation!r}")

    def matches(self, f: HandFeatures, margin: float = ORIENTATION_MARGIN) -> bool:
        if f.pinch != self.pinch:
            return False
        for want, have in zip(self.fingers, f.fingers):
            if want == "*":
                continue
            if (want == "1") != bool(have):
                return False
        if self.orientation == "any":
            return True
        return self.orientation == f.orientation and f.orientation_margin >= margin

    def specificity(self) -> tuple:
        wildcards = self.fingers.count("*")
        return (self.pinch is not None, 5 - wildcards, self.orientation != "any")

    def describe(self) -> str:
        parts = []
        if self.pinch == "all":
            parts.append("All fingertips together")
        elif self.pinch:
            parts.append(f"Pinch thumb + {self.pinch}")
            extra = [n for n, c in zip(FINGER_NAMES, self.fingers) if c == "1" and n not in ("thumb", self.pinch)]
            if extra:
                parts[-1] += ", " + " + ".join(extra) + " up"
        else:
            up = [n for n, c in zip(FINGER_NAMES, self.fingers) if c == "1"]
            down = [n for n, c in zip(FINGER_NAMES, self.fingers) if c == "0"]
            if self.fingers == "11111":
                parts.append("Open hand")
            elif self.fingers == "00000":
                parts.append("Fist")
            elif self.fingers == "*****":
                parts.append("Any hand")
            elif up and len(down) == 5 - len(up):
                parts.append(" + ".join(up).capitalize() + (" only" if len(up) == 1 else ""))
            elif up and self.fingers[0] == "*" and "*" not in self.fingers[1:]:
                parts.append(" + ".join(up).capitalize() + " (any thumb)")
            elif up:
                parts.append(" + ".join(up).capitalize() + " up")
            else:
                parts.append(" + ".join(down).capitalize() + " down")
        if self.orientation != "any":
            # Orientation is measured on the raw (unmirrored) camera image; describe it
            # from the user's point of view, matching the mirrored preview.
            seen = {"left": "right", "right": "left"}.get(self.orientation, self.orientation)
            parts.append(f"pointing {seen}")
        return ", ".join(parts)

    def to_dict(self) -> dict:
        return {"fingers": self.fingers, "pinch": self.pinch, "orientation": self.orientation}

    @classmethod
    def from_dict(cls, d: dict) -> "Gesture":
        return cls(d.get("fingers", "*****"), d.get("pinch"), d.get("orientation", "any"))


# Named presets offered in the editor's picker.
PRESET_GESTURES: list[tuple[str, Gesture]] = [
    ("Index up (any thumb)", Gesture("*1000")),
    ("Index + middle (any thumb)", Gesture("*1100")),
    ("Index + middle, pointing up (any thumb)", Gesture("*1100", None, "up")),
    ("Index + middle, pointing down (any thumb)", Gesture("*1100", None, "down")),
    ("Index only", Gesture("01000")),
    ("Thumb only", Gesture("10000")),
    ("Pinky only", Gesture("00001")),
    ("Middle only", Gesture("00100")),
    ("Index + middle", Gesture("01100")),
    ("Index + middle, pointing up", Gesture("01100", None, "up")),
    ("Index + middle, pointing down", Gesture("01100", None, "down")),
    ("Index + pinky", Gesture("01001")),
    ("Thumb + index", Gesture("11000")),
    ("Thumb + pinky", Gesture("10001")),
    ("Thumb + index + middle", Gesture("11100")),
    ("Index + middle + ring", Gesture("01110")),
    ("Four fingers (no thumb)", Gesture("01111")),
    ("Open hand", Gesture("11111")),
    ("Fist", Gesture("00000")),
    ("Pinch thumb + index", Gesture("*****", "index")),
    ("Pinch thumb + middle", Gesture("*****", "middle")),
    ("Pinch thumb + ring", Gesture("*****", "ring")),
    ("Pinch thumb + pinky", Gesture("*****", "pinky")),
    ("All fingertips together", Gesture("*****", "all")),
]
