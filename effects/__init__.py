from .distortion import DistortionEffect
from .echo import EchoEffect
from .eq import EQEffect
from .pitch import PitchEffect
from .reverb import ReverbEffect
from .volume import VolumeEffect

# Pipeline order: Volume -> Pitch -> EQ -> Distortion -> Reverb -> Echo
EFFECT_CLASSES = (VolumeEffect, PitchEffect, EQEffect, DistortionEffect, ReverbEffect, EchoEffect)


def build_chain(sample_rate: int):
    return [cls(sample_rate) for cls in EFFECT_CLASSES]
