"""GSMem-class memory-bus RF emitter (educational, authorized lab only).

Models: patterned memory traffic → narrowband radiation at a bus harmonic
(carrier ~100 MHz DDR fundamental or GSM uplink if coupled), OOK/FSK keying.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.framing import encode_payload  # noqa: E402
from common.modulation import add_preamble  # noqa: E402

# Default "found" harmonic for the sim (scan live to find yours)
FC_HZ = 100.2e6  # e.g. DDR-ish / clock harmonic region
FS = 2.048e6
SPS = 32  # samples/symbol → 64 ksym/s at FS


def payload_to_bits(payload: bytes, fec: bool = True) -> np.ndarray:
    return add_preamble(encode_payload(payload, fec=fec), n=48)


def synthesize_bus_radiation(bits: np.ndarray, mod: str = "ask",
                             fc: float = FC_HZ, fs: float = FS, sps: int = SPS,
                             snr_hint: float | None = None) -> np.ndarray:
    """Baseband-ish complex envelope at `fc` (passband real or complex).
    Returns complex64 at fs (for SDR-style processing).
    """
    # complex baseband modulation then upconvert
    if mod == "ask":
        # OOK envelope at baseband (complex), then upconverted below
        env = np.repeat(bits.astype(np.float64), sps)
        cb = env.astype(np.complex128)
    elif mod == "bpsk":
        # BPSK complex baseband: ±1 held for sps samples
        env = 2.0 * bits.astype(np.float64) - 1.0
        cb = np.repeat(env, sps).astype(np.complex128)
    elif mod == "fsk":
        f_dev = fs / (4 * sps)
        freq = np.repeat(np.where(bits > 0.5, f_dev, -f_dev), sps)
        phase = 2 * np.pi * np.cumsum(freq) / fs
        cb = np.exp(1j * phase)
    else:
        raise ValueError(mod)
    # upconvert to fc (keep complex passband for cheap SDR model)
    n = np.arange(cb.size)
    lo = np.exp(1j * 2 * np.pi * fc * n / fs)
    return (cb * lo).astype(np.complex64)


def memory_pattern_schedule(bits: np.ndarray) -> list[tuple[int, int]]:
    """Map bits -> [(n_pages, stride) ...] for live page-touch emitter.
    Bit 1: dense stride (high switching); bit 0: sparse / idle.
    """
    return [(64 if b else 4, 4096 if b else 1 << 20) for b in bits]


if __name__ == "__main__":
    msg = b"MEMBUS-RF-LAB-OK"
    bits = payload_to_bits(msg)
    wave = synthesize_bus_radiation(bits, mod="ask")
    print(f"bits={bits.size} wave={wave.size} complex64 (~{wave.size/FS*1000:.1f} ms)")
    print(f"live pattern entries={len(memory_pattern_schedule(bits))}")
