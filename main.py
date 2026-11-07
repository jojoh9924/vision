import argparse
import sys

from app.controller import Controller
from app.detector import ensure_model

MAGNIFIER_MS = 33


def start_magnifier(root):
    """macOS only: the zoom box from magnifier.py follows the pointer. Silently skipped elsewhere."""
    if sys.platform != "darwin":
        return None
    try:
        from magnifier import ScreenMagnifier
        magnifier = ScreenMagnifier()
    except Exception as e:
        print(f"Magnifier unavailable: {e}", file=sys.stderr)
        return None

    def tick():
        magnifier.update()
        root.after(MAGNIFIER_MS, tick)

    root.after(MAGNIFIER_MS, tick)
    return magnifier


def main():
    parser = argparse.ArgumentParser(description="Hand-gesture mouse with remappable gestures")
    parser.add_argument("--camera", type=int, default=0, help="camera index (default 0)")
    parser.add_argument("--no-tray", action="store_true", help="do not show a system tray icon")
    parser.add_argument("--no-magnifier", action="store_true", help="macOS: do not show the zoom box")
    args = parser.parse_args()

    ensure_model()
    controller = Controller(camera_index=args.camera)
    controller.start_hotkey()

    from app.ui.camera_window import CameraWindow
    from app.ui.dictation import DictationUI
    from app.ui.pane import Pane

    pane = Pane(controller)
    camera = CameraWindow(pane, controller)
    DictationUI(pane, controller)
    pane.bind("<<ShowCamera>>", lambda e: camera.show())
    magnifier = None if args.no_magnifier else start_magnifier(pane)

    tray = None

    def quit_app():
        if tray:
            tray.stop()
        controller.stop()
        pane.destroy()

    if not args.no_tray:
        try:
            from app.ui.tray import Tray
            tray = Tray(pane, controller, pane.deiconify, camera.show, quit_app)
            tray.start()
        except Exception as e:  # tray is optional
            print(f"Tray icon unavailable: {e}", file=sys.stderr)
    else:
        pane.protocol("WM_DELETE_WINDOW", quit_app)

    controller.start()
    try:
        pane.mainloop()
    finally:
        if tray:
            tray.stop()
        if magnifier:
            magnifier.close()
        controller.stop()


if __name__ == "__main__":
    main()
