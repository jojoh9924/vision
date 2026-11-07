# Cursor stabilization

The classifier now adjusts One Euro smoothing in normal `main.py` operation,
explicitly enabled by the user before reaching the original 90% per-class target.
The latest comparison accuracy is about 84%; this is not validated target-level
performance. Press `a` in the camera preview to toggle adaptation off/on. The
preview displays the active mode. Recording sessions always use baseline smoothing.

`adaptive_smoothing.py` gradually blends (minimum cutoff, beta) profiles:
STATIONARY (0.7, 0.003), PRECISION (0.9, 0.004), MOVING (1.3, 0.008).
Uncertain, untrained, inactive, or missing-hand states blend toward the original
(1.0, 0.005) baseline. Turning adaptation off restores that baseline immediately.
Position history is preserved, both axes share the policy, and pointing and dragging
use the same filters. These are conservative initial settings, not empirically
optimized ones. This changes smoothing only; it does not predict destinations.

## Collect real examples

From the repository root, using the project's Python environment:

```sh
.venv310/bin/python -m cursor_stabilization.collect_cursor_data
```

Keep the camera preview focused for keyboard controls. Existing cursor movement
and gesture actions remain active while recording. Use the pointing gesture:

- `1`: STATIONARY — hold at different screen locations, allowing natural tremor.
- `2`: PRECISION — make deliberate small corrections and short traces near targets.
- `3`: MOVING — make broad sweeps at varied speeds and directions.
- `0`: pause labeling; use this before changing exercises.
- `q`: finish the session and close the recording.

The first 0.5 seconds after a label change are excluded. Feature windows cannot
cross label, mode, session, or tracking-loss boundaries. These are task labels,
not automatic ground truth: pause/relabel mistakes and review recordings before
training. Collect at least four separate sessions, each covering all three states
with several repetitions (aim for 30–60 seconds per state per session). Include
both pointing and dragging examples if both need reliable classification.
Record additional natural transitions for live review.

CSV recordings contain normalized raw positions, monotonic timestamps, gesture
mode, session ID, and label; no video is saved. Data and model directories are
ignored by Git. Close the recording normally to flush all buffered samples.

## Train and evaluate

Reserve a complete session for final evaluation; replace the example filename:

```sh
.venv310/bin/python -m cursor_stabilization.train_cursor_classifier \
  --test-session YOUR_SESSION.csv
```

At least three other sessions are required for grouped cross-validation. The
fixed small forest is evaluated against a training-derived speed baseline.
Per-class precision/recall, confusion matrix, session IDs, and the offline 90%
precision/recall target result are saved beside the model in `models/`.
Do not repeatedly tune against the reserved session; collect another final test
session after tuning. A high score on scripted exercises is not proof of intent
recognition in normal use.

Run `.venv310/bin/python main.py` to load the model and display STATIONARY,
PRECISION, or MOVING. A score below 0.7 or a pending state transition produces
UNCERTAIN; new labels require 80 ms persistence. The feature window is 200 ms.
Tracking loss clears history and displays NO HAND; non-pointer gestures display
INACTIVE. Only load trusted local joblib files. Retrain after feature/schema or
incompatible dependency changes.

## Validation and limitations

Adaptive smoothing was enabled at the user's request despite not meeting the
original 90% per-class precision/recall target. Compare adaptation on/off using
`a`, checking small-target accuracy, overshoot, stationary jitter, and responsiveness.
Live camera feel still requires testing. Model metrics describe training-time
evaluation; the application toggle controls runtime adaptation independently.
A fresh three-state session is required for independent final evaluation.

## Files and dependencies

- `one_euro_filter.py`: existing filter, relocated without changing behavior.
- `cursor_features.py`: shared causal motion features, normalized by screen size.
- `cursor_state.py`: trusted model loading and confidence/persistence handling.
- `collect_cursor_data.py`: recording entry point and label controls.
- `train_cursor_classifier.py`: grouped evaluation and model export.
- `test_pipeline.py`: synthetic pipeline tests, not model-quality evidence.

New direct dependencies: scikit-learn and joblib. NumPy and OpenCV already exist.
The scikit-learn upper bound preserves Python 3.10 compatibility. Installation
also resolves their transitive dependencies.

```sh
.venv310/bin/python -m unittest cursor_stabilization.test_pipeline
```

## Guided follow-up recordings

Run `.venv310/bin/python -m cursor_stabilization.collect_cursor_data --guided`.
Follow the camera preview prompts: six 30-second exercises with five-second
preparation intervals, totaling 3.5 minutes. The session ends automatically.
Each state appears twice in a different order. Keep the index fingertip inside
the purple active rectangle, especially during sweeps; clipping at its edges
can make moving input appear stationary. Use normal pointing mode throughout.
Press q to abort if necessary; an aborted recording may be incomplete.

`tune_classifier` compares nine forest configurations using grouped training
cross-validation without replacing the live model. Pass `--exclude-session`
for reserved test sessions and incomplete recordings. Its selected score is a
model-selection result, not independent proof of the 90% per-class target.

### Focus on stationary versus precision

Run `.venv310/bin/python -m cursor_stabilization.collect_cursor_data --focus`.
This automatically alternates STATIONARY and PRECISION three times: 30 seconds
per exercise, with five-second unlabeled preparation breaks (3.5 minutes total).
For stationary, intend to hold one point and allow natural tremor. For precision,
make small deliberate moves toward nearby points in varied directions. Use the
preparation breaks to reposition within the purple rectangle. The session ends
and saves automatically; q ends it early. Existing cursor actions remain active.

Focused sessions supplement full sessions; training now permits two-state
sessions while requiring all three classes in every training fold. Reserve a
separate full three-state session for evaluation. These recordings do not change
the deployed model until training is explicitly run.

## Integration with the remappable app

Normal `main.py` starts the current remappable application. Stabilization runs in
`app/engine.py`; the camera window displays state/score and supports the `a` toggle.
Upstream hover locks, pinch protection, and knuckle-based dragging remain intact.
The standalone collection commands use `recording_app.py` with the app's Tasks
hand detector and the original recording gestures. The newer detector may shift
model performance; previous accuracy measurements do not validate this integration.

No recordings or trained model binaries are shipped to GitHub. Without a local
model, baseline One Euro filtering remains available and the state is UNTRAINED.
