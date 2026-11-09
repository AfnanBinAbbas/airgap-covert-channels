"""Fansmitter-class acoustic emitter: payload to keyed tone schedule (or fan PWM map).

Educational PoC for authorised lab use only.

Noise-robust defaults for live tests use 1000 / 2500 Hz so the tones sit above
typical room rumble and mains-related hum. Fan-RPM style 400 / 800 Hz remains
available via --tones or by passing f0/f1 into bits_to_tone_wave.
"""

from __future__ import annotations

import numpy as np

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.framing import encode_payload  # noqa: E402
from common.modulation import add_preamble  # noqa: E402


# Live defaults: well clear of HVAC / fridge / traffic energy
TONE0_HZ = 1000.0
TONE1_HZ = 2500.0
# Legacy fan-style pair (simulation / Fansmitter fidelity)
TONE0_FAN_HZ = 400.0
TONE1_FAN_HZ = 800.0
FS = 48000
SPS = 960  # 50 symbols/s; longer symbols tolerate room reverb and clock skew


def parse_tones(spec: str | None) -> tuple[float, float]:
    """Parse '1000,2500' or '400,800' into (f0, f1)."""
    if not spec:
        return TONE0_HZ, TONE1_HZ
    parts = [p.strip() for p in spec.split(",")]
    if len(parts) != 2:
        raise ValueError("tones must be 'f0,f1' in Hz, e.g. 1000,2500")
    f0, f1 = float(parts[0]), float(parts[1])
    if f0 <= 0 or f1 <= 0 or f0 == f1:
        raise ValueError("tones must be positive and different")
    if f1 < f0:
        f0, f1 = f1, f0
    return f0, f1


def payload_to_bits(payload: bytes, fec: bool = True) -> np.ndarray:
    bits = encode_payload(payload, fec=fec)
    return add_preamble(bits, n=32)


def bits_to_tone_wave(bits: np.ndarray, fs: int = FS, sps: int = SPS,
                      f0: float = TONE0_HZ, f1: float = TONE1_HZ) -> np.ndarray:
    """Two-tone keying (continuous phase) that models fan RPM jumping between setpoints."""
    n = bits.size * sps
    t = np.arange(n) / fs
    freq = np.repeat(np.where(bits > 0.5, f1, f0), sps)
    phase = 2 * np.pi * np.cumsum(freq) / fs
    amp = 0.9 + 0.1 * np.sin(2 * np.pi * 3.0 * t)
    return amp * np.sin(phase)


def calibration_wave(fs: int = FS, f0: float = TONE0_HZ, f1: float = TONE1_HZ,
                     tone_s: float = 0.35) -> np.ndarray:
    """Short burst of each tone so the receiver can confirm the pair is audible."""
    n = int(tone_s * fs)
    t = np.arange(n) / fs
    w0 = 0.85 * np.sin(2 * np.pi * f0 * t)
    w1 = 0.85 * np.sin(2 * np.pi * f1 * t)
    gap = np.zeros(int(0.1 * fs))
    return np.concatenate([w0, gap, w1])


def fan_pwm_schedule(bits: np.ndarray) -> list[tuple[float, float]]:
    """Map bits to [(duration_s, pwm_duty), ...] for a real lab fan controller.

    duty0/duty1 chosen so blade-pass frequency lands near the fan tone pair for a
    7-blade fan at about 1200/2200 RPM (placeholder; calibrate on your hardware).
    """
    bit_dur = SPS / FS
    duty = {0: 0.35, 1: 0.85}
    return [(bit_dur, float(duty[int(b)])) for b in bits]


if __name__ == "__main__":
    msg = b"AIRGAP-ACOUSTIC-LAB-PING"
    bits = payload_to_bits(msg)
    wave = bits_to_tone_wave(bits)
    print(f"payload={msg!r} bits={bits.size} wave_len={wave.size} (~{wave.size/FS:.2f}s)")
    print(f"tones={TONE0_HZ}/{TONE1_HZ} Hz  fs={FS}  sps={SPS}")
    print(f"pwm schedule entries: {len(fan_pwm_schedule(bits))}")
