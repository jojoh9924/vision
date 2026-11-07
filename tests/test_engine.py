from app import features
from app.actions import Backend
from app.defaults import BUNDLED
from app.engine import Engine
from app.gestures import Gesture
from app.handmodel import landmarks
from app.profiles import Mapping, Profile


class FakeBackend(Backend):
    def __init__(self):
        self.events = []
        self.pos = None

    def screen_size(self):
        return (1920, 1080)

    def move_to(self, x, y):
        self.pos = (x, y)

    def mouse_down(self):
        self.events.append("down")

    def mouse_up(self):
        self.events.append("up")

    def click(self, button="left"):
        self.events.append(f"click:{button}")

    def double_click(self):
        self.events.append("dblclick")

    def scroll(self, amount):
        self.events.append(f"scroll:{amount}")

    def dictate(self):
        self.events.append("dictate")


def feat(pattern, pinch=None, orientation="up", center=(320, 240)):
    return features.extract(landmarks(pattern, pinch=pinch, orientation=orientation, center=center))


def make_engine(profile=None):
    b = FakeBackend()
    e = Engine(b, frame_size=(640, 480), margin=100, smooth=1)
    e.set_profile(profile or next(p for p in BUNDLED() if p.id == "default"))
    return e, b


def test_oneshot_fires_once_after_hold():
    e, b = make_engine()
    f = feat("11111", pinch="middle")  # right click, hold 120 ms
    e.update(f, 0.0)
    assert b.events == [] and e.candidate is not None and e.active is None
    e.update(f, 0.05)
    assert b.events == []
    e.update(f, 0.13)
    assert b.events == ["click:right"]
    e.update(f, 0.5)
    e.update(f, 1.0)
    assert b.events == ["click:right"]
    # release and re-pinch fires again
    e.update(feat("01000"), 1.1)
    e.update(f, 1.2)
    e.update(f, 1.4)
    assert b.events == ["click:right", "click:right"]


def test_button_down_up_and_release_on_hand_loss():
    e, b = make_engine()
    f = feat("11111", pinch="index")  # left_button, hold 0
    e.update(f, 0.0)
    assert b.events == ["down"]
    e.update(f, 0.1)
    assert b.events == ["down"]
    e.update(None, 0.2)
    assert b.events == ["down"]          # within LOST_TIMEOUT
    e.update(None, 0.6)
    assert b.events == ["down", "up"]


def test_button_released_on_gesture_change():
    e, b = make_engine()
    e.update(feat("11111", pinch="index"), 0.0)
    e.update(feat("01000"), 0.1)
    assert b.events == ["down", "up"]


def test_move_tracks_pointer_and_mirrors_x():
    e, b = make_engine()
    e.update(feat("01000", center=(150, 240)), 0.0)
    left = b.pos
    e.update(feat("01000", center=(500, 240)), 0.1)
    right = b.pos
    assert left[0] > right[0]  # hand on the camera's left = user's right
    assert 0 <= left[0] < 1920 and 0 <= left[1] < 1080


def test_scroll_runs_every_frame_and_respects_orientation():
    e, b = make_engine()
    f = feat("01100", orientation="down")
    e.update(f, 0.0)
    e.update(f, 0.2)
    e.update(f, 0.3)
    assert b.events == ["scroll:-60", "scroll:-60"]
    e.update(feat("01100", orientation="up"), 0.4)
    e.update(feat("01100", orientation="up"), 0.6)
    assert b.events[-1] == "scroll:60"


def test_pause_releases_and_blocks():
    e, b = make_engine()
    e.update(feat("11111", pinch="index"), 0.0)
    e.set_paused(True)
    assert b.events == ["down", "up"]
    e.update(feat("11111", pinch="index"), 0.5)
    assert b.events == ["down", "up"]


def test_most_specific_mapping_wins():
    p = Profile("t", "t", [
        Mapping("scroll_up", Gesture("*****"), 0),
        Mapping("left_click", Gesture("01000"), 0),
    ])
    e, b = make_engine(p)
    e.update(feat("01000"), 0.0)
    assert b.events == ["click:left"]


def test_pinch_start_freezes_cursor_and_drag_needs_real_motion():
    import dataclasses
    e, b = make_engine()
    for i, t in enumerate([0.0, 0.03, 0.06]):
        e.update(feat("01000", center=(200 + i * 40, 240)), t)
    before = b.pos
    # thumb and index closing fast: gap shrinks, the moving fingertip must not drag the cursor
    closing = dataclasses.replace(feat("01000", center=(330, 240)), pinch_gap=0.4)
    e.update(closing, 0.09)
    assert b.pos == before
    # pinch lands: button down at the frozen position, small wobble ignored
    e.update(feat("11111", pinch="index", center=(330, 240)), 0.12)
    e.update(feat("11111", pinch="index", center=(334, 242)), 0.15)
    assert b.events == ["down"] and b.pos == before
    # moving the whole hand drags
    e.update(feat("11111", pinch="index", center=(450, 240)), 0.2)
    assert b.pos != before
    e.update(feat("01000", center=(450, 240)), 0.3)
    assert b.events == ["down", "up"]


def test_hover_lock_ignores_small_drift_until_clear_move():
    e, b = make_engine()
    e.update(feat("01000", center=(300, 240)), 0.0)
    e.update(feat("01000", center=(301, 240)), 0.1)
    e.update(feat("01000", center=(302, 241)), 0.3)   # still for 300 ms: locks
    locked = b.pos
    e.update(feat("01000", center=(305, 243)), 0.4)
    assert b.pos == locked
    e.update(feat("01000", center=(380, 240)), 0.5)   # clear move: follows again
    assert b.pos != locked


def test_toggle_gesture_fires_even_while_paused_and_only_that():
    e, b = make_engine()
    e.set_paused(True)
    # a normal gesture does nothing while paused
    e.update(feat("11111", pinch="index"), 0.0)
    e.update(feat("11111", pinch="index"), 0.5)
    assert b.events == [] and not e.toggle_requested
    # the toggle gesture (thumb + pinky, 1.5 s) still works
    e.update(feat("10001"), 1.0)
    e.update(feat("10001"), 2.0)
    assert not e.toggle_requested
    e.update(feat("10001"), 2.6)
    assert e.toggle_requested
    e.toggle_requested = False
    e.update(feat("10001"), 5.0)      # latched: no repeat while held
    assert not e.toggle_requested


def test_suspended_engine_does_nothing_and_releases_buttons():
    e, b = make_engine()
    e.update(feat("11111", pinch="index"), 0.0)
    e.set_suspended(True)
    assert b.events == ["down", "up"]
    e.update(feat("11111", pinch="index"), 0.5)
    e.update(feat("10001"), 1.0)
    e.update(feat("10001"), 3.0)
    assert b.events == ["down", "up"] and not e.toggle_requested
    e.set_suspended(False)
    e.update(feat("11111", pinch="index"), 3.5)
    assert b.events == ["down", "up", "down"]
