"""Observation only: never changes cursor coordinates or filter parameters."""
from pathlib import Path
import numpy as np
from .cursor_features import CursorFeatures, FEATURE_NAMES, LABELS, WINDOW_SECONDS

DEFAULT_MODEL = Path(__file__).parent / 'models' / 'cursor_state.joblib'


class CursorState:
    def __init__(self, model_path=DEFAULT_MODEL, threshold=0.7, persistence=0.08):
        self.features = CursorFeatures()
        self.model = None
        self.threshold = threshold
        self.persistence = persistence
        self.pending = None
        self.since = None
        self.state = 'UNCERTAIN'
        if model_path is not None and Path(model_path).exists():
            import joblib
            artifact = joblib.load(model_path)  # Only load trusted, locally trained artifacts.
            if (artifact.get('schema_version') != 1 or
                    tuple(artifact.get('features', ())) != FEATURE_NAMES or
                    artifact.get('window_seconds') != WINDOW_SECONDS):
                raise ValueError('Incompatible cursor model; retrain with this feature schema')
            self.model = artifact['model']
            if set(self.model.classes_) != set(LABELS):
                raise ValueError('Cursor model must contain all three movement states')

    def reset(self):
        self.features.reset()
        self.pending = self.since = None
        self.state = 'UNCERTAIN'

    def update(self, timestamp, x, y):
        if self.features.samples and timestamp - self.features.samples[-1][0] > 0.15:
            self.reset()
        values = self.features.update(timestamp, x, y)
        if self.model is None:
            return 'UNTRAINED', 0.0
        if values is None:
            self.pending = self.since = None
            self.state = 'UNCERTAIN'
            return self.state, 0.0
        probabilities = self.model.predict_proba([values])[0]
        index = int(np.argmax(probabilities))
        label, score = str(self.model.classes_[index]), float(probabilities[index])
        if score < self.threshold:
            self.pending = self.since = None
            self.state = 'UNCERTAIN'
            return self.state, score
        if label != self.pending:
            self.pending, self.since = label, timestamp
        if timestamp - self.since >= self.persistence:
            self.state = label
        else:
            self.state = 'UNCERTAIN'
        return self.state, score
