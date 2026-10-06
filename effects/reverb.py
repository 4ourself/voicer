"""Freeverb-style reverb (8 damped combs + 4 allpasses), vectorised per block."""
import numpy as np
from scipy.signal import lfilter

from .base import Effect, Param

COMBS = (1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617)
ALLPASS = (556, 441, 341, 225)


class _Comb:
    def __init__(self, d):
        self.d, self.buf, self.pos, self.zi = d, np.zeros(d, np.float32), 0, np.zeros(1)

    def process(self, x, fb, damp):
        out = np.empty_like(x)
        i, n = 0, len(x)
        while i < n:
            m = min(self.d - self.pos, n - i)
            o = self.buf[self.pos:self.pos + m].copy()
            f, self.zi = lfilter([1.0 - damp], [1.0, -damp], o, zi=self.zi)
            self.buf[self.pos:self.pos + m] = x[i:i + m] + (f * fb).astype(np.float32)
            out[i:i + m] = o
            self.pos = (self.pos + m) % self.d
            i += m
        return out


class _Allpass:
    def __init__(self, d):
        self.d, self.buf, self.pos = d, np.zeros(d, np.float32), 0

    def process(self, x):
        out = np.empty_like(x)
        i, n = 0, len(x)
        while i < n:
            m = min(self.d - self.pos, n - i)
            o = self.buf[self.pos:self.pos + m].copy()
            out[i:i + m] = o - x[i:i + m]
            self.buf[self.pos:self.pos + m] = x[i:i + m] + o * 0.5
            self.pos = (self.pos + m) % self.d
            i += m
        return out


class ReverbEffect(Effect):
    name = "reverb"
    label = "Reverb"
    primary = "mix"
    params = (
        Param("room", "Room", 0, 100, 5, 50, "%"),
        Param("damping", "Damping", 0, 100, 5, 40, "%"),
        Param("mix", "Mix", 0, 100, 5, 25, "%"),
    )

    def reset(self):
        k = self.sample_rate / 44100.0
        self._combs = [_Comb(int(d * k)) for d in COMBS]
        self._aps = [_Allpass(int(d * k)) for d in ALLPASS]

    def _process(self, x):
        v = self.values
        fb = 0.70 + 0.28 * v["room"] / 100.0
        damp = 0.05 + 0.85 * v["damping"] / 100.0
        inp = x * np.float32(0.015)
        wet = np.zeros_like(x)
        for c in self._combs:
            wet += c.process(inp, fb, damp)
        for a in self._aps:
            wet = a.process(wet)
        m = v["mix"] / 100.0
        return (x * (1 - m) + wet * np.float32(3.0 * m)).astype(np.float32)
