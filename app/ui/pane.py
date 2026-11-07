"""Thin always-visible pane on the right: profile switcher and the gesture -> action legend."""

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from PIL import ImageTk

from ..actions import ACTIONS
from ..icons import icon_for
from .editor import MappingEditor

PANE_WIDTH = 250   # logical pixels; scaled for the display's DPI at runtime
ICON = 56
BG = "#f4f4f6"
ROW_BG = "#ffffff"
ACTIVE_BG = "#c9f2c7"
CANDIDATE_BG = "#fff1c2"
POLL_MS = 100


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

        self._rows: dict[str, tk.Frame] = {}
        self._photos: list = []
        self._pid_by_name: dict[str, str] = {}
        self._build()
        self.refresh_profiles()
        self.refresh_rows()
        self.c.listen(self._on_event)
        self.after(POLL_MS, self._poll)

    # layout
    def _build(self):
        top = tk.Frame(self, bg=BG, padx=8, pady=8)
        top.pack(fill="x")

        tk.Label(top, text="Profile", bg=BG, font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
        self.profile_box = ttk.Combobox(top, state="readonly", width=22)
        self.profile_box.grid(row=1, column=0, columnspan=2, sticky="we", pady=(0, 6))
        self.profile_box.bind("<<ComboboxSelected>>", self._on_profile_selected)

        self.pause_btn = ttk.Button(top, text="Pause", command=self.c.toggle_paused)
        self.pause_btn.grid(row=2, column=0, sticky="we", padx=(0, 4))

        menu_btn = ttk.Menubutton(top, text="Profile ▾")
        menu = tk.Menu(menu_btn, tearoff=False)
        menu.add_command(label="New profile (copy of current)...", command=self._new_profile)
        menu.add_command(label="Rename...", command=self._rename_profile)
        menu.add_command(label="Delete", command=self._delete_profile)
        menu.add_separator()
        menu.add_command(label="Show camera", command=lambda: self.event_generate("<<ShowCamera>>"))
        menu.add_command(label="Reset bundled profiles", command=self._reset_bundled)
        menu_btn["menu"] = menu
        menu_btn.grid(row=2, column=1, sticky="we")
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)

        self.status = tk.Label(self, text="", bg=BG, fg="#a33", font=("Segoe UI", 8),
                               wraplength=self.width - 20, justify="left")
        self.status.pack(fill="x", padx=8)

        hint = tk.Label(self, text="Click a row to change its gesture", bg=BG, fg="#666",
                        font=("Segoe UI", 8))
        hint.pack(fill="x", padx=8, pady=(0, 4))

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(body, bg=BG, highlightthickness=0)
        bar = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.rows_frame = tk.Frame(self.canvas, bg=BG)
        self._rows_window = self.canvas.create_window((0, 0), window=self.rows_frame, anchor="nw")
        self.rows_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._rows_window, width=e.width))
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(-int(e.delta / 120), "units"))

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
        # assigned actions first, unassigned at the bottom
        actions = sorted(ACTIONS.values(), key=lambda a: profile.mapping_for(a.id) is None)
        for action in actions:
            mapping = profile.mapping_for(action.id)
            row = tk.Frame(self.rows_frame, bg=ROW_BG, padx=6, pady=6, cursor="hand2")
            row.pack(fill="x", padx=8, pady=3)
            if mapping:
                photo = ImageTk.PhotoImage(icon_for(mapping, self.icon))
            else:
                photo = ImageTk.PhotoImage(_blank(self.icon))
            self._photos.append(photo)
            icon = tk.Label(row, image=photo, bg=ROW_BG)
            icon.pack(side="left")
            text = tk.Frame(row, bg=ROW_BG)
            text.pack(side="left", fill="x", expand=True, padx=(8, 0))
            tk.Label(text, text=action.label, bg=ROW_BG, anchor="w",
                     font=("Segoe UI", 10, "bold")).pack(fill="x")
            desc = mapping.gesture.describe() if mapping else "unassigned"
            if mapping and mapping.hold_ms >= 300:
                desc += f"  (hold {mapping.hold_ms / 1000:g}s)"
            tk.Label(text, text=desc, bg=ROW_BG, anchor="w", justify="left",
                     fg="#222" if mapping else "#999",
                     wraplength=self.width - self.icon - int(60 * self.scale), font=("Segoe UI", 9)).pack(fill="x")
            if action.hint:
                tk.Label(text, text=action.hint, bg=ROW_BG, anchor="w", justify="left", fg="#777",
                         wraplength=self.width - self.icon - int(60 * self.scale), font=("Segoe UI", 8)).pack(fill="x")
            if action.id == "speech_to_text" and not self.c.backend.speech_available:
                tk.Label(text, text="microphone unavailable", bg=ROW_BG, anchor="w", fg="#a33",
                         font=("Segoe UI", 8)).pack(fill="x")
            for w in (row, icon, text, *text.winfo_children()):
                w.bind("<Button-1>", lambda e, a=action.id: self._edit(a))
            self._rows[action.id] = row
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
        self.pause_btn.configure(text="Resume" if self.c.paused else "Pause")

    # user actions
    def _on_profile_selected(self, _):
        pid = self._pid_by_name.get(self.profile_box.get())
        if pid:
            self.c.switch_profile(pid)

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
            bg = ACTIVE_BG if action_id == active else CANDIDATE_BG if action_id == candidate else ROW_BG
            if row["bg"] != bg:
                _set_bg(row, bg)
        if s["error"]:
            self.status.configure(text=s["error"])
        elif self.c.paused:
            self.status.configure(text="Paused: gestures are ignored", fg="#a60")
        else:
            self.status.configure(text="")
        self.after(POLL_MS, self._poll)


def _set_bg(widget, bg):
    try:
        widget.configure(bg=bg)
    except tk.TclError:
        return
    for child in widget.winfo_children():
        _set_bg(child, bg)


def _blank(size):
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([4, 4, size - 5, size - 5], radius=8, outline=(200, 200, 200), width=2)
    d.text((size / 2 - 4, size / 2 - 8), "?", fill=(170, 170, 170))
    return img
