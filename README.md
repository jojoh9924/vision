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
- **Gesture pane** (right side, always on top): a picture of each gesture next to the action it triggers. The row lights up green while its action is active, yellow while a gesture is being held before it fires.
- **Tray icon**: right-click to switch profiles, pause or resume gestures, reopen the windows, or quit.

## Default gestures

| Action | Gesture |
|---|---|
| Move pointer | Index finger up |
| Left button | Pinch thumb + index. Tap to click, hold to drag, two taps to double click |
| Right click | Pinch thumb + middle |
| Double click | Pinch thumb + ring |
| Scroll up | Index + middle, pointing up |
| Scroll down | Index + middle, pointing down |
| Dictate | Open hand, held 1 second |

Two more bundled profiles: **Low dexterity** (no pinches or quick taps, longer holds) and **Legacy** (the original Archand mapping).

## Customising gestures

Click any row in the pane to change it:

- pick a gesture from the list, or
- press **Record** and hold your own pose for 2 seconds. A snapshot of your hand becomes that row's picture.
- set how long the pose must be held before it fires (longer avoids accidental triggers).

If the gesture is already used by another action you are asked whether to move it.

Profiles are JSON files in `profiles/`. Use the **Profile** menu in the pane to make a copy, rename, delete, or restore the bundled ones. The active profile is remembered in `settings.json`.

## Tests

```
.venv\Scripts\python -m pytest tests
```
