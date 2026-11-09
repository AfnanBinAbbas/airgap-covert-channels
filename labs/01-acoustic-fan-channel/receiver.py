"""Acoustic receiver: narrow bandpass, Goertzel tone energy, CRC decode.

Goertzel is a matched filter for a single known frequency, which rejects noise
outside each tone far better than a wide band around both tones.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.signal import butter, filtfilt

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.framing import decode_payload  # noqa: E402
from common.modulation import find_preamble  # noqa: E402

from emitter import FS, SPS, TONE0_HZ, TONE1_HZ, payload_to_bits  # noqa: E402


def bandpass(x: np.ndarray, fs: float, lo: float, hi: float, order: int = 4) -> np.ndarray:
    nyq = fs / 2
    lo_n = max(lo / nyq, 1e-4)
    hi_n = min(hi / nyq, 0.99)
    if lo_n >= hi_n:
        return x
    b, a = butter(order, [lo_n, hi_n], btype="band")
    return filtfilt(b, a, x)


def goertzel_power(seg: np.ndarray, freq: float, fs: float) -> float:
    """Energy at `freq` for one symbol segment (vectorised correlation form)."""
    n = seg.size
    if n < 4:
        return 0.0
    t = np.arange(n) / fs
    ref = np.exp(-1j * 2 * np.pi * freq * t)
    c = np.dot(seg.astype(np.complex128), ref)
    return float((c.real ** 2 + c.imag ** 2) / n)


def _tone_pair_filters(fs: float, f0: float, f1: float, half_bw: float = 40.0):
    """Narrow bandpass centred on each tone (rejects between-tone noise)."""
    def _bp(fc: float):
        lo, hi = fc - half_bw, fc + half_bw
        nyq = fs / 2
        lo_n = max(lo / nyq, 1e-4)
        hi_n = min(hi / nyq, 0.99)
        if lo_n >= hi_n:
            return None, None
        b, a = butter(3, [lo_n, hi_n], btype="band")
        return b, a

    return _bp(f0), _bp(f1)


def _filtpad(x: np.ndarray, b, a, pad: int = 512) -> np.ndarray:
    """filtfilt with edge padding so the first/last bits are not corrupted."""
    if b is None:
        return x
    xp = np.pad(x, (pad, pad), mode="edge")
    yp = filtfilt(b, a, xp)
    return yp[pad : pad + x.size]


def demod_tones(wave: np.ndarray, fs: int = FS, sps: int = SPS,
                f0: float = TONE0_HZ, f1: float = TONE1_HZ) -> np.ndarray:
    """Per-tone narrowband matched energy → bits (vectorised)."""
    if wave.size < sps:
        return np.zeros(0, dtype=np.uint8)
    (b0, a0), (b1, a1) = _tone_pair_filters(fs, f0, f1)
    x0 = _filtpad(wave, b0, a0) if b0 is not None else wave
    x1 = _filtpad(wave, b1, a1) if b1 is not None else wave
    n_sym = min(x0.size, x1.size) // sps
    if n_sym == 0:
        return np.zeros(0, dtype=np.uint8)
    t = np.arange(sps) / fs
    r0 = np.sin(2 * np.pi * f0 * t)
    r1 = np.sin(2 * np.pi * f1 * t)
    segs0 = x0[: n_sym * sps].reshape(n_sym, sps)
    segs1 = x1[: n_sym * sps].reshape(n_sym, sps)
    e0 = np.abs(segs0 @ r0)
    e1 = np.abs(segs1 @ r1)
    return (e1 > e0).astype(np.uint8)


def estimate_snr_db(wave: np.ndarray, fs: int = FS,
                    f0: float = TONE0_HZ, f1: float = TONE1_HZ,
                    sps: int = SPS) -> float:
    """Rough in-band SNR: tone energy during active symbols vs quiet floor."""
    if wave.size < sps * 8:
        return -99.0
    (b0, a0), _ = _tone_pair_filters(fs, f0, f1)
    x = filtfilt(b0, a0, wave) if b0 is not None else wave
    n_sym = x.size // sps
    # sample energy per symbol at f0 (works for both tones after dual filter mix)
    energies = []
    for i in range(0, n_sym, max(1, n_sym // 200)):
        seg = x[i * sps : (i + 1) * sps]
        energies.append(goertzel_power(seg, f0, fs) + goertzel_power(seg, f1, fs))
    if not energies:
        return -99.0
    energies = np.asarray(energies)
    # quiet floor = 20th percentile; signal = 80th percentile
    floor = float(np.percentile(energies, 20)) + 1e-18
    peak = float(np.percentile(energies, 80)) + 1e-18
    snr = float(10.0 * np.log10(peak / floor))
    return min(snr, 60.0)  # cap: silence floors otherwise report absurd SNR


def recover_frame(bits: np.ndarray, fec: bool = True, max_pre_err: int = 5) -> tuple[bool, bytes, dict]:
    pre = np.tile(np.array([1, 0], dtype=np.uint8), 16)
    idx = _find_pre(bits, pre, max_pre_err)
    if idx < 0:
        idx = _find_pre(1 - bits, pre, max_pre_err)
        if idx >= 0:
            bits = 1 - bits
    if idx < 0:
        return False, b"", {"error": "no preamble"}
    payload_bits = bits[idx + pre.size :]
    return decode_payload(payload_bits, fec=fec)


def _find_pre(bits: np.ndarray, pre: np.ndarray, max_err: int) -> int:
    """Preamble search allowing up to max_err bit errors."""
    w = bits.astype(np.uint8)
    p = pre.astype(np.uint8)
    if w.size < p.size:
        return -1
    best_i, best_e = -1, max_err + 1
    for i in range(0, w.size - p.size + 1):
        e = int(np.count_nonzero(w[i : i + p.size] != p))
        if e < best_e:
            best_e, best_i = e, i
            if e == 0:
                break
    return best_i if best_e <= max_err else -1


def receive_file(path: str | Path, fec: bool = True) -> tuple[bool, bytes, dict]:
    """Read WAV or raw float64 mono."""
    path = Path(path)
    if path.suffix.lower() == ".wav":
        import wave

        with wave.open(str(path), "rb") as w:
            fs = w.getframerate()
            n = w.getnframes()
            raw = w.readframes(n)
            sw = w.getsampwidth()
        if sw == 2:
            data = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
        elif sw == 4:
            data = np.frombuffer(raw, dtype=np.int32).astype(np.float64) / 2147483648.0
        else:
            raise ValueError(f"unsupported sampwidth {sw}")
    else:
        data = np.fromfile(path, dtype=np.float64)
        fs = FS
    if fs != FS and data.size:
        ratio = FS / fs
        n_out = int(data.size * ratio)
        data = np.interp(np.linspace(0, data.size - 1, n_out), np.arange(data.size), data)
    bits = demod_tones(data, fs=FS, sps=SPS)
    return recover_frame(bits, fec=fec)


if __name__ == "__main__":
    from emitter import bits_to_tone_wave
    from channel_sim import acoustic_channel

    msg = b"HELLO-FAN-CHANNEL"
    bits = payload_to_bits(msg)
    tx = bits_to_tone_wave(bits)
    rx = acoustic_channel(tx, FS, snr_db=18, seed=42)
    b = demod_tones(rx)
    ok, body, stats = recover_frame(b)
    snr = estimate_snr_db(rx)
    print(f"ok={ok} body={body!r} snr={snr:.1f} dB stats={stats}")
