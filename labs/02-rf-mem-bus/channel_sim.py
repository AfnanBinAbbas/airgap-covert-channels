"""RF channel for memory-bus sims: path loss, multipath, phase noise, quantization."""

from __future__ import annotations

import numpy as np

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.channel import awgn_channel, multipath_channel, quantize  # noqa: E402


def phase_noise(x: np.ndarray, fs: float, bandwidth_hz: float = 100.0,
                rms_rad: float = 0.05, seed: int | None = None) -> np.ndarray:
    """Lowpass phase noise with target total RMS phase error (bounded, not a free random walk)."""
    from scipy.signal import lfilter

    rng = np.random.default_rng(seed)
    n = x.size
    w = rng.normal(0, 1, n)
    # 1-pole LPF cutoff ≈ bandwidth_hz
    a = float(np.exp(-2 * np.pi * min(bandwidth_hz, fs / 2.5) / fs)) if fs > 0 else 0.99
    y = lfilter([1 - a], [1.0, -a], w)
    y = y / (float(np.std(y)) + 1e-15) * rms_rad
    return x * np.exp(1j * y)


def rf_channel(tx: np.ndarray, fs: float, snr_db: float = 12.0,
               path_loss_db: float = -40.0, multipath: bool = True,
               phase_noise_en: bool = True, quant_bits: int = 10,
               seed: int | None = None) -> np.ndarray:
    y = tx.astype(np.complex128) * (10 ** (path_loss_db / 20))
    if multipath:
        # apply real-tap multipath to I and Q separately
        taps_d = [0.0, 1.1e-6, 2.7e-6]
        taps_g = [1.0, 0.35, 0.18]
        yi = multipath_channel(y.real, taps_d, taps_g, fs, seed=seed)
        yq = multipath_channel(y.imag, taps_d, taps_g, fs, seed=seed)
        y = yi + 1j * yq
    if phase_noise_en:
        y = phase_noise(y, fs, seed=seed)
    # AWGN on complex (snr relative to post-pathloss power)
    y = awgn_channel(y.real, snr_db, seed=seed) + 1j * awgn_channel(y.imag, snr_db, seed=None if seed is None else seed + 1)
    # quantize I/Q
    if quant_bits is not None:
        # scale each component
        def q(c):
            m = np.max(np.abs(c)) + 1e-15
            return quantize(c / m, quant_bits) * m

        y = q(y.real) + 1j * q(y.imag)
    return y.astype(np.complex64)
