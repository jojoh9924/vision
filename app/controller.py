"""Owns the profile store, engine and worker; the UI talks to this and listens for changes."""

from .actions import PyAutoGuiBackend
from .engine import Engine
from .profiles import ROOT, Mapping, Profile, ProfileStore
from .worker import Worker


class Controller:
    def __init__(self, camera_index=0, frame_size=(640, 480)):
        self.store = ProfileStore()
        self.store.ensure_bundled()
        self.profiles: list[Profile] = self.store.load_all()
        self.backend = PyAutoGuiBackend()
        self.engine = Engine(self.backend, frame_size=frame_size)
        self.worker = Worker(self.engine, camera_index, frame_size)
        self.paused = False
        self._listeners = []

        pid = self.store.active_profile_id()
        self.profile = next((p for p in self.profiles if p.id == pid), self.profiles[0])
        self.engine.set_profile(self.profile)

    # lifecycle
    def start(self):
        self.worker.start()

    def stop(self):
        self.worker.stop()
        self.worker.join(timeout=2)
        with self.worker.engine_lock:
            self.engine.release()

    # listeners: fn(event) with event in {"profile", "profiles", "paused"}
    def listen(self, fn):
        self._listeners.append(fn)

    def _notify(self, event):
        for fn in list(self._listeners):
            fn(event)

    # profiles
    def reload_profiles(self):
        self.profiles = self.store.load_all()
        self._notify("profiles")

    def switch_profile(self, pid: str):
        profile = next((p for p in self.profiles if p.id == pid), None)
        if profile is None or profile is self.profile:
            return
        self.profile = profile
        self.store.set_active_profile_id(pid)
        with self.worker.engine_lock:
            self.engine.set_profile(profile)
        self._notify("profile")

    def new_profile(self, name: str) -> Profile:
        clone = self.store.copy(self.profile, name)
        self.reload_profiles()
        self.switch_profile(clone.id)
        return clone

    def rename_profile(self, name: str):
        self.profile.name = name
        self.store.save(self.profile)
        self.reload_profiles()
        self._notify("profile")

    def delete_profile(self) -> bool:
        if self.profile.bundled or len(self.profiles) <= 1:
            return False
        doomed = self.profile.id
        fallback = next(p for p in self.profiles if p.id != doomed)
        self.switch_profile(fallback.id)
        self.store.delete(doomed)
        self.reload_profiles()
        return True

    def reset_bundled(self):
        self.store.ensure_bundled(overwrite=True)
        self.reload_profiles()
        current = next((p for p in self.profiles if p.id == self.profile.id), self.profiles[0])
        self.profile = current
        with self.worker.engine_lock:
            self.engine.set_profile(current)
        self._notify("profile")

    # mappings
    def set_mapping(self, mapping: Mapping, replace_conflict: bool = False):
        conflict = self.profile.conflict(mapping.gesture, mapping.action)
        if conflict and replace_conflict:
            self.profile.clear_mapping(conflict.action)
        self.profile.set_mapping(mapping)
        self._save_and_apply()

    def clear_mapping(self, action_id: str):
        self.profile.clear_mapping(action_id)
        self._save_and_apply()

    def _save_and_apply(self):
        self.store.save(self.profile)
        with self.worker.engine_lock:
            self.engine.refresh_profile()
        self._notify("profile")

    def snapshot_path(self, action_id: str) -> str:
        """Path for a recorded gesture image, relative to the repo root when possible."""
        path = self.store.dir / "images" / f"{self.profile.id}_{action_id}.png"
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)

    # pause
    def set_paused(self, paused: bool):
        self.paused = paused
        with self.worker.engine_lock:
            self.engine.set_paused(paused)
        self._notify("paused")

    def toggle_paused(self):
        self.set_paused(not self.paused)
