"""FM receiver: discriminator → matched integrate → bits → FEC."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.signal import butter, filtfilt

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.framing import decode_payload  # noqa: E402
from common.modulation import find_preamble  # noqa: E402

from channel_sim import fm_discriminator  # noqa: E402
from emitter import DEV_HZ, FS, SPS  # noqa: E402


def lowpass(x: np.ndarray, fs: float, cutoff: float, order: int = 4) -> np.ndarray:
    nyq = fs / 2
    b, a = butter(order, min(cutoff / nyq, 0.99), btype="low")
    return filtfilt(b, a, x)


def demod_fm_bits(iq: np.ndarray, fs: float = FS, sps: int = SPS,
                  deviation: float = DEV_HZ) -> np.ndarray:
    freq = fm_discriminator(iq, fs)
    n_sym = freq.size // sps
    if n_sym == 0:
        return np.zeros(0, dtype=np.uint8)
    soft = freq[: n_sym * sps].reshape(n_sym, sps).mean(axis=1)
    # two-level threshold: midpoint of observed extremes is robust
    thr = (float(np.max(soft)) + float(np.min(soft))) / 2 if soft.size else 0.0
    return (soft > thr).astype(np.uint8)


def recover_frame(bits: np.ndarray, fec: bool = True) -> tuple[bool, bytes, dict]:
    pre = np.tile(np.array([1, 0], dtype=np.uint8), 24)
    idx = find_preamble(bits, pre)
    if idx < 0:
        idx = find_preamble(1 - bits, pre)
        if idx >= 0:
            bits = 1 - bits
    if idx < 0:
        return False, b"", {"error": "no preamble"}
    return decode_payload(bits[idx + pre.size :], fec=fec)


def receive_fm(iq: np.ndarray, fs: float = FS, fec: bool = True) -> tuple[bool, bytes, dict]:
    bits = demod_fm_bits(iq, fs=fs)
    ok, body, st = recover_frame(bits, fec=fec)
    st.update({"n_rx_bits": int(bits.size)})
    return ok, body, st


if __name__ == "__main__":
    from emitter import fm_modulate_bits, payload_to_bits
    from channel_sim import fm_channel

    msg = b"FM-DECODE-OK"
    bits = payload_to_bits(msg)
    tx = fm_modulate_bits(bits)
    rx = fm_channel(tx, FS, snr_db=18, seed=3)
    ok, body, st = receive_fm(rx)
    print(f"ok={ok} body={body!r} {st}")
