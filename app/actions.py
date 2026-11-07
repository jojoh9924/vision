"""Action registry and the pyautogui / speech backend that performs them."""

import sys
import threading
import time
from dataclasses import dataclass

CONTINUOUS, ONESHOT, BUTTON = "continuous", "oneshot", "button"

SCROLL_STEP = 60
SCROLL_INTERVAL = 0.1      # seconds between scroll steps while held
TYPE_INTERVAL = 0.01       # seconds between keystrokes when typing dictated text
WHISPER_MODEL = "base"     # local faster-whisper model; downloaded on first dictate
LIVE_RATE = 16000
LIVE_CHUNK_SECONDS = 1.2   # transcribe about this often so words appear while you speak
LIVE_SPEECH_RMS = 0.006    # above this mic's room noise (~0.0045), low enough for quiet speech


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
    Action("speech_to_text", "Dictate", ONESHOT, default_hold_ms=1000,
           hint="stays on while you speak; hold this gesture again to stop"),
    Action("toggle_gestures", "Pause / resume gestures", ONESHOT, default_hold_ms=1500,
           hint="works while paused too"),
]}

TOGGLE_ACTION = "toggle_gestures"


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
        self._stop_listening = threading.Event()
        self._whisper_model = None
        self.speech_available = False
        self.speech_error = ""
        try:
            import speech_recognition as sr
            from faster_whisper import WhisperModel
            self._sr = sr
            self._WhisperModel = WhisperModel
            self._recognizer = sr.Recognizer()
            self._mic = sr.Microphone()
            self.speech_available = True
        except Exception as e:  # missing PyAudio, no microphone, or no Whisper
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

    @property
    def listening(self):
        return self._listening

    def dictate(self):
        """Start dictation, or stop it if it is already running."""
        if not self.speech_available:
            return
        if self._listening:
            print("Dictate off.", file=sys.stderr)
            self.stop_dictate()
            return
        self._stop_listening.clear()
        self._listening = True
        threading.Thread(target=self._dictate_worker, daemon=True).start()

    def stop_dictate(self):
        self._stop_listening.set()

    def _whisper(self):
        if self._whisper_model is None:
            print(f"Loading Whisper ({WHISPER_MODEL}).", file=sys.stderr)
            self._whisper_model = self._WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        return self._whisper_model

    def _transcribe_samples(self, samples, prompt):
        segments, _info = self._whisper().transcribe(
            samples,
            beam_size=1,
            language="en",
            vad_filter=True,
            condition_on_previous_text=False,
            initial_prompt=prompt or None,
            without_timestamps=True,
        )
        return "".join(segment.text for segment in segments).strip()

    def _dictate_worker(self):
        import numpy as np
        rate = LIVE_RATE
        mic = self._sr.Microphone(sample_rate=rate, chunk_size=int(rate * 0.1))
        blocks = []
        lock = threading.Lock()
        stop_read = threading.Event()

        def read_mic():
            try:
                with mic as source:
                    while not stop_read.is_set():
                        raw = source.stream.read(source.CHUNK)
                        block = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
                        with lock:
                            blocks.append(block)
            except Exception as e:
                print(f"Dictate failed: {e}", file=sys.stderr)
                stop_read.set()

        def snapshot():
            with lock:
                if not blocks:
                    return np.empty(0, dtype=np.float32)
                return np.concatenate(blocks)

        def consume(end, keep):
            """Drop audio before `end`, leaving `keep` samples of overlap. New mic
            samples appended during transcription stay in the buffer."""
            with lock:
                if not blocks:
                    return 0
                audio = np.concatenate(blocks)
                end = min(end, audio.size)
                drop = max(0, end - keep)
                rest = audio[drop:]
                blocks.clear()
                if rest.size:
                    blocks.append(rest)
                return end - drop

        try:
            self._whisper()
            print("Listening. Hold the dictate gesture again to stop.", file=sys.stderr)
            reader = threading.Thread(target=read_mic, daemon=True)
            reader.start()
            typed = ""
            processed = 0
            overlap = int(0.25 * rate)
            while not stop_read.is_set() and not self._stop_listening.is_set():
                time.sleep(0.12)
                audio = snapshot()
                pending = audio.size - processed
                if pending < int(LIVE_CHUNK_SECONDS * rate):
                    continue
                fresh = audio[processed:]
                if float(np.sqrt(np.mean(fresh ** 2))) < LIVE_SPEECH_RMS:
                    processed = consume(audio.size, 0)
                    continue
                piece = self._transcribe_samples(audio[max(0, processed - overlap):], typed[-160:])
                addition = _new_dictation(typed, piece)
                if addition:
                    self._gui.write(addition, interval=0)
                    typed += addition
                processed = consume(audio.size, overlap)
            audio = snapshot()
            tail = audio[processed:]
            if tail.size >= int(0.3 * rate) and float(np.sqrt(np.mean(tail ** 2))) >= LIVE_SPEECH_RMS:
                piece = self._transcribe_samples(audio[max(0, processed - overlap):], typed[-160:])
                addition = _new_dictation(typed, piece)
                if addition:
                    self._gui.write(addition, interval=0)
        except Exception as e:
            print(f"Dictate failed: {e}", file=sys.stderr)
        finally:
            stop_read.set()
            self._listening = False


def _new_dictation(already, piece):
    """Text from this chunk that has not been typed yet."""
    piece = " ".join(piece.split())
    if not piece:
        return ""
    prev = already.strip()
    if prev:
        low_piece = piece.lower()
        low_prev = prev.lower()
        if low_piece.startswith(low_prev):
            piece = piece[len(prev):].strip()
        else:
            # The chunk overlaps the previous audio, so drop a repeated ending.
            cut = 0
            limit = min(len(low_prev), len(low_piece), 40)
            for n in range(limit, 0, -1):
                if low_piece.startswith(low_prev[-n:]):
                    cut = n
                    break
            piece = piece[cut:].strip()
    if not piece:
        return ""
    if already and not already.endswith((" ", "\n")) and piece[0] not in ",.!?;:'":
        return " " + piece
    return piece
