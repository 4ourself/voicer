import numpy as np

from .base import Effect, Param


class DistortionEffect(Effect):
    name = "distortion"
    label = "Distortion"
    primary = "drive_db"
    params = (
        Param("drive_db", "Drive", 0, 40, 1, 12, " dB"),
        Param("level_db", "Level", -24, 6, 1, -8, " dB"),
        Param("mix", "Mix", 0, 100, 5, 100, "%"),
    )

    def _process(self, x):
        v = self.values
        wet = np.tanh(x * np.float32(10 ** (v["drive_db"] / 20))) * np.float32(10 ** (v["level_db"] / 20))
        m = np.float32(v["mix"] / 100.0)
        return x * (1 - m) + wet * m
