import numpy as np
import pytest

from audio.processor import VoiceProcessor
from effects import build_chain

SR = 48000


def tone(freq, seconds=1.0, amp=0.5):
    t = np.arange(int(SR * seconds)) / SR
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def run_blocks(fx, x, block=480):
    return np.concatenate([fx.process(x[i:i + block]) for i in range(0, len(x), block)])


def dom_freq(x):
    x = x[SR // 4:]
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    return np.argmax(spec) * SR / len(x)


def fx(name):
    f = next(e for e in build_chain(SR) if e.name == name)
    f.set_enabled(True)
    return f


@pytest.mark.parametrize("st", [-12, -5, 4, 7, 12])
def test_pitch_shifts_without_changing_length(st):
    p = fx("pitch"); p.set("semitones", st)
    y = run_blocks(p, tone(440, 1.5))
    assert len(y) == SR * 3 // 2
    expected = 440 * 2 ** (st / 12)
    assert abs(dom_freq(y) - expected) / expected < 0.03


def test_pitch_zero_is_bypass():
    p = fx("pitch")
    x = tone(300, 0.1)
    assert np.array_equal(run_blocks(p, x), x)


def test_pitch_works_with_odd_and_large_blocks():
    p = fx("pitch"); p.set("semitones", 5)
    y = run_blocks(p, tone(440, 1.0), block=4096)
    assert abs(dom_freq(y) - 440 * 2 ** (5 / 12)) < 15
    y = run_blocks(p, tone(440, 0.5), block=137)
    assert np.isfinite(y).all()


def test_volume():
    v = fx("volume"); v.set("volume", 50)
    x = tone(440, 0.2)
    y = run_blocks(v, x)
    assert np.allclose(y[-1000:], x[-1000:] * 0.5, atol=1e-5)
    v.set("gain_db", 6)
    y = run_blocks(v, x)
    assert abs(np.abs(y[-1000:]).max() / np.abs(x[-1000:]).max() - 0.5 * 10 ** (6 / 20)) < 1e-3


def test_eq_bass_boost_and_cut():
    e = fx("eq"); e.set("bass_db", 12)
    low = run_blocks(e, tone(60, 0.5)); lowflat = tone(60, 0.5)
    assert np.abs(low[-4800:]).max() > 2.5 * np.abs(lowflat[-4800:]).max()
    e = fx("eq"); e.set("lowpass_hz", 1000)
    hi = run_blocks(e, tone(8000, 0.5))
    assert np.abs(hi[-4800:]).max() < 0.02


def test_distortion_clips_and_mix():
    d = fx("distortion"); d.set("drive_db", 30); d.set("level_db", 0)
    y = run_blocks(d, tone(200, 0.2, amp=0.5))
    assert np.abs(y).max() <= 1.0 and np.abs(y[-2000:]).max() > 0.9
    d.set("mix", 0)
    x = tone(200, 0.1)
    assert np.allclose(run_blocks(d, x), x, atol=1e-6)


def test_reverb_has_tail_and_is_stable():
    r = fx("reverb"); r.set("mix", 50)
    x = np.zeros(SR * 3, np.float32); x[:480] = 0.8
    y = run_blocks(r, x)
    assert np.isfinite(y).all() and np.abs(y).max() < 2
    assert np.abs(y[SR // 2:SR]).max() > 0.001          # tail after the impulse
    assert np.abs(y[-4800:]).max() < np.abs(y[SR // 2:SR]).max()  # decays


def test_echo_repeats_at_delay():
    e = fx("echo"); e.set("delay_ms", 100); e.set("mix", 100); e.set("feedback", 0)
    x = np.zeros(SR, np.float32); x[0] = 1.0
    y = run_blocks(e, x)
    assert abs(y[0] - 1) < 1e-6
    assert y[4800] > 0.99 and abs(y[2400]) < 1e-6


def test_effects_toggle_and_persist_roundtrip():
    vp = VoiceProcessor(SR)
    vp.effect("pitch").set("semitones", -5); vp.effect("pitch").set_enabled(True)
    d = vp.to_dict()
    vp2 = VoiceProcessor(SR); vp2.load_dict(d)
    assert vp2.effect("pitch").enabled and vp2.effect("pitch").get("semitones") == -5


def test_params_clamped():
    p = fx("pitch")
    assert p.set("semitones", 99) == 12


def test_full_chain_realtime_budget():
    import time
    vp = VoiceProcessor(SR)
    for e in vp.chain:
        e.set_enabled(True)
    vp.effect("pitch").set("semitones", 3)
    x = tone(220, 0.1)[:480]
    t = time.perf_counter()
    for _ in range(200):
        vp.process(x)
    per_block_ms = (time.perf_counter() - t) / 200 * 1000
    print("ms per 10ms block with ALL effects:", per_block_ms)
    assert per_block_ms < 5.0
