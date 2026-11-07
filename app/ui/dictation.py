"""Dictation prompts: a confirm card at the text cursor, then a floating status pill with Stop.

The card opens each time you click into a text field, anchored to the text
cursor, and goes away if you start typing.
Targets are at least 44 pt tall, text is high contrast, and nothing flashes.
The app you were typing in gets keyboard focus back, so dictated text lands
there and not in these windows.
"""

import math
import os
import sys
import time
import tkinter as tk
from tkinter import font as tkfont

from ..caret import FIELD_WITHOUT_POSITION, focused_text_field, text_length

TICK_MS = 100
WATCH_MS = 250            # how often to check for clicks and which text field has focus
CLICK_GRACE = 0.8         # seconds a click waits for focus to land in a text field
CARET_GAP = 6
POINTER_HALF = 10         # half the height of the I-beam pointer, so the card clears it
NEAR_POINTER = 40         # text cursor this close to the click is trusted over the pointer
TAIL_W, TAIL_H = 16, 8
TOP_MARGIN = 46           # clears the menu bar

CLEAR = "systemTransparent"
CARD_BG = "#ffffff"
INK = "#1d1d1f"
MUTED = "#5f6068"
PRIMARY = "#0066d6"
PRIMARY_HOVER = "#0055b3"
SECONDARY = "#ececf0"
SECONDARY_HOVER = "#dfdfe5"
PILL_BG = "#1d1d1f"
PILL_MUTED = "#a1a1a8"
STOP = "#d92d20"
STOP_HOVER = "#b8251a"
LIVE = "#ff453a"
WAIT = "#f5a623"

STATUS_TEXT = {"loading": "Getting ready…", "listening": "Listening", "finishing": "Finishing…"}


def _family():
    return tkfont.nametofont("TkDefaultFont").actual("family")


def round_rect(canvas, x1, y1, x2, y2, r, **kw):
    r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
    steps = max(8, int(r * 1.5))
    pts = []
    for cx, cy, start in ((x2 - r, y1 + r, -90), (x2 - r, y2 - r, 0),
                          (x1 + r, y2 - r, 90), (x1 + r, y1 + r, 180)):
        for i in range(steps + 1):
            a = math.radians(start + i * 90 / steps)
            pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
    return canvas.create_polygon(pts, width=0, **kw)


class PillButton:
    def __init__(self, canvas, x, y, w, h, text, font, bg, hover, fg, command):
        self.canvas = canvas
        tag = f"button{id(self)}"
        self.shape = round_rect(canvas, x, y, x + w, y + h, h / 2, fill=bg, tags=(tag,))
        canvas.create_text(x + w / 2, y + h / 2, text=text, fill=fg, font=font, tags=(tag,))
        canvas.tag_bind(tag, "<Enter>", lambda e: self._hover(hover, "pointinghand"))
        canvas.tag_bind(tag, "<Leave>", lambda e: self._hover(bg, ""))
        canvas.tag_bind(tag, "<ButtonRelease-1>", lambda e: command())

    def _hover(self, color, cursor):
        self.canvas.itemconfigure(self.shape, fill=color)
        self.canvas.configure(cursor=cursor)


class Floating(tk.Toplevel):
    """Borderless, rounded, shadowed window that floats above every app."""

    def __init__(self, master, title, width, height):
        super().__init__(master, bg=CLEAR)
        self.title(title)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        if sys.platform == "darwin":
            self.attributes("-transparent", True)
        self.width, self.height = width, height
        self.canvas = tk.Canvas(self, width=width, height=height, bg=CLEAR, highlightthickness=0, bd=0)
        self.canvas.pack()
        self.family = _family()

    def show_at(self, x, y):
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = int(min(max(8, x), sw - self.width - 8))
        y = int(min(max(TOP_MARGIN - 16, y), sh - self.height - 8))
        self.geometry(f"{self.width}x{self.height}+{x}+{y}")
        _float_above_apps(self)
        return x, y


class ConfirmCard(Floating):
    WIDTH, BODY_H = 300, 132

    def __init__(self, master, anchor, on_start, on_cancel):
        """`anchor` is the (x, y, w, h) screen rect the card's tail points at."""
        super().__init__(master, "Speech-to-text confirm", self.WIDTH, self.BODY_H + TAIL_H)
        sh = self.winfo_screenheight()
        ax, ay, _aw, ah = anchor
        below = ay + ah + CARET_GAP + self.height <= sh - 8
        wy = ay + ah + CARET_GAP if below else ay - CARET_GAP - self.height
        wx, wy = self.show_at(ax - 32, wy)
        tail_x = min(max(24, ax - wx), self.width - 24)
        self._draw(below, tail_x, on_start, on_cancel)
        _float_above_apps(self)   # recompute the shadow for the drawn shape

    def _draw(self, below, tail_x, on_start, on_cancel):
        c, f = self.canvas, self.family
        top = TAIL_H if below else 0
        round_rect(c, 0, top, self.width, top + self.BODY_H, 16, fill=CARD_BG)
        tip = 0 if below else self.height
        base = top if below else top + self.BODY_H
        c.create_polygon(tail_x - TAIL_W / 2, base, tail_x, tip, tail_x + TAIL_W / 2, base,
                         fill=CARD_BG, width=0)
        pad = 20
        c.create_text(pad, top + pad, anchor="nw", text="Start speech-to-text?", fill=INK, font=(f, 17, "bold"))
        c.create_text(pad, top + pad + 26, anchor="nw", text="Your words are typed at the cursor.",
                      fill=MUTED, font=(f, 14))
        bw, bh = 118, 44
        by = top + self.BODY_H - pad - bh
        PillButton(c, self.width - pad - bw, by, bw, bh, "Start", (f, 15, "bold"),
                   PRIMARY, PRIMARY_HOVER, "#ffffff", on_start)
        PillButton(c, self.width - pad - 2 * bw - 10, by, bw, bh, "Cancel", (f, 15, "bold"),
                   SECONDARY, SECONDARY_HOVER, INK, on_cancel)


class StatusPill(Floating):
    HEIGHT = 60

    def __init__(self, master, on_stop):
        f = _family()
        title = tkfont.Font(family=f, size=16, weight="bold")
        text_w = max(title.measure(t) for t in STATUS_TEXT.values())
        self.stop_w = 92
        width = 24 + 12 + 12 + text_w + 24 + self.stop_w + 10
        super().__init__(master, "Speech-to-text status", width, self.HEIGHT)
        c, h = self.canvas, self.HEIGHT
        round_rect(c, 0, 0, width, h, h / 2, fill=PILL_BG)
        self.dot = c.create_oval(24, h / 2 - 6, 36, h / 2 + 6, width=0)
        self.label = c.create_text(48, h / 2, anchor="w", fill="#ffffff", font=title)
        self.stop = PillButton(c, width - 10 - self.stop_w, 10, self.stop_w, h - 20, "Stop",
                               (f, 15, "bold"), STOP, STOP_HOVER, "#ffffff", on_stop)
        self.stop_tag = c.gettags(self.stop.shape)[0]
        self._state = None
        self.show_at((self.winfo_screenwidth() - width) // 2, TOP_MARGIN)

    def set_state(self, state):
        if state == self._state:
            return
        self._state = state
        c = self.canvas
        c.itemconfigure(self.label, text=STATUS_TEXT[state])
        if state == "listening":
            c.itemconfigure(self.dot, fill=LIVE, outline="")
        else:
            c.itemconfigure(self.dot, fill="", outline=WAIT, width=2)
        c.itemconfigure(self.stop_tag, state="hidden" if state == "finishing" else "normal")


class DictationUI:
    def __init__(self, root, controller):
        self.root = root
        self.c = controller
        self.card = None
        self.pill = None
        self._target_app = None
        self._card_field = None    # text field the open card belongs to
        self._card_chars = None    # its length when the card opened; typing closes the card
        self._last_field = None    # text field seen on the previous watch
        self._watching = False     # becomes True after the first watch, so startup does not prompt
        self._clicks = _click_count()
        self._click_at = None      # time of a click not yet matched to a text field
        self._ignore_clicks_until = 0.0
        root.after(TICK_MS, self._tick)
        root.after(WATCH_MS, self._watch)

    def _open_card(self, element, caret, clicked):
        self._card_field = element
        self._card_chars = text_length(element)
        self.card = ConfirmCard(self.root, self._anchor(caret, clicked), self._start, self._cancel)
        # Showing a window activates this app; give the keyboard back right away.
        self._return_focus()

    def _watch(self):
        """Offer dictation each time the user clicks into a text field (or focus
        moves to a new one); withdraw the offer once they type or leave it."""
        try:
            now = time.monotonic()
            clicks = _click_count()
            if clicks != self._clicks and now >= self._ignore_clicks_until and not self._pointer_on_card():
                self._click_at = now
            self._clicks = clicks
            # Focus can land a moment after the click when switching apps.
            clicked = self._click_at is not None and now - self._click_at <= CLICK_GRACE
            if self.c.backend.dictation_state != "idle" or _we_are_frontmost():
                return
            field = focused_text_field(retry=False)
            element = field[0] if field else None
            if self.card is not None and (
                    clicked or element != self._card_field or text_length(element) != self._card_chars):
                self._close_card()
            if (self.card is None and self._watching and not self.c.paused and element is not None
                    and (clicked or element != self._last_field)):
                self._click_at = None
                self._target_app = _frontmost_app()
                self._open_card(*field, clicked)
            self._last_field = element
            self._watching = True
        finally:
            self.root.after(WATCH_MS, self._watch)

    def _anchor(self, caret, clicked):
        """Point the card at the text cursor when it is where the user is looking,
        otherwise at the mouse pointer. After a click the text cursor can be far
        away (clicking below the text moves it to the end) or only approximate
        (the field's corner, when an app will not report it)."""
        px, py = self.root.winfo_pointerxy()
        pointer = (px, py - POINTER_HALF, 2, 2 * POINTER_HALF)
        if caret == FIELD_WITHOUT_POSITION:
            return pointer
        cx, cy, _cw, ch = caret
        near = abs(cx - px) <= NEAR_POINTER and cy - NEAR_POINTER <= py <= cy + ch + NEAR_POINTER
        return caret if near or not clicked else pointer

    def _pointer_on_card(self):
        if self.card is None:
            return False
        x, y = self.root.winfo_pointerxy()
        cx, cy = self.card.winfo_rootx(), self.card.winfo_rooty()
        return cx <= x < cx + self.card.width and cy <= y < cy + self.card.height

    def _close_card(self):
        if self.card is not None:
            self.card.destroy()
            self.card = None
            self._card_field = None

    def _own_click(self):
        """Clicks on the card or pill must not count as clicking into the text field."""
        self._click_at = None
        self._ignore_clicks_until = time.monotonic() + 0.6

    def _start(self):
        self._own_click()
        self._close_card()
        if self.c.backend.start_dictate():
            self._show_pill()
        self._return_focus()

    def _cancel(self):
        self._own_click()
        self._close_card()
        self._return_focus()

    def _stop(self):
        self._own_click()
        self.c.backend.stop_dictate()
        if self.pill is not None:
            self.pill.set_state("finishing")
        self._return_focus()

    def _return_focus(self):
        if self._target_app is not None:
            self.root.after(60, _activate, self._target_app)

    def _show_pill(self):
        if self.pill is None:
            self.pill = StatusPill(self.root, self._stop)
        self.pill.set_state(self.c.backend.dictation_state if self.c.backend.dictation_state != "idle"
                            else "loading")

    def _tick(self):
        try:
            state = self.c.backend.dictation_state
            if state == "idle":
                if self.pill is not None:
                    self.pill.destroy()
                    self.pill = None
            else:
                self._show_pill()
        finally:
            self.root.after(TICK_MS, self._tick)


def _float_above_apps(win):
    """Tk's -topmost does not lift borderless windows above other apps on macOS,
    so the window would fall behind the app that gets focus back."""
    if sys.platform != "darwin":
        return
    try:
        from AppKit import (NSApplication, NSStatusWindowLevel,
                            NSWindowCollectionBehaviorCanJoinAllSpaces,
                            NSWindowCollectionBehaviorFullScreenAuxiliary)
        win.update_idletasks()
        title = win.title()
        for ns_window in NSApplication.sharedApplication().windows():
            if ns_window.title() == title:
                ns_window.setLevel_(NSStatusWindowLevel)
                ns_window.setHidesOnDeactivate_(False)
                ns_window.setCollectionBehavior_(NSWindowCollectionBehaviorCanJoinAllSpaces
                                                 | NSWindowCollectionBehaviorFullScreenAuxiliary)
                ns_window.setHasShadow_(True)
                ns_window.invalidateShadow()
    except Exception:
        pass


def _frontmost_app():
    """The app that had keyboard focus before the card opened (macOS only)."""
    if sys.platform != "darwin":
        return None
    try:
        from AppKit import NSWorkspace
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
    except Exception:
        return None
    if app is None or app.processIdentifier() == os.getpid():
        return None
    return app


def _click_count():
    """System-wide count of left-button releases, real or from the gesture
    backend. Reading it needs no extra permission."""
    if sys.platform != "darwin":
        return 0
    try:
        import Quartz
        return Quartz.CGEventSourceCounterForEventType(
            Quartz.kCGEventSourceStateCombinedSessionState, Quartz.kCGEventLeftMouseUp)
    except Exception:
        return 0


def _we_are_frontmost():
    if sys.platform != "darwin":
        return False
    try:
        from AppKit import NSWorkspace
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
    except Exception:
        return False
    return app is not None and app.processIdentifier() == os.getpid()


def _activate(app):
    try:
        from AppKit import NSApplicationActivateIgnoringOtherApps
        app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
    except Exception:
        pass
