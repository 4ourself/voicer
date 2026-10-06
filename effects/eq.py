"""3-band EQ (RBJ biquads) + optional high-pass / low-pass filters."""
import math

import numpy as np
from scipy.signal import sosfilt

from .base import Effect, Param


def _norm(b0, b1, b2, a0, a1, a2):
    return [b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0]


def low_shelf(f0, gain_db, sr, S=1.0):
    A = 10 ** (gain_db / 40)
    w = 2 * math.pi * f0 / sr
    c, s = math.cos(w), math.sin(w)
    al = s / 2 * math.sqrt((A + 1 / A) * (1 / S - 1) + 2)
    r = 2 * math.sqrt(A) * al
    return _norm(A * ((A + 1) - (A - 1) * c + r), 2 * A * ((A - 1) - (A + 1) * c),
                 A * ((A + 1) - (A - 1) * c - r), (A + 1) + (A - 1) * c + r,
                 -2 * ((A - 1) + (A + 1) * c), (A + 1) + (A - 1) * c - r)


def high_shelf(f0, gain_db, sr, S=1.0):
    A = 10 ** (gain_db / 40)
    w = 2 * math.pi * f0 / sr
    c, s = math.cos(w), math.sin(w)
    al = s / 2 * math.sqrt((A + 1 / A) * (1 / S - 1) + 2)
    r = 2 * math.sqrt(A) * al
    return _norm(A * ((A + 1) + (A - 1) * c + r), -2 * A * ((A - 1) + (A + 1) * c),
                 A * ((A + 1) + (A - 1) * c - r), (A + 1) - (A - 1) * c + r,
                 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - r)


def peaking(f0, gain_db, Q, sr):
    A = 10 ** (gain_db / 40)
    w = 2 * math.pi * f0 / sr
    c, al = math.cos(w), math.sin(w) / (2 * Q)
    return _norm(1 + al * A, -2 * c, 1 - al * A, 1 + al / A, -2 * c, 1 - al / A)


def lowpass(f0, sr, Q=0.7071):
    w = 2 * math.pi * f0 / sr
    c, al = math.cos(w), math.sin(w) / (2 * Q)
    return _norm((1 - c) / 2, 1 - c, (1 - c) / 2, 1 + al, -2 * c, 1 - al)


def highpass(f0, sr, Q=0.7071):
    w = 2 * math.pi * f0 / sr
    c, al = math.cos(w), math.sin(w) / (2 * Q)
    return _norm((1 + c) / 2, -(1 + c), (1 + c) / 2, 1 + al, -2 * c, 1 - al)


class EQEffect(Effect):
    name = "eq"
    label = "EQ / Filters"
    primary = "bass_db"
    params = (
        Param("bass_db", "Bass", -18, 18, 1, 0, " dB"),
        Param("mid_db", "Mid", -18, 18, 1, 0, " dB"),
        Param("treble_db", "Treble", -18, 18, 1, 0, " dB"),
        Param("highpass_hz", "High-pass", 0, 1000, 10, 0, " Hz"),
        Param("lowpass_hz", "Low-pass", 1000, 20000, 100, 20000, " Hz"),
    )

    def reset(self):
        self._sos = None
        self._zi = None
        self._dirty = True

    def _on_change(self, key):
        self._dirty = True

    def _rebuild(self):
        v, sr = self.values, self.sample_rate
        secs = []
        if v["highpass_hz"] >= 20:
            secs.append(highpass(v["highpass_hz"], sr))
        if v["bass_db"]:
            secs.append(low_shelf(120, v["bass_db"], sr))
        if v["mid_db"]:
            secs.append(peaking(1000, v["mid_db"], 0.8, sr))
        if v["treble_db"]:
            secs.append(high_shelf(5000, v["treble_db"], sr))
        if v["lowpass_hz"] < min(19999, sr * 0.45):
            secs.append(lowpass(v["lowpass_hz"], sr))
        old = None if self._sos is None else len(self._sos)
        self._sos = np.array(secs, dtype=np.float64) if secs else None
        if self._sos is None:
            self._zi = None
        elif old != len(self._sos) or self._zi is None:
            self._zi = np.zeros((len(self._sos), 2))
        self._dirty = False

    def _process(self, x):
        if self._dirty:
            self._rebuild()
        if self._sos is None:
            return x
        y, self._zi = sosfilt(self._sos, x, zi=self._zi)
        return y.astype(np.float32)
