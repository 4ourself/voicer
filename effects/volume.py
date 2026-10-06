import numpy as np

from .base import Effect, Param


class VolumeEffect(Effect):
    name = "volume"
    label = "Volume / Gain"
    default_enabled = True
    primary = "volume"
    params = (
        Param("volume", "Volume", 0, 200, 5, 100, "%"),
        Param("gain_db", "Gain", -24, 24, 1, 0, " dB"),
    )

    def reset(self):
        self._last = None

    def _target(self) -> float:
        return self.values["volume"] / 100.0 * 10 ** (self.values["gain_db"] / 20.0)

    def _process(self, x):
        g = self._target()
        last = self._last if self._last is not None else g
        self._last = g
        if abs(g - last) > 1e-6:  # ramp to avoid zipper noise
            ramp = np.linspace(last, g, len(x), dtype=np.float32)
            return x * ramp
        if abs(g - 1.0) < 1e-6:
            return x
        return x * np.float32(g)
