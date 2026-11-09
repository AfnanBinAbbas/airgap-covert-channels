"""Modulation / demodulation for covert channels (BPSK, BFSK, OOK/ASK, NRZ)."""

from __future__ import annotations

import numpy as np


def nrz_encode(bits: np.ndarray, sps: int) -> np.ndarray:
    """Return ±1 NRZ waveform at `sps` samples per bit."""
    bits = np.asarray(bits, dtype=np.float64)
    symbols = 2.0 * bits - 1.0
    return np.repeat(symbols, sps)


def nrz_decode(wave: np.ndarray, sps: int, threshold: float | None = None) -> np.ndarray:
    """Slice NRZ waveform back to bits (integrate-and-dump)."""
    n_sym = len(wave) // sps
    if n_sym == 0:
        return np.zeros(0, dtype=np.uint8)
    wave = wave[: n_sym * sps].reshape(n_sym, sps)
    soft = wave.mean(axis=1)
    if threshold is None:
        threshold = 0.0
    return (soft > threshold).astype(np.uint8)


def bpsk_mod(bits: np.ndarray, sps: int, fc: float, fs: float) -> np.ndarray:
    """BPSK: carrier phase 0 or pi per bit."""
    bits = np.asarray(bits, dtype=np.float64)
    n = bits.size * sps
    t = np.arange(n) / fs
    phase = np.repeat(2 * np.pi * fc * (np.arange(n) // sps) / 1.0, 1)
    # cleaner: phase per symbol index
    sym_idx = np.arange(n) // sps
    car = np.cos(2 * np.pi * fc * sym_idx / 1.0 * (1.0 / sps) * sps / sps)  # keep simple below
    # Use standard: carrier at fc, phase flipped per bit
    t = np.arange(n) / fs
    phases = np.pi * np.repeat(bits, sps)
    return np.cos(2 * np.pi * fc * t + phases)


def bpsk_demod(wave: np.ndarray, sps: int, fc: float, fs: float) -> np.ndarray:
    """Coherent BPSK demod with integrate-and-dump."""
    n_sym = len(wave) // sps
    if n_sym == 0:
        return np.zeros(0, dtype=np.uint8)
    t = np.arange(n_sym * sps) / fs
    ref = np.cos(2 * np.pi * fc * t)
    mixed = wave[: n_sym * sps] * ref
    soft = mixed.reshape(n_sym, sps).sum(axis=1)
    return (soft > 0).astype(np.uint8)


def fsk_mod(bits: np.ndarray, sps: int, f0: float, f1: float, fs: float) -> np.ndarray:
    """Binary FSK: f0 for 0, f1 for 1. Continuous phase."""
    bits = np.asarray(bits, dtype=np.float64)
    n = bits.size * sps
    freq = np.repeat(np.where(bits > 0.5, f1, f0), sps)
    phase = 2 * np.pi * np.cumsum(freq) / fs
    return np.cos(phase)


def fsk_demod(wave: np.ndarray, sps: int, f0: float, f1: float, fs: float) -> np.ndarray:
    """Non-coherent matched-filter FSK (correlate against both tones)."""
    n_sym = len(wave) // sps
    if n_sym == 0:
        return np.zeros(0, dtype=np.uint8)
    wave = wave[: n_sym * sps]
    t = np.arange(sps) / fs
    r0 = np.cos(2 * np.pi * f0 * t)
    r1 = np.cos(2 * np.pi * f1 * t)
    out = np.zeros(n_sym, dtype=np.uint8)
    for i in range(n_sym):
        seg = wave[i * sps : (i + 1) * sps]
        e0 = np.abs(np.dot(seg, r0))
        e1 = np.abs(np.dot(seg, r1))
        out[i] = 1 if e1 > e0 else 0
    return out


def ask_mod(bits: np.ndarray, sps: int, fc: float, fs: float, depth: float = 1.0) -> np.ndarray:
    """OOK / ASK: amplitude 1 for 1, (1-depth) for 0."""
    bits = np.asarray(bits, dtype=np.float64)
    n = bits.size * sps
    t = np.arange(n) / fs
    amp = np.repeat(1.0 - depth * (1.0 - bits), sps)
    return amp * np.cos(2 * np.pi * fc * t)


def ask_demod(wave: np.ndarray, sps: int, fc: float, fs: float, threshold: float | None = None) -> np.ndarray:
    """Envelope + threshold ASK demod."""
    n_sym = len(wave) // sps
    if n_sym == 0:
        return np.zeros(0, dtype=np.uint8)
    t = np.arange(n_sym * sps) / fs
    # quadrature demod envelope
    i = wave[: n_sym * sps] * np.cos(2 * np.pi * fc * t)
    q = wave[: n_sym * sps] * -np.sin(2 * np.pi * fc * t)
    env = np.sqrt(i.reshape(n_sym, sps).sum(axis=1) ** 2 + q.reshape(n_sym, sps).sum(axis=1) ** 2)
    if threshold is None:
        threshold = (env.max() + env.min()) / 2 if env.size else 0.0
    return (env > threshold).astype(np.uint8)


def add_preamble(bits: np.ndarray, n: int = 32) -> np.ndarray:
    """Alternating 1010... preamble for AGC / clock sync."""
    pre = np.tile(np.array([1, 0], dtype=np.uint8), (n + 1) // 2)[:n]
    return np.concatenate([pre, bits])


def find_preamble(wave_bits: np.ndarray, preamble: np.ndarray) -> int:
    """Return start index of preamble in bit stream, or -1."""
    p = preamble.astype(np.uint8)
    w = wave_bits.astype(np.uint8)
    for i in range(0, max(0, w.size - p.size + 1)):
        if np.array_equal(w[i : i + p.size], p):
            return i
    return -1
