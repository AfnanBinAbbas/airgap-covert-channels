"""Memory-bus RF receiver: downconvert → correlate → bits → FEC decode."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.framing import decode_payload  # noqa: E402
from common.modulation import find_preamble  # noqa: E402

from emitter import FC_HZ, FS, SPS  # noqa: E402


def downconvert_to_env(iq: np.ndarray, fc: float, fs: float) -> np.ndarray:
    n = np.arange(iq.size)
    return iq * np.exp(-1j * 2 * np.pi * fc * n / fs)


def demod_ask_complex(env: np.ndarray, sps: int = SPS) -> np.ndarray:
    """Envelope of complex baseband OOK → bits (integrate per symbol)."""
    mag = np.abs(env)
    n_sym = mag.size // sps
    if n_sym == 0:
        return np.zeros(0, dtype=np.uint8)
    soft = mag[: n_sym * sps].reshape(n_sym, sps).mean(axis=1)
    thr = (soft.max() + soft.min()) / 2 if soft.size else 0.0
    return (soft > thr).astype(np.uint8)


def demod_bpsk_complex(env: np.ndarray, sps: int = SPS) -> np.ndarray:
    soft = env[: env.size // sps * sps].reshape(-1, sps).mean(axis=1)
    # baseband BPSK constellation is ±real; use I directly (small residual
    # phase noise does not flip sign for SNR > ~0 dB)
    return (soft.real > 0).astype(np.uint8)


def demod_fsk_complex(env: np.ndarray, sps: int, fs: float) -> np.ndarray:
    """Per-symbol frequency discriminator FSK (unwrap-safe)."""
    if env.size < sps * 2:
        return np.zeros(0, dtype=np.uint8)
    ph = np.unwrap(np.angle(env))
    d = np.diff(ph, prepend=ph[0]) * fs / (2 * np.pi)
    n_sym = d.size // sps
    soft = d[: n_sym * sps].reshape(n_sym, sps).mean(axis=1)
    thr = (float(soft.max()) + float(soft.min())) / 2 if soft.size else 0.0
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


def receive_iq(iq: np.ndarray, fs: float = FS, fc: float = FC_HZ, mod: str = "ask",
               fec: bool = True) -> tuple[bool, bytes, dict]:
    env = downconvert_to_env(iq.astype(np.complex128), fc, fs)
    if mod == "ask":
        bits = demod_ask_complex(env, SPS)
    elif mod == "bpsk":
        bits = demod_bpsk_complex(env, SPS)
    elif mod == "fsk":
        bits = demod_fsk_complex(env, SPS, fs)
    else:
        raise ValueError(mod)
    ok, body, stats = recover_frame(bits, fec=fec)
    stats.update({"mod": mod, "n_rx_bits": int(bits.size)})
    return ok, body, stats


if __name__ == "__main__":
    from emitter import payload_to_bits, synthesize_bus_radiation
    from channel_sim import rf_channel

    msg = b"MEMBUS-DECODE-OK"
    bits = payload_to_bits(msg)
    tx = synthesize_bus_radiation(bits, mod="ask")
    rx = rf_channel(tx, FS, snr_db=15, seed=7)
    ok, body, st = receive_iq(rx, mod="ask")
    print(f"ok={ok} body={body!r} {st}")
