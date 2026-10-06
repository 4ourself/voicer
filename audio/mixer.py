"""Final mix: processed voice x master volume, soft-limited."""
from __future__ import annotations

import numpy as np


def soft_limit(x: np.ndarray, knee: float = 0.8) -> np.ndarray:
    """Transparent below `knee`, smoothly saturates towards +-1 above it."""
    a = np.abs(x)
    if a.max(initial=0.0) <= knee:
        return x
    over = knee + (1 - knee) * np.tanh((a - knee) / (1 - knee))
    return np.where(a > knee, np.sign(x) * over, x).astype(np.float32)


class Mixer:
    def __init__(self):
        self.voice_volume = 1.0

    def mix(self, voice_stereo: np.ndarray, frames: int) -> np.ndarray:
        return soft_limit(voice_stereo * np.float32(self.voice_volume))
