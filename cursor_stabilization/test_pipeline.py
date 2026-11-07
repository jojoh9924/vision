import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np
from .cursor_features import CursorFeatures, LABELS
from .cursor_state import CursorState
from .train_cursor_classifier import load_sessions


class PipelineTests(unittest.TestCase):
    def test_features_and_gaps(self):
        features = CursorFeatures()
        result = None
        for i in range(31):
            result = features.update(i / 60, i / 60, 0)
        self.assertAlmostEqual(result[1], 1)
        self.assertAlmostEqual(result[7], 1)
        self.assertIsNone(features.update(2, 0, 0))
        self.assertIsNone(features.update(2, 0, 0))
        self.assertIsNone(features.update(3, float('nan'), 0))

    def test_no_model(self):
        state = CursorState(model_path=None)
        self.assertEqual(state.update(0, 0, 0)[0], 'UNTRAINED')

    def test_training_roundtrip(self):
        # Synthetic data verifies plumbing only, never real-world accuracy.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for session in range(4):
                with (root / f'{session}.csv').open('w', newline='') as stream:
                    writer = csv.writer(stream)
                    writer.writerow(['session', 'timestamp', 'x', 'y', 'mode', 'label'])
                    for j, label in enumerate(LABELS):
                        for i in range(90):
                            t = i / 60
                            x = 0.5 if j == 0 else 0.1 + t * (0.01 if j == 1 else 0.4)
                            writer.writerow([str(session), j * 3 + t, x, 0.5, 'POINT', label])
            x, y, groups = load_sessions([root / '0.csv'])
            self.assertEqual(set(y), set(LABELS))
            self.assertTrue(np.isfinite(x).all())
            model_path = root / 'model.joblib'
            subprocess.run([sys.executable, '-m', 'cursor_stabilization.train_cursor_classifier',
                            '--data-dir', str(root), '--test-session', '3.csv',
                            '--output', str(model_path)], check=True, capture_output=True)
            state = CursorState(model_path=model_path)
            for i in range(60):
                label, score = state.update(i / 60, 0.5, 0.5)
            self.assertEqual(label, 'STATIONARY')
            self.assertGreaterEqual(score, 0.7)
            self.assertEqual(state.update(5, 0.5, 0.5)[0], 'UNCERTAIN')


if __name__ == '__main__':
    unittest.main()
