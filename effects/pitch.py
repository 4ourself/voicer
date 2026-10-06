"""Real-time pitch shifter (no speed change): dual-tap crossfaded delay line.

Two read heads sweep through a delay line. Their sweep speed (1 - ratio) shifts the pitch,
and sin^2 windows 180 degrees apart crossfade between them so the jump when a head wraps is
inaudible. Latency is on average WINDOW/2 (~20 ms with a 40 ms window).
"""
import numpy as np

from .base import Effect, Param


class PitchEffect(Effect):
    name = "pitch"
    label = "Pitch"
    primary = "semitones"
    params = (
        Param("semitones", "Semitones", -12, 12, 1, 0, " st"),
        Param("window_ms", "Window", 20, 80, 5, 40, " ms"),
    )

    def reset(self):
        self._size = 8192
        self._buf = np.zeros(self._size, np.float32)
        self._wp = 0
        self._phase = 0.0

    def _ensure(self, n, window):
        need = n + window + 16
        if need > self._size:
            size = 1 << int(np.ceil(np.log2(need)))
            new = np.zeros(size, np.float32)
            # keep recent history aligned (cheap rebuild; only happens when parameters grow)
            old_idx = (self._wp - np.arange(self._size, 0, -1)) % self._size
            new_idx = (self._wp - np.arange(self._size, 0, -1)) % size
            new[new_idx] = self._buf[old_idx]
            self._buf, self._size = new, size

    def _process(self, x):
        st = self.values["semitones"]
        if abs(st) < 1e-3:
            return x
        n = len(x)
        window = int(self.values["window_ms"] / 1000.0 * self.sample_rate)
        self._ensure(n, window)
        mask = self._size - 1
        ratio = 2.0 ** (st / 12.0)

        base = self._wp + np.arange(n)
        self._buf[base & mask] = x

        phase = (self._phase + (1.0 - ratio) / window * np.arange(1, n + 1)) % 1.0
        self._phase = float(phase[-1])

        out = np.zeros(n, np.float32)
        for offset in (0.0, 0.5):
            p = (phase + offset) % 1.0
            pos = base - (p * window + 2.0)
            i0 = np.floor(pos).astype(np.int64)
            frac = (pos - i0).astype(np.float32)
            s = self._buf[i0 & mask] * (1.0 - frac) + self._buf[(i0 + 1) & mask] * frac
            out += s * (np.sin(np.pi * p) ** 2).astype(np.float32)
        self._wp = (self._wp + n) & mask
        return out
