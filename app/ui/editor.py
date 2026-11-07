"""Dialog for changing one action's gesture: pick a preset, or record your own pose."""

import tkinter as tk
from collections import Counter
from tkinter import messagebox, ttk

from PIL import ImageTk

from ..actions import ACTIONS
from ..gestures import PRESET_GESTURES, Gesture
from ..icons import render, save_snapshot
from ..profiles import ROOT, Mapping

RECORD_SECONDS = 2.0
SAMPLE_MS = 50
PREVIEW = 128
CUSTOM = "Custom (recorded)"


class MappingEditor(tk.Toplevel):
    def __init__(self, master, controller, action_id):
        super().__init__(master)
        self.c = controller
        self.action = ACTIONS[action_id]
        self.title(f"Gesture for: {self.action.label}")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.transient(master)

        current = controller.profile.mapping_for(action_id)
        self.gesture = current.gesture if current else PRESET_GESTURES[0][1]
        self.image_path = current.image if current else None
        self._recorded_frame = None
        self._recorded_bbox = None
        self._samples = []
        self._recording = False
        self._photo = None

        self._build(current)
        self._show_preview()
        self.grab_set()
        self.geometry(f"+{master.winfo_rootx() - 360}+{master.winfo_rooty() + 80}")

    def _build(self, current):
        pad = {"padx": 10, "pady": 4}
        head = tk.Label(self, text=self.action.label, font=("Segoe UI", 12, "bold"))
        head.grid(row=0, column=0, columnspan=2, sticky="w", **pad)
        if self.action.hint:
            tk.Label(self, text=self.action.hint, fg="#666").grid(row=1, column=0, columnspan=2, sticky="w", padx=10)

        tk.Label(self, text="Choose a gesture").grid(row=2, column=0, sticky="w", **pad)
        names = [n for n, _ in PRESET_GESTURES]
        self.preset_box = ttk.Combobox(self, state="readonly", values=names + [CUSTOM], width=32)
        self.preset_box.grid(row=3, column=0, sticky="we", padx=10)
        self.preset_box.bind("<<ComboboxSelected>>", self._on_preset)
        self._select_preset_for(self.gesture)

        self.preview = tk.Label(self, bg="white", relief="groove", width=PREVIEW, height=PREVIEW)
        self.preview.grid(row=2, column=1, rowspan=4, padx=10, pady=4)

        tk.Label(self, text="or record your own").grid(row=4, column=0, sticky="w", **pad)
        rec = tk.Frame(self)
        rec.grid(row=5, column=0, sticky="we", padx=10)
        self.record_btn = ttk.Button(rec, text=f"Record (hold pose {RECORD_SECONDS:g}s)", command=self._start_record)
        self.record_btn.pack(side="left")
        self.record_status = tk.Label(rec, text="", fg="#1a6", width=18, anchor="w")
        self.record_status.pack(side="left", padx=6)

        tk.Label(self, text="Hold before it triggers (ms)").grid(row=6, column=0, sticky="w", **pad)
        self.hold_var = tk.IntVar(value=current.hold_ms if current else self.action.default_hold_ms)
        ttk.Spinbox(self, from_=0, to=3000, increment=50, textvariable=self.hold_var, width=8).grid(
            row=6, column=1, sticky="w", padx=10)
        tk.Label(self, text="Longer holds avoid accidental triggers; 0 fires immediately.",
                 fg="#666", font=("Segoe UI", 8)).grid(row=7, column=0, columnspan=2, sticky="w", padx=10)

        self.desc = tk.Label(self, text="", fg="#333")
        self.desc.grid(row=8, column=0, columnspan=2, sticky="w", **pad)

        btns = tk.Frame(self)
        btns.grid(row=9, column=0, columnspan=2, sticky="e", padx=10, pady=10)
        ttk.Button(btns, text="Save", command=self._save).pack(side="right", padx=4)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right", padx=4)
        if current:
            ttk.Button(btns, text="Clear mapping", command=self._clear).pack(side="left")

    # preset handling
    def _select_preset_for(self, gesture):
        for name, g in PRESET_GESTURES:
            if g == gesture:
                self.preset_box.set(name)
                return
        self.preset_box.set(CUSTOM)

    def _on_preset(self, _):
        name = self.preset_box.get()
        if name == CUSTOM:
            return
        self.gesture = dict(PRESET_GESTURES)[name]
        self.image_path = None
        self._recorded_frame = None
        self._show_preview()

    def _show_preview(self):
        self._photo = ImageTk.PhotoImage(render(self.gesture, PREVIEW))
        self.preview.configure(image=self._photo, width=PREVIEW, height=PREVIEW)
        self.desc.configure(text=self.gesture.describe())

    # recording
    def _start_record(self):
        if self._recording:
            return
        self._recording = True
        self._samples = []
        self._recorded_frame = None
        self.record_btn.state(["disabled"])
        self._ticks_left = int(RECORD_SECONDS * 1000 / SAMPLE_MS)
        self._record_tick()

    def _record_tick(self):
        s = self.c.worker.snapshot()
        f = s["features"]
        if f is not None:
            self._samples.append((f.fingers_str, f.pinch, f.orientation))
            self._recorded_frame = s["raw_frame"]
            self._recorded_bbox = f.bbox
        secs = self._ticks_left * SAMPLE_MS / 1000
        self.record_status.configure(text=f"Hold it... {secs:.1f}s" if f is not None else "No hand seen")
        self._ticks_left -= 1
        if self._ticks_left > 0:
            self.after(SAMPLE_MS, self._record_tick)
        else:
            self._finish_record()

    def _finish_record(self):
        self._recording = False
        self.record_btn.state(["!disabled"])
        if len(self._samples) < 5:
            self.record_status.configure(text="No hand seen, try again", fg="#a33")
            return
        fingers = Counter(s[0] for s in self._samples).most_common(1)[0][0]
        pinch = Counter(s[1] for s in self._samples).most_common(1)[0][0]
        orientation = Counter(s[2] for s in self._samples).most_common(1)[0][0]
        if pinch:
            fingers = "*****"
        self.gesture = Gesture(fingers, pinch, orientation if orientation != "up" else "any")
        self.image_path = self.c.snapshot_path(self.action.id)
        self.record_status.configure(text="Recorded", fg="#1a6")
        self._select_preset_for(self.gesture)
        self._show_preview()

    # save / clear
    def _save(self):
        try:
            hold = max(0, int(self.hold_var.get()))
        except (tk.TclError, ValueError):
            hold = self.action.default_hold_ms
        conflict = self.c.profile.conflict(self.gesture, self.action.id)
        replace = False
        if conflict:
            other = ACTIONS[conflict.action].label
            if not messagebox.askyesno(
                    "Gesture already used",
                    f"'{self.gesture.describe()}' already triggers {other}.\n\n"
                    f"Use it for {self.action.label} instead and leave {other} unassigned?",
                    parent=self):
                return
            replace = True
        image = None
        if self._recorded_frame is not None and self.image_path:
            save_snapshot(self._recorded_frame, self._recorded_bbox, ROOT / self.image_path)
            image = self.image_path
        elif self.image_path and (ROOT / self.image_path).exists():
            image = self.image_path
        self.c.set_mapping(Mapping(self.action.id, self.gesture, hold, image), replace_conflict=replace)
        self.destroy()

    def _clear(self):
        self.c.clear_mapping(self.action.id)
        self.destroy()
