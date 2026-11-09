"""FM broadcast-channel simulation: AWGN, CFO, multipath, deemphasis at RX."""

from __future__ import annotations

import numpy as np

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.channel import awgn_channel, multipath_channel  # noqa: E402


def add_cfo(x: np.ndarray, fs: float, cfo_hz: float, seed: int | None = None) -> np.ndarray:
    n = np.arange(x.size)
    return x * np.exp(1j * 2 * np.pi * cfo_hz * n / fs)


def fm_channel(tx: np.ndarray, fs: float, snr_db: float = 15.0,
               cfo_hz: float = 0.0, multipath: bool = True,
               seed: int | None = None) -> np.ndarray:
    y = tx.astype(np.complex128)
    if multipath:
        yi = multipath_channel(y.real, [0, 2e-6], [1.0, 0.3], fs, seed=seed)
        yq = multipath_channel(y.imag, [0, 2e-6], [1.0, 0.3], fs, seed=seed)
        y = yi + 1j * yq
    if cfo_hz:
        y = add_cfo(y, fs, cfo_hz)
    y = awgn_channel(y.real, snr_db, seed=seed) + 1j * awgn_channel(
        y.imag, snr_db, seed=None if seed is None else seed + 3
    )
    return y.astype(np.complex64)


def fm_discriminator(iq: np.ndarray, fs: float) -> np.ndarray:
    """Instantaneous frequency estimate from complex IQ (unwrap before diff)."""
    phase = np.unwrap(np.angle(iq))
    d = np.diff(phase, prepend=phase[0])
    return d * fs / (2 * np.pi)
