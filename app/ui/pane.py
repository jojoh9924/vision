"""Thin always-visible pane on the right: on/off switch, profile picker and the gesture legend."""

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from PIL import Image, ImageDraw, ImageTk

from ..actions import ACTIONS, TOGGLE_ACTION
from ..controller import HOTKEY_LABEL
from ..icons import icon_for, tray_image
from .editor import MappingEditor

PANE_WIDTH = 250   # logical pixels; scaled for the display's DPI at runtime
ICON = 52
POLL_MS = 100

BG = "#f3f4f7"
CARD = "#ffffff"
BORDER = "#e2e4e9"
TILE = "#f1f2f6"
TEXT = "#1d1f24"
MUTED = "#6b7080"
FAINT = "#a3a8b5"
GREEN = "#34c759"
GREEN_DARK = "#1f8a3c"
GREEN_SOFT = "#e6f8ea"
AMBER = "#f5a623"
AMBER_SOFT = "#fff5e0"
RED = "#d9534f"
GREY = "#c9ccd4"

FONT = "Segoe UI"


class Pane(tk.Tk):
    def __init__(self, controller):
        super().__init__()
        self.c = controller
        self.title("Gestures")
        self.configure(bg=BG)
        self.attributes("-topmost", True)
        self.scale = max(1.0, self.winfo_fpixels("1i") / 96)
        self.width = int(PANE_WIDTH * self.scale)
        self.icon = int(ICON * self.scale)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{self.width}x{sh - int(90 * self.scale)}+{sw - self.width - int(10 * self.scale)}+0")
        self.minsize(self.width, 400)
        self.protocol("WM_DELETE_WINDOW", self.withdraw)
        self._app_icon = ImageTk.PhotoImage(tray_image(64))
        self.iconphoto(True, self._app_icon)

        self._rows: dict[str, dict] = {}
        self._photos: list = []
        self._pid_by_name: dict[str, str] = {}
        self._style()
        self._build()
        self.refresh_profiles()
        self.refresh_rows()
        self.c.dispatch = lambda fn: self.after(0, fn)
        self.c.listen(self._on_event)
        self.after(POLL_MS, self._poll)

    # look
    def _style(self):
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure("TCombobox", fieldbackground=CARD, background=CARD, bordercolor=BORDER,
                     arrowcolor=MUTED, padding=4, relief="flat")
        st.map("TCombobox", fieldbackground=[("readonly", CARD)], bordercolor=[("focus", GREEN)])
        st.configure("Flat.TMenubutton", background=CARD, bordercolor=BORDER, relief="flat",
                     padding=4, arrowcolor=MUTED, foreground=MUTED)
        st.map("Flat.TMenubutton", background=[("active", TILE)])
        st.configure("Thin.Vertical.TScrollbar", background=GREY, troughcolor=BG, bordercolor=BG,
                     arrowcolor=BG, relief="flat", width=int(6 * self.scale))
        st.map("Thin.Vertical.TScrollbar", background=[("active", FAINT)])

    def _pad(self, n):
        return int(n * self.scale)

    def _card(self, parent, **kw):
        outer = tk.Frame(parent, bg=BORDER, padx=1, pady=1)
        inner = tk.Frame(outer, bg=CARD, **kw)
        inner.pack(fill="both", expand=True)
        outer.inner = inner
        return outer

    def _section(self, parent, text):
        tk.Label(parent, text=text.upper(), bg=BG, fg=FAINT, anchor="w",
                 font=(FONT, 8, "bold")).pack(fill="x", padx=self._pad(14), pady=(self._pad(12), self._pad(4)))

    # layout
    def _build(self):
        head = tk.Frame(self, bg=BG)
        head.pack(fill="x", padx=self._pad(14), pady=(self._pad(12), 0))
        tk.Label(head, text="Gestures", bg=BG, fg=TEXT, anchor="w", font=(FONT, 14, "bold")).pack(side="left")
        self.fps_label = tk.Label(head, text="", bg=BG, fg=FAINT, font=(FONT, 8))
        self.fps_label.pack(side="right", anchor="s", pady=(0, 3))

        # on/off switch card
        card = self._card(self, padx=self._pad(12), pady=self._pad(10), cursor="hand2")
        card.pack(fill="x", padx=self._pad(12), pady=(self._pad(10), 0))
        row = card.inner
        labels = tk.Frame(row, bg=CARD)
        labels.pack(side="left", fill="x", expand=True)
        tk.Label(labels, text="Gesture control", bg=CARD, fg=TEXT, anchor="w",
                 font=(FONT, 10, "bold")).pack(fill="x")
        self.state_label = tk.Label(labels, text="", bg=CARD, anchor="w", font=(FONT, 9))
        self.state_label.pack(fill="x")
        self.switch = ToggleSwitch(row, self.scale, command=self.c.toggle_paused, bg=CARD)
        self.switch.pack(side="right", padx=(self._pad(8), 0))
        for w in (row, labels, *labels.winfo_children()):
            w.bind("<Button-1>", lambda e: self.c.toggle_paused())
        self.toggle_hint = tk.Label(self, text="", bg=BG, fg=MUTED, anchor="w", justify="left",
                                    font=(FONT, 8), wraplength=self.width - self._pad(28))
        self.toggle_hint.pack(fill="x", padx=self._pad(14), pady=(self._pad(4), 0))

        # profile
        self._section(self, "Profile")
        prow = tk.Frame(self, bg=BG)
        prow.pack(fill="x", padx=self._pad(12))
        self.profile_box = ttk.Combobox(prow, state="readonly", font=(FONT, 10))
        self.profile_box.pack(side="left", fill="x", expand=True)
        self.profile_box.bind("<<ComboboxSelected>>", self._on_profile_selected)
        menu_btn = ttk.Menubutton(prow, text="More", style="Flat.TMenubutton")
        menu = tk.Menu(menu_btn, tearoff=False, font=(FONT, 9))
        menu.add_command(label="New profile (copy of current)...", command=self._new_profile)
        menu.add_command(label="Rename...", command=self._rename_profile)
        menu.add_command(label="Delete", command=self._delete_profile)
        menu.add_separator()
        menu.add_command(label="Show camera", command=lambda: self.event_generate("<<ShowCamera>>"))
        menu.add_command(label="Reset bundled profiles", command=self._reset_bundled)
        menu_btn["menu"] = menu
        menu_btn.pack(side="left", padx=(self._pad(6), 0))

        self.status = tk.Label(self, text="", bg=BG, fg=RED, font=(FONT, 8), anchor="w",
                               wraplength=self.width - self._pad(28), justify="left")
        self.status.pack(fill="x", padx=self._pad(14))

        # actions
        self._section(self, "Actions  ·  click to edit")
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(body, bg=BG, highlightthickness=0)
        self.bar = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview,
                                 style="Thin.Vertical.TScrollbar")
        self.canvas.configure(yscrollcommand=self._on_scroll)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.rows_frame = tk.Frame(self.canvas, bg=BG)
        self._rows_window = self.canvas.create_window((0, 0), window=self.rows_frame, anchor="nw")
        self.rows_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._rows_window, width=e.width))
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _on_scroll(self, lo, hi):
        self.bar.set(lo, hi)
        if float(lo) <= 0.0 and float(hi) >= 1.0:
            self.bar.pack_forget()
        elif not self.bar.winfo_ismapped():
            self.bar.pack(side="right", fill="y")

    def _on_wheel(self, e):
        if self.bar.winfo_ismapped():
            self.canvas.yview_scroll(-int(e.delta / 120), "units")

    def refresh_profiles(self):
        self._pid_by_name = {p.name: p.id for p in self.c.profiles}
        self.profile_box["values"] = list(self._pid_by_name)
        self.profile_box.set(self.c.profile.name)

    def refresh_rows(self):
        for w in self.rows_frame.winfo_children():
            w.destroy()
        self._rows.clear()
        self._photos.clear()
        profile = self.c.profile
        actions = sorted(ACTIONS.values(), key=lambda a: profile.mapping_for(a.id) is None)
        wrap = self.width - self.icon - self._pad(64)
        for action in actions:
            mapping = profile.mapping_for(action.id)
            card = self._card(self.rows_frame, cursor="hand2")
            card.pack(fill="x", padx=self._pad(12), pady=(0, self._pad(6)))
            inner = card.inner
            accent = tk.Frame(inner, bg=CARD, width=self._pad(4))
            accent.pack(side="left", fill="y")
            content = tk.Frame(inner, bg=CARD, padx=self._pad(8), pady=self._pad(7))
            content.pack(side="left", fill="both", expand=True)

            img = icon_for(mapping, self.icon) if mapping else _blank(self.icon)
            photo = ImageTk.PhotoImage(_tile(img, self.icon, self._pad(6)))
            self._photos.append(photo)
            icon = tk.Label(content, image=photo, bg=CARD)
            icon.pack(side="left")

            text = tk.Frame(content, bg=CARD)
            text.pack(side="left", fill="x", expand=True, padx=(self._pad(10), 0))
            tk.Label(text, text=action.label, bg=CARD, fg=TEXT if mapping else MUTED, anchor="w",
                     font=(FONT, 10, "bold")).pack(fill="x")
            desc = mapping.gesture.describe() if mapping else "Not assigned"
            if mapping and mapping.hold_ms >= 300:
                desc += f"  ·  hold {mapping.hold_ms / 1000:g}s"
            tk.Label(text, text=desc, bg=CARD, fg=TEXT if mapping else FAINT, anchor="w", justify="left",
                     wraplength=wrap, font=(FONT, 9)).pack(fill="x")
            if action.hint:
                tk.Label(text, text=action.hint, bg=CARD, fg=MUTED, anchor="w", justify="left",
                         wraplength=wrap, font=(FONT, 8)).pack(fill="x")
            for w in (inner, accent, content, icon, text, *text.winfo_children()):
                w.bind("<Button-1>", lambda e, a=action.id: self._edit(a))
            self._rows[action.id] = {"inner": inner, "accent": accent, "state": None}
        self._update_pause_button()

    # events from controller
    def _on_event(self, event):
        if event == "profiles":
            self.refresh_profiles()
        elif event == "profile":
            self.refresh_profiles()
            self.refresh_rows()
        elif event == "paused":
            self._update_pause_button()

    def _update_pause_button(self):
        self.switch.set(not self.c.paused)
        if self.c.paused:
            self.state_label.configure(text="Off  ·  gestures are ignored", fg=RED)
        else:
            self.state_label.configure(text="On", fg=GREEN_DARK)
        hint = f"Toggle with {HOTKEY_LABEL}"
        toggle = self.c.profile.mapping_for(TOGGLE_ACTION)
        if toggle:
            hint += f", or hold {toggle.gesture.describe().lower()}"
        self.toggle_hint.configure(text=hint)

    # user actions
    def _on_profile_selected(self, _):
        pid = self._pid_by_name.get(self.profile_box.get())
        if pid:
            self.c.switch_profile(pid)
        self.focus()

    def _edit(self, action_id):
        MappingEditor(self, self.c, action_id)

    def _new_profile(self):
        name = simpledialog.askstring("New profile", "Name for the new profile:", parent=self)
        if name and name.strip():
            self.c.new_profile(name.strip())

    def _rename_profile(self):
        if self.c.profile.bundled:
            messagebox.showinfo("Rename", "Bundled profiles cannot be renamed. Make a copy first.", parent=self)
            return
        name = simpledialog.askstring("Rename profile", "New name:", initialvalue=self.c.profile.name, parent=self)
        if name and name.strip():
            self.c.rename_profile(name.strip())

    def _delete_profile(self):
        if self.c.profile.bundled:
            messagebox.showinfo("Delete", "Bundled profiles cannot be deleted.", parent=self)
            return
        if messagebox.askyesno("Delete profile", f"Delete '{self.c.profile.name}'?", parent=self):
            self.c.delete_profile()

    def _reset_bundled(self):
        if messagebox.askyesno("Reset", "Restore the bundled profiles to their defaults?", parent=self):
            self.c.reset_bundled()

    # live highlight
    def _poll(self):
        s = self.c.worker.snapshot()
        active = s["active"].action if s["active"] else None
        candidate = s["candidate"].action if s["candidate"] else None
        for action_id, row in self._rows.items():
            state = "active" if action_id == active else "candidate" if action_id == candidate else None
            if state != row["state"]:
                row["state"] = state
                bg = GREEN_SOFT if state == "active" else AMBER_SOFT if state == "candidate" else CARD
                accent = GREEN if state == "active" else AMBER if state == "candidate" else CARD
                _set_bg(row["inner"], bg)
                row["accent"].configure(bg=accent)
        if s["error"]:
            self.status.configure(text=s["error"])
        else:
            self.status.configure(text="")
        self.fps_label.configure(text=f"{s['fps']:.0f} fps" if s["frame"] is not None else "")
        self.after(POLL_MS, self._poll)


class ToggleSwitch(tk.Canvas):
    """Pill-shaped on/off switch with a sliding knob."""

    def __init__(self, master, scale=1.0, command=None, **kw):
        self.w, self.h = int(46 * scale), int(26 * scale)
        super().__init__(master, width=self.w, height=self.h, highlightthickness=0, bd=0,
                         cursor="hand2", **kw)
        self.command = command
        self.on = True
        self.bind("<Button-1>", lambda e: self.command and self.command())
        self._draw()

    def set(self, on: bool):
        if on != self.on:
            self.on = on
            self._draw()

    def _draw(self):
        self.delete("all")
        w, h, r = self.w, self.h, self.h / 2
        color = GREEN if self.on else GREY
        self.create_oval(0, 0, h, h, fill=color, outline=color)
        self.create_oval(w - h, 0, w, h, fill=color, outline=color)
        self.create_rectangle(r, 0, w - r, h, fill=color, outline=color)
        pad = max(2, int(2 * self.h / 26))
        x = w - h + pad if self.on else pad
        self.create_oval(x, pad, x + h - 2 * pad, h - pad, fill="white", outline="#e6e6e6")


def _set_bg(widget, bg):
    try:
        widget.configure(bg=bg)
    except tk.TclError:
        return
    for child in widget.winfo_children():
        if isinstance(child, tk.Canvas):
            continue
        _set_bg(child, bg)


def _tile(img: Image.Image, size: int, radius: int) -> Image.Image:
    """Icon on a soft rounded tile."""
    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(tile).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=TILE)
    inset = int(size * 0.08)
    icon = img.resize((size - 2 * inset, size - 2 * inset), Image.LANCZOS)
    tile.alpha_composite(icon, (inset, inset))
    return tile


def _blank(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = size * 0.18
    d.ellipse([size / 2 - r, size / 2 - r, size / 2 + r, size / 2 + r], outline=FAINT, width=2)
    return img
