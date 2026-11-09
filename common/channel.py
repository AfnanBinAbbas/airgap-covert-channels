"""Synthetic covert channels: AWGN, multipath, fading, quantization, sample-rate mismatch."""

from __future__ import annotations

import numpy as np


def awgn_channel(x: np.ndarray, snr_db: float, fs: float | None = None, seed: int | None = None) -> np.ndarray:
    """Add white Gaussian noise for a target SNR (dB) relative to signal power."""
    rng = np.random.default_rng(seed)
    x = np.asarray(x, dtype=np.float64)
    p_sig = np.mean(x**2) if x.size else 1.0
    if p_sig <= 0:
        p_sig = 1.0
    p_noise = p_sig / (10 ** (snr_db / 10))
    noise = rng.normal(0.0, np.sqrt(p_noise), size=x.shape)
    return x + noise


def apply_gain(x: np.ndarray, gain_db: float) -> np.ndarray:
    return np.asarray(x, dtype=np.float64) * (10 ** (gain_db / 20))


def multipath_channel(x: np.ndarray, delays_s: list[float], gains: list[float], fs: float,
                      seed: int | None = None) -> np.ndarray:
    """Simple tapped-delay-line multipath."""
    y = np.zeros_like(x, dtype=np.float64)
    for d, g in zip(delays_s, gains):
        tap = int(round(d * fs))
        if tap == 0:
            y += g * x
        elif tap > 0 and tap < len(x):
            y[tap:] += g * x[:-tap]
    return y


def fading_channel(x: np.ndarray, doppler_hz: float, fs: float, seed: int | None = None) -> np.ndarray:
    """Flat Rayleigh-ish fading via complex baseband envelope (applied to real x)."""
    rng = np.random.default_rng(seed)
    n = x.size
    t = np.arange(n) / fs
    # two gaussian processes lowpassed roughly by doppler
    def lowpass_noise():
        w = rng.normal(0, 1, n)
        # crude 1-pole LPF with cutoff ~ doppler
        a = np.exp(-2 * np.pi * doppler_hz / fs) if fs > 0 else 0.9
        y = np.zeros(n)
        acc = 0.0
        for i in range(n):
            acc = a * acc + (1 - a) * w[i]
            y[i] = acc
        return y
    i = lowpass_noise()
    q = lowpass_noise()
    env = np.sqrt(i**2 + q**2)
    env = env / (np.mean(env) + 1e-12)
    return x * env


def quantize(x: np.ndarray, bits: int) -> np.ndarray:
    """Uniform quantize to `bits` bits (models cheap ADC / SDR front-end)."""
    if bits >= 24:
        return x
    lo, hi = np.min(x), np.max(x)
    if hi <= lo:
        return x
    levels = 2**bits
    step = (hi - lo) / levels
    q = np.round((x - lo) / step) * step + lo
    return q


def resample_linear(x: np.ndarray, ratio: float) -> np.ndarray:
    """Linear resample by ratio (fs_out/fs_in). Models clock skew between boxes."""
    if ratio == 1.0 or x.size < 2:
        return x.copy()
    n_out = int(round(x.size * ratio))
    t_in = np.arange(x.size)
    t_out = np.arange(n_out) / ratio
    return np.interp(t_out, t_in, x)


def covert_channel_sim(bits: np.ndarray, mod: str = "bpsk", snr_db: float = 10.0,
                       sps: int = 8, fs: float = 48000.0, fc: float | None = None,
                       seed: int | None = None, multipath: bool = False,
                       fade: bool = False, quant_bits: int | None = None,
                       clock_skew: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """Full sim: modulate -> channel -> return (rx_wave, tx_bits).
    Caller demodulates with matching demod function."""
    from . import modulation as M

    if fc is None:
        fc = fs / 8
    if mod == "bpsk":
        tx = M.bpsk_mod(bits, sps, fc, fs)
        demod = lambda w: M.bpsk_demod(w, sps, fc, fs)
    elif mod == "fsk":
        f0, f1 = fc * 0.8, fc * 1.25
        tx = M.fsk_mod(bits, sps, f0, f1, fs)
        demod = lambda w: M.fsk_demod(w, sps, f0, f1, fs)
    elif mod == "ask":
        tx = M.ask_mod(bits, sps, fc, fs)
        demod = lambda w: M.ask_demod(w, sps, fc, fs)
    else:
        raise ValueError(f"unknown mod {mod}")

    if multipath:
        tx = multipath_channel(tx, [0, 1.5 / fc], [1.0, 0.4], fs, seed=seed)
    if fade:
        tx = fading_channel(tx, doppler_hz=2.0, fs=fs, seed=seed)
    rx = awgn_channel(tx, snr_db, seed=seed)
    if quant_bits is not None:
        rx = quantize(rx, quant_bits)
    if clock_skew != 1.0:
        rx = resample_linear(rx, clock_skew)
    # stash demod on array attr is ugly; return via closure in caller instead
    return rx, bits


def ber(a: np.ndarray, b: np.ndarray) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 1.0
    return float(np.mean(a[:n] != b[:n]))
