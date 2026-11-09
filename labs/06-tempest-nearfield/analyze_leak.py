#!/usr/bin/env python3
"""Analyze TEMPEST-style leak capture: find tone, demod OOK, CRC-decode pattern."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from common.framing import decode_payload  # noqa: E402
from common.iq import load_iq  # noqa: E402
from common.modulation import find_preamble  # noqa: E402


def find_strongest_offset(iq: np.ndarray, fs: float, search_hz: float = 200e3) -> float:
    """FFT peak frequency offset of strongest tone."""
    win = np.hanning(iq.size)
    spec = np.fft.fft(iq * win)
    freqs = np.fft.fftfreq(iq.size, 1 / fs)
    mag = np.abs(spec)
    # only search within ±search_hz
    mask = np.abs(freqs) <= search_hz
    if not np.any(mask):
        return float(freqs[np.argmax(mag)])
    idxs = np.where(mask)[0]
    best = idxs[np.argmax(mag[idxs])]
    return float(freqs[best])


def demod_ook_at(iq: np.ndarray, fs: float, offset_hz: float, sps: int) -> np.ndarray:
    n = np.arange(iq.size)
    base = iq * np.exp(-1j * 2 * np.pi * offset_hz * n / fs)
    mag = np.abs(base)
    n_sym = mag.size // sps
    soft = mag[: n_sym * sps].reshape(n_sym, sps).mean(axis=1)
    thr = (soft.max() + soft.min()) / 2 if soft.size else 0.0
    return (soft > thr).astype(np.uint8)


def recover(bits: np.ndarray, fec: bool = True) -> tuple[bool, bytes, dict]:
    pre = np.tile(np.array([1, 0], dtype=np.uint8), 20)
    idx = find_preamble(bits, pre)
    if idx < 0:
        idx = find_preamble(1 - bits, pre)
        if idx >= 0:
            bits = 1 - bits
    if idx < 0:
        return False, b"", {"error": "no preamble"}
    return decode_payload(bits[idx + pre.size :], fec=fec)


def analyze(iq: np.ndarray, fs: float, sps: int = 40) -> tuple[bool, bytes, dict]:
    off = find_strongest_offset(iq, fs)
    # refine around peak by trying sps neighborhood
    best = (False, b"", {"offset_hz": off})
    for s in (sps, sps // 2, sps * 2, max(8, sps - 8), sps + 8):
        if s < 4:
            continue
        bits = demod_ook_at(iq, fs, off, s)
        ok, body, st = recover(bits)
        st.update({"offset_hz": off, "sps": s, "n_bits": int(bits.size)})
        if ok:
            return True, body, st
        if st.get("error") != "no preamble":
            best = (ok, body, st)
    return best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path, nargs="?",
                    default=ROOT / "recordings" / "tempest_sim.c64")
    ap.add_argument("--sps", type=int, default=40)
    args = ap.parse_args()

    if not args.input.exists():
        # auto-simulate first
        print("[*] no capture, so generating a sim first")
        import subprocess

        subprocess.check_call([sys.executable, str(Path(__file__).with_name("simulate_leak.py"))])

    iq, meta = load_iq(args.input)
    fs = float(meta.get("fs", 2.048e6))
    print(f"[*] analyzing {args.input}  n={iq.size} fs={fs}")
    ok, body, st = analyze(iq, fs, sps=args.sps)
    print(f"ok={ok} payload={body!r} stats={st}")

    # also plot
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        win = np.hanning(min(iq.size, 65536))
        seg = iq[: win.size] * win
        freqs = np.fft.fftshift(np.fft.fftfreq(seg.size, 1 / fs)) / 1e3
        p = 20 * np.log10(np.abs(np.fft.fftshift(np.fft.fft(seg))) + 1e-15)
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.plot(freqs, p)
        ax.set_xlabel("offset (kHz)")
        ax.set_ylabel("dB")
        ax.set_title("TEMPEST sim spectrum")
        fig.tight_layout()
        out = ROOT / "results" / "tempest_spectrum.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=120)
        print(f"[plot] {out}")
    except Exception as e:
        print(f"[plot skipped] {e}")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
