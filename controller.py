"""UI-facing facade over the backend (config + AudioEngine).

The TUI never touches DSP, decoding or devices directly: it calls these methods and reads state.
All methods are cheap and thread-safe enough to be called from the UI thread at any frequency;
disk writes are debounced (tick()).
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

from audio import devices as dev
from audio.diagnostics import verdict
from effects.presets import BUILTIN, apply_preset


@dataclass
class DeviceChoice:
    setting: str          # value stored in config: "default" | "none" | device name
    label: str
    index: int | None = None
    samplerate: float | None = None
    virtual: bool = False
    current: bool = False


class Controller:
    SAVE_INTERVAL = 0.5

    def __init__(self, config, engine):
        self.config, self.engine = config, engine
        config.autosave = False            # sliders change 30x/s: persist with a debounce instead
        self._last_save = 0.0
        self._cpu_t = (time.perf_counter(), time.process_time())
        self._cpu = 0.0
        self._ncpu = os.cpu_count() or 1

    # ------------------------------------------------------------------ voice effects
    @property
    def chain(self):
        return self.engine.processor.chain

    def effect(self, name: str):
        return self.engine.processor.effect(name)

    def _changed(self) -> None:
        self.engine.save_effects()

    def set_param(self, effect: str, key: str, value: float) -> float:
        e = self.effect(effect)
        v = e.set(key, value)
        self._changed()
        return v

    def adjust(self, effect: str, key: str, steps: float) -> tuple[float, bool]:
        """Move a parameter by `steps` of its step size. Auto-enables the effect. Returns (value, enabled_now)."""
        e = self.effect(effect)
        p = e.param(key)
        raw = e.get(key) + steps * p.step
        snapped = round((raw - p.min) / p.step) * p.step + p.min
        v = e.set(key, round(snapped, 6))
        newly = False
        if not e.enabled and abs(v - p.default) > 1e-9:
            e.set_enabled(True)
            newly = True
        self._changed()
        return v, newly

    def toggle_effect(self, effect: str) -> bool:
        e = self.effect(effect)
        e.set_enabled(not e.enabled)
        self._changed()
        return e.enabled

    def reset_effect(self, effect: str) -> None:
        self.effect(effect).reset_params()
        self._changed()

    def reset_param(self, effect: str, key: str) -> None:
        e = self.effect(effect)
        e.set(key, e.param(key).default)
        self._changed()

    @property
    def bypass(self) -> bool:
        return self.engine.processor.bypass

    def toggle_bypass(self) -> bool:
        self.engine.set_bypass(not self.bypass)
        return self.bypass

    @property
    def hear_output(self) -> bool:
        return self.engine.hear_output

    def toggle_hear_output(self) -> bool:
        self.engine.set_hear_output(not self.hear_output)
        return self.hear_output

    # ------------------------------------------------------------------ presets
    def preset_names(self) -> list[tuple[str, bool]]:
        """[(name, is_builtin)]"""
        user = self.config.get("presets") or {}
        return [(n, True) for n in BUILTIN] + [(n, False) for n in user]

    def apply_preset(self, name: str) -> None:
        user = self.config.get("presets") or {}
        spec = BUILTIN.get(name) if name in BUILTIN else user.get(name)
        if spec is None:
            raise KeyError(name)
        apply_preset(self.engine.processor, spec)
        self._changed()

    def save_preset(self, name: str) -> None:
        name = name.strip()
        if not name or name in BUILTIN:
            raise ValueError("choose a different preset name")
        user = self.config.get("presets") or {}
        user[name] = self.engine.processor.to_dict()
        self.config.set("presets", user)

    def delete_preset(self, name: str) -> None:
        user = self.config.get("presets") or {}
        user.pop(name, None)
        self.config.set("presets", user)

    # ------------------------------------------------------------------ devices
    ROLE_KEY = {"input": "audio.input_device", "output": "audio.output_device",
                "monitor": "audio.monitor_device"}

    def hostapi(self) -> str:
        try:
            return dev.preferred_hostapi(self.config.get("audio.host_api"))
        except dev.AudioBackendError:
            return ""

    def device_choices(self, role: str) -> list[DeviceChoice]:
        current = self.config.get(self.ROLE_KEY[role])
        out = [DeviceChoice("default", "Default device", current=current == "default")]
        try:
            for d in dev.list_devices("input" if role == "input" else "output", self.hostapi()):
                out.append(DeviceChoice(d.name, d.name, d.index, d.default_samplerate,
                                        dev.is_virtual(d.name), current == d.name))
        except dev.AudioBackendError:
            pass
        if role == "monitor":
            out.append(DeviceChoice("none", "None (no monitoring)", current=current == "none"))
        return out

    def select_device(self, role: str, setting: str) -> bool:
        self.config.set(self.ROLE_KEY[role], setting)
        return self.engine.restart_role(role)

    def refresh_devices(self) -> None:
        self.engine.refresh_devices()

    def first_run_defaults(self) -> dict[str, str]:
        """Sensible first-run picks: default mic, a virtual cable as output when one exists."""
        picks = {"input": "default", "output": "default", "monitor": "default"}
        cables = [c for c in self.device_choices("output") if c.virtual]
        best = next((c for c in cables if "input" in c.label.lower()), cables[0] if cables else None)
        if best:
            picks["output"] = best.setting
        return picks

    # ------------------------------------------------------------------ status / housekeeping
    def cpu_percent(self) -> float:
        now, cpu = time.perf_counter(), time.process_time()
        t0, c0 = self._cpu_t
        if now - t0 >= 1.0:
            self._cpu = (cpu - c0) / (now - t0) / self._ncpu * 100.0
            self._cpu_t = (now, cpu)
        return self._cpu

    def checks(self):
        return verdict(self.engine)

    def drain_notifications(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        import queue
        while True:
            try:
                out.append(self.engine.events.get_nowait())
            except queue.Empty:
                break
        return out

    def tick(self) -> None:
        """Debounced persistence; call from the UI loop."""
        now = time.monotonic()
        if now - self._last_save >= self.SAVE_INTERVAL:
            self._last_save = now
            self.config.save_if_dirty()

    def shutdown(self) -> None:
        """Ordered shutdown: audio streams -> persist."""
        for step in (self.engine.stop, self.engine.save_effects, self.config.save):
            try:
                step()
            except Exception:  # noqa: BLE001 - keep going: every device must be released
                pass
