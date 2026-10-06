"""Built-in voice presets (data only). A preset = {effect_name: {"enabled": bool, "params": {...}}}.
Applying a preset resets every effect to defaults first, then overlays the preset."""


def _p(**effects):
    return {name: {"enabled": True, "params": params} for name, params in effects.items()}


BUILTIN = {
    "Normal": {},
    "Deep Voice": _p(pitch={"semitones": -5}, eq={"bass_db": 6, "treble_db": -2}),
    "High Voice": _p(pitch={"semitones": 5}, eq={"treble_db": 3}),
    "Chipmunk": _p(pitch={"semitones": 9}),
    "Radio": _p(eq={"highpass_hz": 400, "lowpass_hz": 3400, "mid_db": 4},
                distortion={"drive_db": 8, "level_db": -4, "mix": 35}),
    "Robot": _p(pitch={"semitones": -2}, distortion={"drive_db": 10, "level_db": -6, "mix": 40},
                echo={"delay_ms": 50, "feedback": 60, "mix": 45}),
    "Distorted": _p(distortion={"drive_db": 28, "level_db": -10, "mix": 100}),
    "Cave": _p(reverb={"room": 85, "damping": 30, "mix": 45}, echo={"delay_ms": 250, "feedback": 40, "mix": 25}),
    "Demon": _p(pitch={"semitones": -9}, distortion={"drive_db": 18, "level_db": -8, "mix": 60},
                reverb={"room": 60, "damping": 50, "mix": 20}),
}


def apply_preset(processor, spec: dict) -> None:
    for e in processor.chain:
        e.reset_params()
        e.set_enabled(e.name == "volume")      # volume is the always-on base stage
        if e.name in spec:
            e.load_dict(spec[e.name])
