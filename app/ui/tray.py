"""System tray icon: switch profiles, pause, show windows, quit. Callbacks hop onto the Tk thread."""

import pystray
from pystray import Menu, MenuItem

from ..icons import tray_image


class Tray:
    def __init__(self, root, controller, show_pane, show_camera, quit_app):
        self.root = root
        self.c = controller
        self._show_pane = show_pane
        self._show_camera = show_camera
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
        yield MenuItem("Profiles", Menu(self._profile_items))
        yield MenuItem(lambda _: "Resume gestures" if self.c.paused else "Pause gestures",
                       self._on_tk(self.c.toggle_paused))
        yield Menu.SEPARATOR
        yield MenuItem("Show gesture pane", self._on_tk(self._show_pane), default=True)
        yield MenuItem("Show camera", self._on_tk(self._show_camera))
        yield Menu.SEPARATOR
        yield MenuItem("Reset bundled profiles", self._on_tk(self.c.reset_bundled))
        yield MenuItem("Quit", self._on_tk(self._quit))

    def _profile_items(self):
        for p in self.c.profiles:
            yield MenuItem(p.name, self._on_tk(self.c.switch_profile, p.id),
                           checked=lambda _, pid=p.id: self.c.profile.id == pid, radio=True)
