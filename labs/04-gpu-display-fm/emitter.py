"""AirHopper-class FM emitter: message bits → FM modulated RF (complex baseband)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.framing import encode_payload  # noqa: E402
from common.modulation import add_preamble  # noqa: E402

FM_CENTER_HZ = 97.9e6  # pick a clear lab frequency
FS = 1.024e6  # SDR rate
SPS = 64  # samples per bit at FS ≈ 16 kbps
DEV_HZ = 3.0e3  # FM deviation for the covert sub-message (kHz-scale)
PREEMPH_TAU = 50e-6  # standard FM deemphasis (applied at RX)


def payload_to_bits(payload: bytes, fec: bool = True) -> np.ndarray:
    return add_preamble(encode_payload(payload, fec=fec), n=48)


def fm_modulate_bits(bits: np.ndarray, fs: float = FS, sps: int = SPS,
                     fc: float = 0.0, deviation: float = DEV_HZ) -> np.ndarray:
    """Complex baseband FM (fc=0 for easy sim) with per-bit frequency deviation."""
    freq = np.repeat(np.where(bits > 0.5, deviation, -deviation), sps)
    # small pilot tone offset so carrier isn't pure DC
    freq = freq + 200.0
    phase = 2 * np.pi * np.cumsum(freq) / fs
    return np.exp(1j * phase).astype(np.complex64)


def gpu_pattern_schedule(bits: np.ndarray, width: int = 1920, height: int = 1080):
    """Map bits → fullscreen fill colors for a lab GPU emitter.
    bit 1 → bright bar pattern (high memory traffic), bit 0 → dark / idle.
    """
    return [(width, height, (30, 30, 30) if b == 0 else (220, 220, 220)) for b in bits]


if __name__ == "__main__":
    msg = b"AIRHOPPER-FM-LAB"
    bits = payload_to_bits(msg)
    wave = fm_modulate_bits(bits)
    print(f"bits={bits.size} wave={wave.size} (~{wave.size/FS*1000:.1f} ms) dev={DEV_HZ} Hz")
