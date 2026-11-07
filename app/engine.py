"""Per-frame state machine: features -> matched mapping -> hold -> fire/hold/release."""

from cursor_stabilization import OneEuroFilter
from cursor_stabilization.cursor_state import CursorState
from cursor_stabilization.adaptive_smoothing import AdaptiveSmoothing

from .actions import ACTIONS, BUTTON, CONTINUOUS, ONESHOT, SCROLL_STEP, TOGGLE_ACTION, Backend
from .features import HandFeatures
from .profiles import Mapping, Profile

LOST_TIMEOUT = 0.3    # seconds without a hand before held buttons are released
DRAG_DEADZONE_PX = 40  # knuckle travel (screen px) while a button is held before a drag starts
HOVER_BREAK_PX = 32    # knuckle movement needed to leave a locked position
APPROACH_GAP = 0.65    # thumb-index gap (hand sizes) below which a pinch may be starting
APPROACH_DROP = 0.10   # gap must have shrunk by this much within APPROACH_WINDOW to count
APPROACH_WINDOW = 0.15 # seconds
CURL_SPEED = 3.5       # fingertip speed relative to the knuckle (hand sizes / s) that means "clicking"
REWIND_S = 0.15        # when a click starts, put the cursor back where it was this long ago
TRAIL_S = 0.5          # how much cursor history to keep for the rewind


class Engine:
    def __init__(self, backend: Backend, frame_size=(640, 480), margin=100, smooth=8):
        self.backend = backend
        self.frame_w, self.frame_h = frame_size
        self.margin = margin
        self.smooth = smooth
        self.screen_w, self.screen_h = backend.screen_size()
        self.cursor_state = CursorState()
        self.cursor_label, self.cursor_score = 'UNTRAINED', 0.0
        self.filter_x, self.filter_y = OneEuroFilter(), OneEuroFilter()
        # Off by default: One Euro tracks fast motion almost 1:1, which lets the start of a
        # finger curl drag the cursor off a target. The fixed low-pass below (1/smooth per
        # frame) is what the click stabilisation was tuned against. Toggle with 'a'.
        self.adaptive = AdaptiveSmoothing(self.filter_x, self.filter_y, enabled=False)

        self.profile: Profile | None = None
        self._ordered: list[Mapping] = []
        self.paused = False
        self.suspended = False          # True while the editor is recording a pose: nothing fires
        self.toggle_requested = False   # set when the toggle gesture fires; the worker acts on it

        self.candidate: Mapping | None = None
        self.active: Mapping | None = None
        self._candidate_since = 0.0
        self._button_down = False
        self._last_seen = 0.0
        # cursor stabilisation
        self._lock = None           # cursor held here while hovering or starting a pinch
        self._press_knuckle = None  # knuckle screen position when a button went down
        self._press_cursor = None
        self._drag_started = False
        self._gap_history = []      # recent (time, pinch_gap)
        self._trail = []            # recent (time, x, y) cursor positions, for the rewind
        self._last_tip = None       # (time, fingertip offset from knuckle) from the previous frame
        self._lock_knuckle = None   # knuckle screen position when the lock was taken
        self._prev_x = self.screen_w / 2
        self._prev_y = self.screen_h / 2

    # configuration
    def set_profile(self, profile: Profile):
        self.release()
        self.profile = profile
        self._ordered = profile.ordered_mappings()

    def refresh_profile(self):
        if self.profile:
            self.set_profile(self.profile)

    def set_paused(self, paused: bool):
        self.paused = paused
        if paused:
            self.release()

    def set_suspended(self, suspended: bool):
        self.suspended = suspended
        if suspended:
            self.release()

    # per frame
    def update(self, features: HandFeatures | None, now: float):
        if self.suspended:
            return
        if features is None:
            self._last_tip = None
            self.cursor_state.reset()
            self.cursor_label, self.cursor_score = 'NO HAND', 0.0
            self.adaptive.update('NO HAND', now)
            if self.candidate and now - self._last_seen > LOST_TIMEOUT:
                self.release()
            return
        self._last_seen = now

        candidates = self._ordered
        if self.paused:
            # Dictate can still be turned off while other gestures are ignored.
            listening = getattr(self.backend, "listening", False)
            candidates = [m for m in candidates if m.action == TOGGLE_ACTION or (
                listening and m.action == "speech_to_text")]
        match = next((m for m in candidates if m.gesture.matches(features)), None)

        if match is not self.candidate:
            self.release()
            self.candidate = match
            self._candidate_since = now
        if match is None:
            self.cursor_label, self.cursor_score = 'INACTIVE', 0.0
            self.adaptive.update('INACTIVE', now)
            return

        if self.active is None and (now - self._candidate_since) * 1000 >= match.hold_ms:
            self._activate(match)
        if self.active is not None:
            self._run(self.active, features)

    def release(self):
        self.cursor_state.reset()
        self.cursor_label, self.cursor_score = 'INACTIVE', 0.0
        if self._button_down:
            self.backend.mouse_up()
            self._button_down = False
        self._press_knuckle = None
        self._drag_started = False
        self.active = None
        self.candidate = None

    # internals
    def _activate(self, m: Mapping):
        self.active = m
        action = ACTIONS[m.action]
        if action.kind == ONESHOT:
            self._fire(m.action)
        elif action.kind == BUTTON:
            self.backend.mouse_down()
            self._button_down = True
            self._press_knuckle = None
            self._drag_started = False

    def _fire(self, action_id: str):
        b = self.backend
        if action_id == "left_click":
            b.click("left")
        elif action_id == "right_click":
            b.click("right")
        elif action_id == "double_click":
            b.double_click()
        elif action_id == "speech_to_text":
            b.dictate()
        elif action_id == TOGGLE_ACTION:
            self.toggle_requested = True

    def _run(self, m: Mapping, f: HandFeatures):
        action = ACTIONS[m.action]
        if action.moves_cursor:
            # Use the same raw index-tip mapping as the training recorder.
            tx, ty = self._to_screen(tuple(int(v) for v in f.pointer))
            self.cursor_label, self.cursor_score = self.cursor_state.update(
                self._last_seen, 1.0 - tx / self.screen_w, ty / self.screen_h)
            self.adaptive.update(self.cursor_label, self._last_seen)
            if self._button_down:
                self._drag_cursor(f)
            else:
                self._point_cursor(f, self._last_seen)
        if not action.moves_cursor:
            self.cursor_state.reset()
            self.cursor_label, self.cursor_score = 'INACTIVE', 0.0
            self.adaptive.update('INACTIVE', self._last_seen)
        if action.kind == CONTINUOUS:
            if m.action == "scroll_up":
                self.backend.scroll(SCROLL_STEP)
            elif m.action == "scroll_down":
                self.backend.scroll(-SCROLL_STEP)

    def _to_screen(self, point):
        px, py = point
        tx = _interp(px, self.margin, self.frame_w - self.margin, 0, self.screen_w)
        ty = _interp(py, self.margin, self.frame_h - self.margin, 0, self.screen_h)
        return tx, ty

    def _clicking(self, f: HandFeatures, now: float) -> bool:
        """Is a click starting? The index curls (fingertip moves fast relative to the
        knuckle) or the thumb and index close on each other quickly."""
        kx, ky = f.knuckle
        offset = (f.pointer[0] - kx, f.pointer[1] - ky)
        curling = False
        if self._last_tip is not None:
            t0, prev = self._last_tip
            dt = max(now - t0, 1e-3)
            curling = _dist(offset, prev) / dt / max(f.hand_size, 1.0) >= CURL_SPEED
        self._last_tip = (now, offset)

        self._gap_history.append((now, f.pinch_gap))
        self._gap_history = [(t, g) for t, g in self._gap_history if now - t <= APPROACH_WINDOW]
        closing = (f.pinch_gap < APPROACH_GAP
                   and max(g for _, g in self._gap_history) - f.pinch_gap >= APPROACH_DROP)
        return curling or closing

    def _take_lock(self, f: HandFeatures):
        self._lock = (self._prev_x, self._prev_y)
        self._lock_knuckle = self._to_screen(f.knuckle)

    def _point_cursor(self, f: HandFeatures, now: float):
        target = self._to_screen(f.pointer)

        # A click starting: freeze, and undo the little the curl already moved the cursor.
        if self._clicking(f, now):
            if self._lock is None:
                self._rewind(now - REWIND_S)
                self._take_lock(f)
            return

        # While locked, only the hand itself moving (the knuckle) releases the lock.
        # The fingertip is ignored here because a curl moves it without the hand moving.
        if self._lock is not None:
            if _dist(self._to_screen(f.knuckle), self._lock_knuckle) < HOVER_BREAK_PX:
                return
            self._lock = None

        self._glide_to(target)

    def _drag_cursor(self, f: HandFeatures):
        """While a button is held, move by how far the knuckle travelled since the press."""
        k = self._to_screen(f.knuckle)
        if self._press_knuckle is None:
            self._press_knuckle = k
            self._press_cursor = (self._prev_x, self._prev_y)
            return
        dx, dy = k[0] - self._press_knuckle[0], k[1] - self._press_knuckle[1]
        if not self._drag_started:
            if (dx * dx + dy * dy) ** 0.5 < DRAG_DEADZONE_PX:
                return
            self._drag_started = True
        self._lock = None
        self._glide_to((self._press_cursor[0] + dx, self._press_cursor[1] + dy))

    def _glide_to(self, target):
        tx, ty = target
        if self.adaptive.enabled:
            x = self.filter_x.update(tx, self._last_seen)
            y = self.filter_y.update(ty, self._last_seen)
        else:
            x = self._prev_x + (tx - self._prev_x) / self.smooth
            y = self._prev_y + (ty - self._prev_y) / self.smooth
            self.filter_x.update(x, self._last_seen)   # keep in step for a smooth switch-over
            self.filter_y.update(y, self._last_seen)
        self._emit(x, y)
        self._trail.append((self._last_seen, x, y))
        self._trail = [t for t in self._trail if self._last_seen - t[0] <= TRAIL_S]

    def _rewind(self, when: float):
        """Move the cursor back to where it was at time `when` (or the oldest known)."""
        if not self._trail:
            return
        older = [t for t in self._trail if t[0] <= when]
        _, x, y = older[-1] if older else self._trail[0]
        self._emit(x, y)
        self._trail = []

    def _emit(self, x, y):
        self._prev_x, self._prev_y = x, y
        # camera is mirrored relative to the user, so flip x
        sx = min(max(self.screen_w - x, 0), self.screen_w - 1)
        sy = min(max(y, 0), self.screen_h - 1)
        self.backend.move_to(sx, sy)


def _dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def _interp(v, lo, hi, out_lo, out_hi):
    if v <= lo:
        return out_lo
    if v >= hi:
        return out_hi
    return out_lo + (v - lo) / (hi - lo) * (out_hi - out_lo)
