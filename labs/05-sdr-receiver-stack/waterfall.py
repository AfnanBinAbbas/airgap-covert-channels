#!/usr/bin/env python3
"""Spectrogram plot of an IQ capture (or synthesize one for demo)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from common.iq import load_iq  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path, nargs="?", help=".c64 capture")
    ap.add_argument("-o", "--out", type=Path, default=ROOT / "results" / "waterfall.png")
    ap.add_argument("--fft", type=int, default=1024)
    ap.add_argument("--simulate", action="store_true")
    args = ap.parse_args()

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if args.input:
        iq, meta = load_iq(args.input)
        fs = float(meta.get("fs", 1.024e6))
        center = float(meta.get("center_hz", 0.0))
        title = f"{args.input.name}  fc={center/1e6:.3f} MHz"
    else:
        # synthesize: two carriers + noise
        fs, center = 1.024e6, 100.2e6
        n = 65536
        t = np.arange(n) / fs
        iq = (np.exp(1j * 2 * np.pi * 3e3 * t) * 0.5
              + np.exp(1j * 2 * np.pi * -12e3 * t) * 0.3
              + 0.05 * (np.random.randn(n) + 1j * np.random.randn(n)))
        iq = iq.astype(np.complex64)
        title = "simulated dual-carrier"

    if iq.size < args.fft:
        args.fft = max(64, 2 ** int(np.log2(iq.size // 2)))
    nper = args.fft
    nover = nper // 2
    freqs = np.fft.fftshift(np.fft.fftfreq(nper, 1 / fs)) / 1e3
    # manual STFT
    step = nper - nover
    starts = list(range(0, max(1, iq.size - nper), step))
    S = []
    for s in starts:
        seg = iq[s : s + nper] * np.hanning(nper)
        sp = np.fft.fftshift(np.fft.fft(seg))
        S.append(20 * np.log10(np.abs(sp) + 1e-15))
    S = np.array(S).T if S else np.zeros((nper, 1))
    fig, ax = plt.subplots(figsize=(10, 5))
    im = ax.imshow(S, origin="lower", aspect="auto",
                   extent=[0, iq.size / fs, freqs[0], freqs[-1]],
                   cmap="viridis")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("freq offset (kHz)")
    ax.set_title(title)
    fig.colorbar(im, label="dB")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(args.out, dpi=120)
    print(f"[plot] {args.out}")


if __name__ == "__main__":
    main()
