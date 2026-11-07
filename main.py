import argparse
import sys

from app.controller import Controller
from app.detector import ensure_model


def main():
    parser = argparse.ArgumentParser(description="Hand-gesture mouse with remappable gestures")
    parser.add_argument("--camera", type=int, default=0, help="camera index (default 0)")
    parser.add_argument("--no-tray", action="store_true", help="do not show a system tray icon")
    args = parser.parse_args()

    ensure_model()
    controller = Controller(camera_index=args.camera)
    controller.start_hotkey()

    from app.ui.camera_window import CameraWindow
    from app.ui.dictation import DictationUI
    from app.ui.magnifier import create_magnifier
    from app.ui.pane import Pane

    pane = Pane(controller)
    camera = CameraWindow(pane, controller)
    DictationUI(pane, controller)
    camera.protocol("WM_DELETE_WINDOW", lambda: controller.set_camera_visible(False))
    pane.bind("<<ShowCamera>>", lambda e: controller.set_camera_visible(True))
    magnifier = create_magnifier(pane, controller.magnifier_on)

    def apply_visibility(event=None):
        if event in (None, "camera"):
            camera.show() if controller.camera_visible else camera.withdraw()
        if event in (None, "magnifier"):
            magnifier.set_enabled(controller.magnifier_on)

    controller.listen(apply_visibility)
    apply_visibility()

    tray = None

    def quit_app():
        if tray:
            tray.stop()
        magnifier.close()
        controller.stop()
        pane.destroy()

    if not args.no_tray:
        try:
            from app.ui.tray import Tray
            tray = Tray(pane, controller, pane.deiconify, quit_app)
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
        magnifier.close()
        controller.stop()


if __name__ == "__main__":
    main()
