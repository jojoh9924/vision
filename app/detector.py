"""Webcam frame -> 21 hand landmarks via the mediapipe Tasks HandLandmarker."""

import urllib.request
from pathlib import Path

import cv2
import mediapipe as mp

from .handmodel import BONES

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/latest/hand_landmarker.task")
MODEL_PATH = Path(__file__).resolve().parent.parent / "assets" / "hand_landmarker.task"

FINGERTIPS = (4, 8, 12, 16, 20)


def ensure_model(path: Path = MODEL_PATH, log=print) -> Path:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        log(f"Downloading hand landmark model to {path} ...")
        urllib.request.urlretrieve(MODEL_URL, path)
        log("Done.")
    return path


class HandDetector:
    def __init__(self, model_path: Path = MODEL_PATH, max_hands=1, confidence=0.5):
        vision = mp.tasks.vision
        options = vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=max_hands,
            min_hand_detection_confidence=confidence,
            min_hand_presence_confidence=confidence,
            min_tracking_confidence=confidence,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        self._last_ts = -1

    def detect(self, frame_bgr, timestamp_ms: int):
        """Returns a list of 21 (x, y) pixel tuples for the first hand, or None."""
        if timestamp_ms <= self._last_ts:
            timestamp_ms = self._last_ts + 1
        self._last_ts = timestamp_ms
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect_for_video(image, timestamp_ms)
        if not result.hand_landmarks:
            return None
        h, w = frame_bgr.shape[:2]
        return [(lm.x * w, lm.y * h) for lm in result.hand_landmarks[0]]

    def close(self):
        self._landmarker.close()


def draw_hand(frame, landmarks, color=(0, 255, 0)):
    pts = [(int(x), int(y)) for x, y in landmarks]
    for a, b in BONES:
        cv2.line(frame, pts[a], pts[b], (255, 255, 255), 2)
    for i, p in enumerate(pts):
        cv2.circle(frame, p, 6 if i in FINGERTIPS else 3, color, cv2.FILLED)
