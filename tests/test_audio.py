"""End-to-end audio on the fake real-time backend: voice -> effects -> output / monitor."""
import sys
import time

import numpy as np
import pytest

from tests import fake_sd

SR = 48000


@pytest.fixture
def eng(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)
    monkeypatch.setenv("VOICER_DATA", str(tmp_path))
    from audio.engine import AudioEngine
    from config import ConfigManager
    cfg = ConfigManager(tmp_path / "config.json")
    cfg.set("audio.output_device", "Fake Cable")
    cfg.set("audio.monitor_device", "Fake Speakers")
    e = AudioEngine(cfg)
    assert e.start() == []
    yield e
    e.stop()


def _peaks(x):
    x = x[SR // 10: SR // 2]
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return sorted(f[np.argsort(spec)[-30:]])


def _grab(store, n0, seconds=0.8):
    time.sleep(seconds)
    return np.concatenate(store[n0:])[:, 0]


def test_voice_reaches_output_unchanged(eng):
    n0 = len(fake_sd.CAPTURED)
    out = _grab(fake_sd.CAPTURED, n0)
    assert any(abs(f - 300) < 20 for f in _peaks(out))          # fake mic is a 300 Hz tone


def test_pitch_shifts_voice_and_bypass_restores(eng):
    eng.processor.effect("pitch").set("semitones", -7)
    eng.processor.effect("pitch").set_enabled(True)
    time.sleep(0.3)
    n0 = len(fake_sd.CAPTURED)
    out = _grab(fake_sd.CAPTURED, n0)
    assert any(abs(f - 300 * 2 ** (-7 / 12)) < 25 for f in _peaks(out))
    eng.set_bypass(True)
    time.sleep(0.3)
    n0 = len(fake_sd.CAPTURED)
    out = _grab(fake_sd.CAPTURED, n0)
    assert any(abs(f - 300) < 20 for f in _peaks(out))


def test_hear_output_on_off_keeps_output_alive(eng):
    eng.set_hear_output(True)
    time.sleep(0.4)
    m0, o0 = len(fake_sd.MONITORED), len(fake_sd.CAPTURED)
    time.sleep(0.5)
    mon = np.concatenate(fake_sd.MONITORED[m0:])
    assert np.abs(mon).max() > 0.1                              # monitor hears the voice
    eng.set_hear_output(False)
    time.sleep(0.4)
    m1, o1 = len(fake_sd.MONITORED), len(fake_sd.CAPTURED)
    time.sleep(0.5)
    assert np.abs(np.concatenate(fake_sd.MONITORED[m1:])).max() < 1e-6      # monitor silent
    assert np.abs(np.concatenate(fake_sd.CAPTURED[o1:])).max() > 0.1        # output still carries the voice
    assert eng.stats()["underruns"] <= 3


def test_effect_param_change_does_not_restart_streams(eng):
    epoch = eng._epoch
    for v in range(-12, 13):
        eng.processor.effect("pitch").set("semitones", v)
    assert eng._epoch == epoch and eng.running
