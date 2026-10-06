"""Live signal-path checks (pure function of engine state) used by the Help/Diagnostics page."""
from __future__ import annotations

from .devices import is_virtual


def verdict(engine) -> list[tuple[str, str]]:
    """[(level, message)] with level in ok | warn | bad. Explains where the signal stops."""
    out: list[tuple[str, str]] = []
    h = engine.health
    o, i, m = h["output"], h["input"], h["monitor"]
    if o["state"] != "ok":
        out.append(("bad", f"OUTPUT not open ({o['error'] or 'no device'}) - nothing reaches Discord."))
    else:
        if is_virtual(o["name"]):
            out.append(("ok", f"Output is a virtual device ({o['name']}). Discord input must be its recording side "
                              "(VB-Cable: 'CABLE Output')."))
        else:
            out.append(("bad", f"Output is '{o['name']}', a NORMAL device. Discord cannot hear it - select the "
                               "virtual cable ('CABLE Input') as Output."))
        if engine.out_level < 0.003 and engine.wave_out.recent_peak(300) < 0.003:
            out.append(("warn", "Output is silent right now (speak, or play a sound)."))
    if i["state"] != "ok":
        out.append(("bad", f"MICROPHONE not open ({i['error'] or 'no device'})."))
    else:
        peak = engine.wave_in.recent_peak(300)
        if is_virtual(i["name"]):
            out.append(("bad", f"Input '{i['name']}' is a virtual cable, not a microphone."))
        elif peak < 0.005:
            out.append(("warn", "Microphone is silent. Speak; else check mute / Windows microphone privacy."))
        else:
            out.append(("ok", "Microphone is delivering audio."))
    if engine.mixer.voice_volume == 0:
        out.append(("warn", "Mixer voice volume is 0% (Settings > Audio)."))
    if m["state"] == "disconnected":
        out.append(("warn", f"MONITOR not open ({m['error']})."))
    for name, err in engine.processor.errors.items():
        out.append(("bad", f"Effect '{name}' crashed and was disabled: {err}"))
    if engine.stats()["underruns"] > 5:
        out.append(("warn", "Buffer underruns detected - raise the audio buffer in Settings > Performance."))
    return out
