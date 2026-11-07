"""System tray icon: on/off switches, show windows, reset, quit. Callbacks hop onto the Tk thread."""

import pystray
from pystray import Menu, MenuItem

from ..icons import tray_image


class Tray:
    def __init__(self, root, controller, show_pane, quit_app):
        self.root = root
        self.c = controller
        self._show_pane = show_pane
        self._quit = quit_app
        self.icon = pystray.Icon("gestures", tray_image(), "Hand gestures", Menu(self._items))
        controller.listen(lambda e: self.icon.update_menu())

    def start(self):
        self.icon.run_detached()

    def stop(self):
        try:
            self.icon.stop()
        except Exception:
            pass

    def _on_tk(self, fn, *args):
        return lambda *_: self.root.after(0, fn, *args)

    def _items(self):
        yield MenuItem("Gesture control", self._on_tk(self.c.toggle_paused),
                       checked=lambda _: not self.c.paused)
        yield MenuItem("Camera view", self._on_tk(self.c.toggle_camera),
                       checked=lambda _: self.c.camera_visible)
        yield MenuItem("Magnifier", self._on_tk(self.c.toggle_magnifier),
                       checked=lambda _: self.c.magnifier_on)
        yield MenuItem("Hover lock (hold still to lock cursor)", self._on_tk(self.c.toggle_hover_lock),
                       checked=lambda _: self.c.hover_lock)
        yield Menu.SEPARATOR
        yield MenuItem("Show gesture pane", self._on_tk(self._show_pane), default=True)
        yield MenuItem("Reset gestures to defaults", self._on_tk(self.c.reset_defaults))
        yield Menu.SEPARATOR
        yield MenuItem("Quit", self._on_tk(self._quit))
