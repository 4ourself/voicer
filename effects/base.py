"""Effect base class: process(audio) + settings, hot-switchable without rebuilding the engine."""
from __future__ import annotations

import threading
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Param:
    key: str
    label: str
    min: float
    max: float
    step: float
    default: float
    unit: str = ""


class Effect:
    name = "effect"
    label = "Effect"
    params: tuple[Param, ...] = ()
    default_enabled = False
    primary = ""          # key of the parameter the dashboard slider edits (defaults to first)

    def __init__(self, sample_rate: int = 48000):
        self.sample_rate = sample_rate
        self.enabled = self.default_enabled
        self._lock = threading.RLock()
        self.values: dict[str, float] = {p.key: p.default for p in self.params}
        self.reset()

    # -- settings ---------------------------------------------------
    def param(self, key: str) -> Param:
        for p in self.params:
            if p.key == key:
                return p
        raise KeyError(key)

    def set(self, key: str, value: float) -> float:
        p = self.param(key)
        value = float(min(p.max, max(p.min, value)))
        with self._lock:
            self.values[key] = value
            self._on_change(key)
        return value

    def get(self, key: str) -> float:
        return self.values[key]

    def reset_params(self) -> None:
        with self._lock:
            for p in self.params:
                self.values[p.key] = p.default
                self._on_change(p.key)

    def set_enabled(self, on: bool) -> None:
        with self._lock:
            if on and not self.enabled:
                self.reset()
            self.enabled = bool(on)

    # -- audio ------------------------------------------------------
    def process(self, x: np.ndarray) -> np.ndarray:
        """x: float32 mono 1-D block. Returns a block of the same length."""
        if not self.enabled:
            return x
        with self._lock:
            return self._process(x)

    def _process(self, x: np.ndarray) -> np.ndarray:  # pragma: no cover
        return x

    def reset(self) -> None:
        """Clear internal DSP state."""

    def _on_change(self, key: str) -> None:
        """Hook: a parameter changed (lock is held)."""

    # -- persistence ------------------------------------------------
    def to_dict(self) -> dict:
        return {"enabled": self.enabled, "params": dict(self.values)}

    def load_dict(self, d: dict) -> None:
        for k, v in (d.get("params") or {}).items():
            try:
                self.set(k, v)
            except KeyError:
                pass
        self.set_enabled(bool(d.get("enabled", self.enabled)))

    @property
    def primary_param(self) -> Param:
        return self.param(self.primary or self.params[0].key)

    def summary(self) -> str:
        parts = []
        for p in self.params:
            v = self.values[p.key]
            parts.append(f"{p.label.lower()} {v:g}{p.unit}")
        return ", ".join(parts)
