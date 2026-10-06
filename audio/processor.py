"""Voice processor: the microphone-only effect chain (the soundpad NEVER passes through here)."""
from __future__ import annotations

import numpy as np

from effects import build_chain


class VoiceProcessor:
    def __init__(self, sample_rate: int):
        self.sample_rate = sample_rate
        self.chain = build_chain(sample_rate)
        self.bypass = False
        self.in_level = 0.0
        self.out_level = 0.0
        self.errors: dict[str, str] = {}

    def effect(self, name: str):
        for e in self.chain:
            if e.name == name:
                return e
        raise KeyError(name)

    def process(self, mono: np.ndarray) -> np.ndarray:
        x = mono
        peak = float(np.abs(x).max()) if len(x) else 0.0
        self.in_level = max(peak, self.in_level * 0.9)
        if not self.bypass:
            for e in self.chain:
                if not e.enabled:
                    continue
                try:
                    x = e.process(x)
                except Exception as ex:  # noqa: BLE001 - a broken effect must not kill audio
                    e.enabled = False
                    self.errors[e.name] = repr(ex)
            x = np.clip(x, -1.0, 1.0).astype(np.float32, copy=False)
        peak = float(np.abs(x).max()) if len(x) else 0.0
        self.out_level = max(peak, self.out_level * 0.9)
        return x

    def to_dict(self) -> dict:
        return {e.name: e.to_dict() for e in self.chain}

    def load_dict(self, d: dict) -> None:
        for e in self.chain:
            if e.name in (d or {}):
                e.load_dict(d[e.name])
