"""Microphone capture. Delivers mono float32 blocks to a callback."""
from __future__ import annotations

import numpy as np

from .devices import DeviceInfo, _sd, wasapi_settings


class MicCapture:
    def __init__(self, on_block):
        self.on_block = on_block
        self.stream = None
        self.info = None
        self.channels = 0
        self.status_events = 0
        self.last_status = ""

    def _cb(self, indata, frames, time_info, status):
        if status:
            self.status_events += 1
            self.last_status = str(status)
        mono = indata[:, 0] if indata.shape[1] == 1 else indata.mean(axis=1)
        self.on_block(np.ascontiguousarray(mono, dtype=np.float32))

    def start(self, info: DeviceInfo, sample_rate: int, block: int) -> None:
        sd = _sd()
        extra = wasapi_settings(info.hostapi)
        last = None
        for channels in dict.fromkeys((1, min(2, max(1, info.max_input)))):
            try:
                self.stream = sd.InputStream(
                    device=info.index, channels=channels, samplerate=sample_rate, blocksize=block,
                    dtype="float32", latency="low", extra_settings=extra, callback=self._cb)
                self.stream.start()
                self.info, self.channels = info, channels
                return
            except Exception as e:  # noqa: BLE001
                last = e
                self.stream = None
        raise RuntimeError(f"cannot open microphone '{info.name}': {last}")

    def stop(self) -> None:
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            finally:
                self.stream = None
