"""Deterministic lifecycle failures: no hardware or callback threads needed."""
import sys

import numpy as np
import pytest

from audio.capture import MicCapture
from audio.devices import DeviceInfo
from audio.engine import AudioEngine
from audio.output import OutputSink
from config import ConfigManager
from tests import fake_sd


class Stream:
    def __init__(self, *, start_error=False, stop_error=False, close_error=False, **kwargs):
        self.start_error = start_error
        self.stop_error = stop_error
        self.close_error = close_error
        self.closed = False

    def start(self):
        if self.start_error:
            raise RuntimeError("device disconnected during start")

    def stop(self):
        if self.stop_error:
            raise RuntimeError("device disconnected during stop")

    def close(self):
        self.closed = True
        if self.close_error:
            raise RuntimeError("device disconnected during close")


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)
    monkeypatch.setattr(fake_sd, "InputStream", Stream)
    monkeypatch.setattr(fake_sd, "OutputStream", Stream)
    cfg = ConfigManager(tmp_path / "config.json", autosave=False)
    eng = AudioEngine(cfg)
    monkeypatch.setattr(eng, "_start_watchdog", lambda: None)
    yield eng
    eng.stop()


@pytest.mark.parametrize("role", ["input", "output"])
def test_failed_start_closes_stream_before_retry(monkeypatch, role):
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)
    streams = []

    def open_stream(**kwargs):
        # A second channel-count attempt must not overlap the first handle.
        assert all(s.closed for s in streams)
        s = Stream(start_error=True)
        streams.append(s)
        return s

    monkeypatch.setattr(fake_sd, "InputStream" if role == "input" else "OutputStream", open_stream)
    info = DeviceInfo(0, "Disconnected device", "Fake API", 2, 2, 48000)
    sink = MicCapture(lambda block: None) if role == "input" else OutputSink(lambda frames: None)
    with pytest.raises(RuntimeError, match="cannot open"):
        sink.start(info, 48000, 480)
    assert streams and all(s.closed for s in streams)
    assert sink.stream is None


@pytest.mark.parametrize("role", ["input", "output"])
@pytest.mark.parametrize("stop_error,close_error", [(True, False), (False, True), (True, True)])
def test_stop_releases_disconnected_stream(role, stop_error, close_error):
    sink = MicCapture(lambda block: None) if role == "input" else OutputSink(lambda frames: None)
    stream = Stream(stop_error=stop_error, close_error=close_error)
    sink.stream = stream
    sink.stop()
    assert stream.closed
    assert sink.stream is None
    sink.stop()  # idempotent


def test_engine_stop_releases_every_role_after_one_device_fails(engine):
    assert engine.start() == []
    streams = [engine._sink(role).stream for role in ("output", "input", "monitor")]
    streams[0].stop_error = True
    engine.stop()
    assert all(s.closed for s in streams)
    assert not engine.running
    assert not engine.has_input and not engine.has_monitor


def test_restart_updates_effect_rate_and_preserves_live_settings(engine):
    assert engine.start() == []
    echo = engine.processor.effect("echo")
    echo.set("delay_ms", 100)
    echo.set("feedback", 0)
    echo.set("mix", 100)
    echo.set_enabled(True)
    engine.set_bypass(True)
    before = engine.processor.to_dict()
    engine.cfg.set("audio.sample_rate", 44100)
    assert engine.start() == []
    assert engine.processor.sample_rate == 44100
    assert all(e.sample_rate == 44100 for e in engine.processor.chain)
    assert engine.processor.to_dict() == before
    assert engine.processor.bypass
    # The actual echo must move to 100 ms at the new rate.
    impulse = np.zeros(8820, np.float32)
    impulse[0] = 0.5
    out = engine.processor.effect("echo").process(impulse)
    assert out[4410] == pytest.approx(0.5)
    assert out[4800] == 0
    assert engine._mic_ring.capacity == engine._mon_ring.capacity == 44100


def test_empty_backend_reports_unavailable_instead_of_crashing(engine, monkeypatch):
    monkeypatch.setattr(fake_sd, "query_hostapis", lambda: [])
    warnings = engine.start()
    assert not engine.running
    assert len(warnings) == 3
    assert all(h["state"] == "disconnected" for h in engine.health.values())
    level, message = engine.events.get_nowait()
    assert level == "error" and "audio" in message.lower()
