"""Action registry and the pyautogui / speech backend that performs them."""

import threading
import time
from dataclasses import dataclass

CONTINUOUS, ONESHOT, BUTTON = "continuous", "oneshot", "button"

SCROLL_STEP = 60
SCROLL_INTERVAL = 0.1      # seconds between scroll steps while held
TYPE_INTERVAL = 0.01       # seconds between keystrokes when typing dictated text
SPEECH_TIMEOUT = 5         # seconds to wait for speech to start
SPEECH_PHRASE_LIMIT = 10   # max seconds of speech captured


@dataclass(frozen=True)
class Action:
    id: str
    label: str
    kind: str
    moves_cursor: bool = False
    default_hold_ms: int = 120
    hint: str = ""


ACTIONS: dict[str, Action] = {a.id: a for a in [
    Action("move", "Move pointer", CONTINUOUS, moves_cursor=True, default_hold_ms=0),
    Action("left_button", "Left button", BUTTON, moves_cursor=True, default_hold_ms=0,
           hint="tap = click, hold = drag, two taps = double click"),
    Action("left_click", "Left click", ONESHOT),
    Action("right_click", "Right click", ONESHOT),
    Action("double_click", "Double click", ONESHOT),
    Action("drag", "Drag", BUTTON, moves_cursor=True, hint="holds the left button while moving"),
    Action("scroll_up", "Scroll up", CONTINUOUS),
    Action("scroll_down", "Scroll down", CONTINUOUS),
    Action("speech_to_text", "Dictate", ONESHOT, default_hold_ms=1000, hint="speak, text is typed"),
]}


class Backend:
    """Interface the engine drives. Replace in tests."""

    def move_to(self, x: float, y: float): ...
    def mouse_down(self): ...
    def mouse_up(self): ...
    def click(self, button: str = "left"): ...
    def double_click(self): ...
    def scroll(self, amount: int): ...
    def dictate(self): ...
    def screen_size(self) -> tuple[int, int]: return (1920, 1080)


class PyAutoGuiBackend(Backend):
    def __init__(self):
        import pyautogui
        pyautogui.PAUSE = 0
        pyautogui.FAILSAFE = False
        self._gui = pyautogui
        self._last_scroll = 0.0
        self._listening = False
        self.speech_available = False
        self.speech_error = ""
        try:
            import speech_recognition as sr
            self._sr = sr
            self._recognizer = sr.Recognizer()
            self._mic = sr.Microphone()
            self.speech_available = True
        except Exception as e:  # missing PyAudio, no microphone, etc.
            self.speech_error = str(e)

    def screen_size(self):
        return self._gui.size()

    def move_to(self, x, y):
        self._gui.moveTo(x, y)

    def mouse_down(self):
        self._gui.mouseDown()

    def mouse_up(self):
        self._gui.mouseUp()

    def click(self, button="left"):
        self._gui.click(button=button)

    def double_click(self):
        self._gui.doubleClick()

    def scroll(self, amount):
        now = time.monotonic()
        if now - self._last_scroll >= SCROLL_INTERVAL:
            self._gui.scroll(amount)
            self._last_scroll = now

    def dictate(self):
        if not self.speech_available or self._listening:
            return
        self._listening = True
        threading.Thread(target=self._dictate_worker, daemon=True).start()

    def _dictate_worker(self):
        sr = self._sr
        try:
            with self._mic as source:
                self._recognizer.adjust_for_ambient_noise(source)
                audio = self._recognizer.listen(source, timeout=SPEECH_TIMEOUT,
                                                phrase_time_limit=SPEECH_PHRASE_LIMIT)
            text = self._recognizer.recognize_google(audio)
            if text:
                self._gui.write(text, interval=TYPE_INTERVAL)
        except (sr.UnknownValueError, sr.RequestError, sr.WaitTimeoutError):
            pass
        finally:
            self._listening = False
