"""Acoustic channel: speaker → room → mic (noise + mild reverb + AGC)."""

from __future__ import annotations

import numpy as np
from scipy.signal import fftconvolve

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.channel import awgn_channel  # noqa: E402


def room_reverb(x: np.ndarray, fs: float, rt60: float = 0.25, wet: float = 0.3,
                seed: int | None = None) -> np.ndarray:
    """Cheap exponential-decay reverb via FFT convolution."""
    rng = np.random.default_rng(seed)
    ir_len = int(min(rt60 * fs, 4096))  # cap IR for speed
    ir = np.zeros(ir_len)
    ir[0] = 1.0
    if ir_len > 1:
        decay = np.exp(-np.arange(1, ir_len) * (6.9 / max(rt60 * fs, 1)))
        ir[1:] = rng.normal(0, 1, ir_len - 1) * decay
    ir /= np.sqrt(np.sum(ir**2)) + 1e-12
    wet_sig = fftconvolve(x, ir)[: x.size]
    return (1 - wet) * x + wet * wet_sig


def mic_agc(x: np.ndarray, target_rms: float = 0.1, win: int = 2048) -> np.ndarray:
    """Slow block RMS AGC (models mic/amp automatic gain)."""
    x = np.asarray(x, dtype=np.float64)
    n = x.size
    if n < win:
        return x.copy()
    out = x.copy()
    step = max(win // 2, 1)
    for i in range(0, n - win + 1, step):
        seg = out[i : i + win]
        rms = float(np.sqrt(np.mean(seg**2))) + 1e-12
        g = target_rms / rms
        out[i : i + win] = seg * g
    return out


def acoustic_channel(tx: np.ndarray, fs: float, snr_db: float = 15.0,
                     distance_gain_db: float = -6.0, reverb: bool = True,
                     agc: bool = True, seed: int | None = None) -> np.ndarray:
    y = np.asarray(tx, dtype=np.float64) * (10 ** (distance_gain_db / 20))
    if reverb:
        # Mild room: enough colouration to stress the demod without drowning it
        y = room_reverb(y, fs, rt60=0.18, wet=0.15, seed=seed)
    y = awgn_channel(y, snr_db, seed=seed)
    if agc:
        y = mic_agc(y)
    return y
