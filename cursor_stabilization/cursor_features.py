"""Causal features shared by recording, training, and live inference."""
from collections import deque
import numpy as np

LABELS = ('STATIONARY', 'PRECISION', 'MOVING')
FEATURE_NAMES = ('speed', 'mean_speed', 'peak_speed', 'speed_std',
                 'mean_acceleration', 'spread', 'path_length', 'straightness',
                 'mean_turn')
WINDOW_SECONDS = 0.2
MAX_GAP_SECONDS = 0.15


class CursorFeatures:
    def __init__(self):
        self.samples = deque()

    def reset(self):
        self.samples.clear()

    def update(self, timestamp, x, y):
        if not np.isfinite([timestamp, x, y]).all():
            self.reset()
            return None
        if self.samples:
            dt = timestamp - self.samples[-1][0]
            if dt <= 0 or dt > MAX_GAP_SECONDS:
                self.reset()
        self.samples.append((timestamp, x, y))
        while len(self.samples) > 2 and self.samples[1][0] <= timestamp - WINDOW_SECONDS:
            self.samples.popleft()
        if len(self.samples) < 4 or timestamp - self.samples[0][0] < WINDOW_SECONDS - 1e-9:
            return None
        data = np.asarray(self.samples)
        dt = np.diff(data[:, 0])
        steps = np.diff(data[:, 1:], axis=0)
        distances = np.linalg.norm(steps, axis=1)
        velocity = steps / dt[:, None]
        speed = np.linalg.norm(velocity, axis=1)
        acceleration = np.linalg.norm(np.diff(velocity, axis=0), axis=1) / ((dt[1:] + dt[:-1]) / 2)
        path = distances.sum()
        displacement = np.linalg.norm(data[-1, 1:] - data[0, 1:])
        denom = distances[1:] * distances[:-1]
        valid = denom > 1e-12
        cosines = np.sum(steps[1:] * steps[:-1], axis=1)[valid] / denom[valid]
        turns = np.arccos(np.clip(cosines, -1, 1))
        return np.array([speed[-1], speed.mean(), speed.max(), speed.std(),
                         acceleration.mean(), np.linalg.norm(data[:, 1:].std(axis=0)),
                         path, displacement / path if path > 1e-12 else 0,
                         turns.mean() if len(turns) else 0])
