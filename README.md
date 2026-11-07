# vision

Control the mouse with hand gestures from your webcam, with gestures you can remap to suit your mobility.

## Setup

```
py -3.13 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py
```

The hand-tracking model (about 8 MB) is downloaded into `assets/` on first run.
Options: `--camera N` to pick a webcam, `--no-tray` to skip the system tray icon.

## What you see

- **Camera window** (top-left, small): your mirrored webcam feed with the detected hand. The caption shows the gesture being recognised and the action it triggers.
- **Gesture pane** (right side, always on top): switches for gesture control, the camera view and the magnifier, then a picture of each gesture next to the action it triggers. A row lights up green while its action is active, amber while a gesture is being held before it fires.
- **Magnifier**: a zoom box beside the pointer showing what is under it, for reading small targets. On macOS it uses the AppKit magnifier in `magnifier.py`; elsewhere a portable one.
- **Tray icon**: right-click for the same switches, to reopen the pane, reset gestures, or quit.

## Turning gesture control on and off

Three ways, all equivalent:

- the **Gesture control** switch at the top of the pane (also in the tray menu),
- the global hotkey **Ctrl+Alt+G**, which works in any application,
- the **Pause / resume gestures** action, a gesture that keeps working while everything else is paused (default: thumb + pinky held 1.5 s). It is remappable like any other action.

While paused the camera window shows PAUSED and no gesture moves the mouse.

## Default gestures

| Action | Gesture |
|---|---|
| Move pointer | Index finger up (thumb either way) |
| Left button | Pinch thumb + index. Tap to click, hold to drag, two taps to double click |
| Right click | Pinch thumb + middle |
| Double click | Pinch thumb + ring |
| Scroll up | Index + middle, pointing up |
| Scroll down | Index + middle, pointing down |
| Dictate | Open hand, held 1 second |
| Pause / resume gestures | Thumb + pinky, held 1.5 seconds |

Left click and Drag exist as separate actions for people who cannot tap or hold a pinch; assign them a gesture if you need them.

## Customising gestures

Click any row in the pane to change it:

- pick a gesture from the list, or
- press **Record my own pose**: gesture control pauses, a 3-second countdown lets you get your hand ready, then your pose is recorded for 4 seconds. A snapshot of your hand becomes that row's picture.
- **Clear mapping** removes the gesture so the action does nothing.

If the gesture is already used by another action you are asked whether to move it.

Your gesture set is saved in `profiles/default.json`. **Reset to defaults** (bottom of the pane, or the tray menu) restores the table above. Switch states are remembered in `settings.json`.

## Tests

```
.venv\Scripts\python -m pytest tests
```

## Cursor stabilization

Cursor movement uses One Euro filtering. If a locally trained classifier is
available, STATIONARY / PRECISION / MOVING predictions gradually adjust the
filter settings. Press **a** with the camera window focused to toggle adaptive
smoothing. Existing hover locking and pinch/drag protections still apply.

Recordings, trained models, and virtual environments are intentionally excluded
from Git. A fresh checkout runs baseline One Euro filtering and displays
UNTRAINED until a model is trained locally. See
[cursor stabilization setup and training](cursor_stabilization/README.md).
