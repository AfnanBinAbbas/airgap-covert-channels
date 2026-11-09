#!/usr/bin/env python3
"""Simulate a leaky VGA/DVI emanation: pixel-clock carrier + OOK pattern sidebands."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from common.framing import encode_payload  # noqa: E402
from common.iq import save_iq  # noqa: E402
from common.modulation import add_preamble  # noqa: E402

# Lab VGA-ish clock
PIXEL_CLOCK_HZ = 25.175e6
FS = 2.048e6  # SDR rate IF after tuning near a harmonic
IF_OFFSET_HZ = 50e3  # how far we tune from the exact harmonic
SPS = 40


def pattern_bits(payload: bytes) -> np.ndarray:
    return add_preamble(encode_payload(payload, fec=True), n=40)


def synthesize_leak(bits: np.ndarray, fs: float = FS, if_off: float = IF_OFFSET_HZ,
                    sps: int = SPS, carrier_amp: float = 1.0,
                    snr_db: float | None = None, seed: int | None = None) -> np.ndarray:
    """Complex baseband at IF: OOK on a strong 'pixel clock harmonic' tone.
    Also add a weak comb of hsync-related tones for realism.
    """
    env = np.repeat(bits.astype(np.float64), sps)
    n = env.size
    t = np.arange(n) / fs
    # main leak tone at IF offset
    leak = carrier_amp * env * np.exp(1j * 2 * np.pi * if_off * t)
    # weak comb: 15.7 kHz-ish hsync side tones (scaled into IF)
    comb = 0.05 * np.exp(1j * 2 * np.pi * 15.7e3 * t) * (0.5 + 0.5 * env)
    x = leak + comb
    if snr_db is not None:
        from common.channel import awgn_channel

        x = awgn_channel(x.real, snr_db, seed=seed) + 1j * awgn_channel(
            x.imag, snr_db, seed=None if seed is None else seed + 1
        )
    return x.astype(np.complex64)


if __name__ == "__main__":
    msg = b"TEMPTEST-PATTERN-OK"
    bits = pattern_bits(msg)
    wave = synthesize_leak(bits, snr_db=18, seed=5)
    out = ROOT / "recordings" / "tempest_sim.c64"
    save_iq(out, wave, fs=FS, center_hz=PIXEL_CLOCK_HZ + IF_OFFSET_HZ,
            meta={"source": "tempest_sim", "pixel_clock": PIXEL_CLOCK_HZ, "payload": msg.decode()})
    print(f"bits={bits.size} wave={wave.size} → {out}")
