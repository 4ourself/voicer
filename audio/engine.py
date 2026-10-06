"""Global audio engine.

    mic stream -> VoiceProcessor (effects) -> mic ring -> Mixer -> output device (e.g. virtual cable)
                                                                 └-> monitor ring -> monitor device (Hear Output)

Threads: PortAudio callback threads (mic / output / monitor) do only lightweight numpy work;
a watchdog thread detects lost devices and reconnects them; the UI only reads/writes plain
attributes (effect parameters are applied under a per-effect lock that is never held for long).
"""
from __future__ import annotations

import queue
import threading
import time

import numpy as np

from .capture import MicCapture
from .devices import (AudioBackendError, friendly_error, preferred_hostapi, refresh_backend,
                      resolve_device)
from .meters import WaveHistory
from .mixer import Mixer
from .output import OutputSink
from .processor import VoiceProcessor
from .ringbuffer import JitterReader, RingBuffer

ROLES = ("output", "input", "monitor")


class AudioEngine:
    def __init__(self, config):
        self.cfg = config
        self.sr = int(config.get("audio.sample_rate"))
        self.block = int(config.get("audio.block_size"))
        self.processor = VoiceProcessor(self.sr)
        self.processor.load_dict(config.get("effects"))
        self.processor.bypass = bool(config.get("audio.bypass"))
        self.mixer = Mixer()
        self.mixer.voice_volume = float(config.get("mixer.voice_volume"))
        self.monitor_volume = float(config.get("mixer.monitor_volume"))
        self.hear_output = bool(config.get("audio.hear_output"))
        self.output_mono = bool(config.get("audio.output_mono"))

        self._mic_ring = RingBuffer(self.sr, 1)
        self._mon_ring = RingBuffer(self.sr, 2)
        self._mic_reader = JitterReader(self._mic_ring)
        self._mon_reader = JitterReader(self._mon_ring)

        self._capture = MicCapture(self._on_mic_block)
        self._output = OutputSink(self._fill_output, "output")
        self._monitor = OutputSink(self._fill_monitor, "monitor")
        self.running = False
        self.has_input = False
        self.has_monitor = False
        self.health = {r: {"state": "init", "name": "", "index": None, "samplerate": None,
                           "error": ""} for r in ROLES}
        self.warnings: list[str] = []
        self.events: queue.SimpleQueue = queue.SimpleQueue()   # (level, text) for the UI
        self.out_level = 0.0
        self.mon_level = 0.0
        self.last_error = ""
        self.mic_blocks = 0
        self.wave_in = WaveHistory()
        self.wave_out = WaveHistory()
        self._lock = threading.RLock()
        self._epoch = 0
        self._hostapi: str | None = None
        self._stop_evt = threading.Event()
        self._watchdog: threading.Thread | None = None

    # ------------------------------------------------------------ audio callbacks (real-time thread!)
    def _on_mic_block(self, mono: np.ndarray) -> None:
        self.mic_blocks += 1
        try:
            if len(mono):
                self.wave_in.push(float(mono.min()), float(mono.max()))
            self._mic_ring.write(self.processor.process(mono))
        except Exception as e:  # noqa: BLE001
            self.last_error = repr(e)

    def _fill_output(self, frames: int) -> np.ndarray:
        # 1) voice stream (already processed by the effect chain in the mic callback)
        if self.has_input:
            voice = np.repeat(self._mic_reader.read(frames), 2, axis=1)
        else:
            voice = np.zeros((frames, 2), np.float32)
        mixed = self.mixer.mix(voice, frames)
        if self.output_mono:
            mixed = np.repeat(mixed.mean(axis=1, keepdims=True), 2, axis=1)
        if self.hear_output and self.has_monitor:
            self._mon_ring.write(mixed * np.float32(self.monitor_volume))
        lo, hi = float(mixed.min()), float(mixed.max())
        self.wave_out.push(lo, hi)
        self.out_level = max(max(abs(lo), abs(hi)), self.out_level * 0.9)
        return mixed

    def _fill_monitor(self, frames: int) -> np.ndarray:
        if not self.hear_output:
            self.mon_level *= 0.9
            return np.zeros((frames, 2), np.float32)
        block = self._mon_reader.read(frames)
        self.mon_level = max(float(np.abs(block).max()), self.mon_level * 0.9)
        return block

    # ------------------------------------------------------------ roles
    def _sink(self, role):
        return {"output": self._output, "input": self._capture, "monitor": self._monitor}[role]

    def _counter(self, role) -> int:
        return {"output": self._output.callbacks, "input": self.mic_blocks,
                "monitor": self._monitor.callbacks}[role]

    def _set_flag(self, role: str, on: bool) -> None:
        if role == "input":
            self.has_input = on
        elif role == "monitor":
            self.has_monitor = on

    def _close_role(self, role: str) -> None:
        self._sink(role).stop()
        self._set_flag(role, False)

    def _open_role(self, role: str) -> bool:
        h = self.health[role]
        setting = self.cfg.get(f"audio.{role}_device")
        h.update(state="disconnected", name="" if setting in ("default", "none") else setting,
                 index=None, samplerate=None, error="")
        self._close_role(role)
        if role == "monitor" and setting == "none":
            h["state"] = "disabled"
            return False
        if self._hostapi is None:
            h["error"] = "audio backend unavailable"
            return False
        try:
            info, note = resolve_device("input" if role == "input" else "output", setting,
                                        self._hostapi, strict=True)
        except Exception as e:  # noqa: BLE001
            h["error"] = friendly_error(str(e))
            return False
        if info is None:
            h["error"] = note or "no default device"
            return False
        try:
            self._sink(role).start(info, self.sr, self.block)
        except Exception as e:  # noqa: BLE001
            h["error"] = friendly_error(str(e))
            return False
        h.update(state="ok", name=info.name, index=info.index, samplerate=info.default_samplerate, error="")
        self._set_flag(role, True)
        return True

    def restart_role(self, role: str) -> bool:
        """Re-open ONE device after the user picked a new one. Other streams are untouched."""
        with self._lock:
            ok = self._open_role(role)
            self._epoch += 1
            self.running = self.health["output"]["state"] == "ok"
            return ok

    # ------------------------------------------------------------ lifecycle
    def start(self) -> list[str]:
        """Open all streams. Never raises: failures are reported through `health`/`warnings`/`events`."""
        with self._lock:
            self._close_all()
            self.sr = int(self.cfg.get("audio.sample_rate"))
            self.block = int(self.cfg.get("audio.block_size"))
            jitter = int(self.cfg.get("audio.jitter_blocks"))
            self.output_mono = bool(self.cfg.get("audio.output_mono"))
            self._mic_reader = JitterReader(self._mic_ring, jitter)
            self._mon_reader = JitterReader(self._mon_ring, jitter)
            self._mic_ring.clear()
            self._mon_ring.clear()
            try:
                self._hostapi = preferred_hostapi(self.cfg.get("audio.host_api"))
            except AudioBackendError as e:
                self._hostapi = None
                self.events.put(("error", str(e)))
            for role in ROLES:
                self._open_role(role)
            self._epoch += 1
            self.running = self.health["output"]["state"] == "ok"
            self.warnings = [f"{r}: {h['error']}" for r, h in self.health.items()
                             if h["state"] == "disconnected" and h["error"]]
            warnings = list(self.warnings)
        self._start_watchdog()
        return warnings

    def _close_all(self) -> None:
        for role in ROLES:
            self._close_role(role)
        self.running = False

    def stop(self) -> None:
        self._stop_evt.set()
        if self._watchdog is not None:
            self._watchdog.join(timeout=1.5)
            self._watchdog = None
        with self._lock:
            self._close_all()

    def refresh_devices(self) -> None:
        """Explicit device refresh (UI key R): close everything, re-enumerate, reopen."""
        with self._lock:
            self._close_all()
            try:
                refresh_backend()
            except AudioBackendError:
                pass
        self.start()
        self.events.put(("info", "Devices refreshed"))

    # ------------------------------------------------------------ watchdog / recovery
    def _start_watchdog(self) -> None:
        if self._watchdog is not None and self._watchdog.is_alive():
            return
        self._stop_evt.clear()
        self._watchdog = threading.Thread(target=self._watch, daemon=True, name="audio-watchdog")
        self._watchdog.start()

    def _lose(self, role: str, msg: str) -> None:
        self._close_role(role)
        h = self.health[role]
        h.update(state="disconnected", error=msg)
        self.running = self.health["output"]["state"] == "ok"
        self.events.put(("warn", f"{role.upper()} {msg}: {h['name'] or role}"))

    def _watch(self) -> None:
        seen: dict[str, tuple[int, float]] = {}
        retry: dict[str, float] = {}
        epoch = -1
        last_full = time.monotonic()
        while not self._stop_evt.wait(0.5):
            if not self._lock.acquire(timeout=0.3):
                continue
            try:
                now = time.monotonic()
                if epoch != self._epoch:        # streams were (re)opened: restart baselines
                    epoch = self._epoch
                    seen = {r: (self._counter(r), now) for r in ROLES}
                    retry = {}
                for role in ROLES:
                    h = self.health[role]
                    if h["state"] == "ok":
                        cnt = self._counter(role)
                        stream = self._sink(role).stream
                        if cnt != seen[role][0]:
                            seen[role] = (cnt, now)
                        elif now - seen[role][1] > 1.5 or (stream is not None and not getattr(stream, "active", True)):
                            self._lose(role, "disconnected")
                    elif h["state"] == "disconnected" and now >= retry.get(role, 0):
                        if self._open_role(role):
                            seen[role] = (self._counter(role), now)
                            self.running = self.health["output"]["state"] == "ok"
                            self.events.put(("info", f"{role.upper()} reconnected: {h['name']}"))
                        else:
                            retry[role] = now + 3.0
                lost = any(h["state"] == "disconnected" for h in self.health.values())
                if lost and now - last_full > 15.0:
                    # cheap retries cannot see newly plugged devices (PortAudio caches the list):
                    # every 15 s re-enumerate with all streams closed.
                    last_full = now
                    self._close_all()
                    try:
                        refresh_backend()
                    except AudioBackendError:
                        pass
                    for role in ROLES:
                        self._open_role(role)
                    self._epoch += 1
                    self.running = self.health["output"]["state"] == "ok"
            except Exception as e:  # noqa: BLE001 - the watchdog must never die
                self.last_error = repr(e)
            finally:
                self._lock.release()

    # ------------------------------------------------------------ live controls (UI thread)
    def set_hear_output(self, on: bool) -> None:
        self.hear_output = bool(on)
        if not on:
            self._mon_ring.clear()
        self.cfg.set("audio.hear_output", self.hear_output)

    def set_bypass(self, on: bool) -> None:
        self.processor.bypass = bool(on)       # affects the voice chain ONLY
        self.cfg.set("audio.bypass", bool(on))

    def set_output_mono(self, on: bool) -> None:
        self.output_mono = bool(on)
        self.cfg.set("audio.output_mono", bool(on))

    def set_volume(self, which: str, value: float) -> None:
        value = max(0.0, min(2.0, value))
        if which == "voice":
            self.mixer.voice_volume = value
        elif which == "monitor":
            self.monitor_volume = value
        else:
            raise KeyError(which)
        self.cfg.set(f"mixer.{which}_volume", value)

    def save_effects(self) -> None:
        self.cfg.set("effects", self.processor.to_dict())

    # ------------------------------------------------------------ status
    @property
    def state(self) -> str:
        if self._epoch == 0:
            return "STARTING"
        if not self.running or any(h["state"] == "disconnected" for h in self.health.values()):
            return "DEVICE ERROR"
        return "RUNNING"

    def latency_ms(self) -> float:
        """Approximate mic->output latency: stream latencies + jitter buffer + pitch window."""
        def lat(sink):
            v = getattr(sink.stream, "latency", 0.0) if sink.stream is not None else 0.0
            return float(v[0] if isinstance(v, (tuple, list)) else v or 0.0)
        ms = (lat(self._capture) + lat(self._output)) * 1000.0
        ms += self.block / self.sr * 1000.0 * (self._mic_reader.jitter_blocks + 0.5)
        pitch = self.processor.effect("pitch")
        if pitch.enabled and not self.processor.bypass and abs(pitch.get("semitones")) > 0.01:
            ms += pitch.get("window_ms") / 2.0
        return ms

    def stats(self) -> dict:
        return {
            "running": self.running, "has_input": self.has_input, "has_monitor": self.has_monitor,
            "mic_in": self.processor.in_level, "mic_out": self.processor.out_level,
            "out": self.out_level, "monitor": self.mon_level,
            "underruns": self._mic_reader.underruns + self._mon_reader.underruns,
            "last_error": self.last_error,
        }
