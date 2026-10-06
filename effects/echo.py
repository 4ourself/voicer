import numpy as np

from .base import Effect, Param


class EchoEffect(Effect):
    name = "echo"
    label = "Echo"
    primary = "mix"
    params = (
        Param("delay_ms", "Delay", 50, 1000, 10, 300, " ms"),
        Param("feedback", "Feedback", 0, 90, 5, 35, "%"),
        Param("mix", "Mix", 0, 100, 5, 30, "%"),
    )

    def reset(self):
        self._size = int(1.1 * self.sample_rate)
        self._buf = np.zeros(self._size, np.float32)
        self._wp = 0

    def _process(self, x):
        v = self.values
        d = int(v["delay_ms"] / 1000 * self.sample_rate)
        fb = np.float32(v["feedback"] / 100.0)
        mix = np.float32(v["mix"] / 100.0)
        out = np.empty_like(x)
        i, n = 0, len(x)
        while i < n:
            m = min(d, n - i)  # chunk <= delay so reads only touch already-written samples
            ridx = (self._wp - d + np.arange(m)) % self._size
            widx = (self._wp + np.arange(m)) % self._size
            delayed = self._buf[ridx]
            self._buf[widx] = x[i:i + m] + delayed * fb
            out[i:i + m] = x[i:i + m] + delayed * mix
            self._wp = (self._wp + m) % self._size
            i += m
        return out
