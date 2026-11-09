#!/usr/bin/env python3
"""Wideband peak scan (sim or RTL-SDR) to find candidate covert carriers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from common.iq import load_iq  # noqa: E402


def psd_peaks(x: np.ndarray, fs: float, center: float, n_peaks: int = 8,
              min_sep_bins: int = 5) -> list[tuple[float, float]]:
    """Return list of (freq_hz, power_db) peaks."""
    win = np.hanning(x.size)
    spec = np.fft.fftshift(np.fft.fft(x * win))
    freqs = np.fft.fftshift(np.fft.fftfreq(x.size, 1 / fs)) + center
    p = 20 * np.log10(np.abs(spec) + 1e-15)
    # smooth a little
    k = 9
    p_s = np.convolve(p, np.ones(k) / k, mode="same")
    peaks = []
    used = np.zeros(p_s.size, dtype=bool)
    order = np.argsort(p_s)[::-1]
    for i in order:
        if used[i]:
            continue
        lo = max(0, i - min_sep_bins)
        hi = min(p_s.size, i + min_sep_bins + 1)
        used[lo:hi] = True
        peaks.append((float(freqs[i]), float(p_s[i])))
        if len(peaks) >= n_peaks:
            break
    return peaks


def scan_from_file(path: Path, n_peaks: int) -> list[tuple[float, float]]:
    iq, meta = load_iq(path)
    fs = float(meta.get("fs", 1.024e6))
    center = float(meta.get("center_hz", 0.0))
    if iq.size == 0:
        return []
    # chunk average if huge
    if iq.size > 1 << 20:
        iq = iq[: 1 << 20]
    return psd_peaks(iq, fs, center, n_peaks=n_peaks)


def scan_rtlsdr(f0: float, f1: float, step: float, rate: float, dwell: float,
                gain: float, n_peaks: int) -> list[tuple[float, float]]:
    try:
        from rtlsdr import RtlSdr
    except ImportError as e:
        raise SystemExit("pyrtlsdr not installed") from e
    sdr = RtlSdr()
    sdr.sample_rate = rate
    sdr.gain = gain
    all_peaks = []
    freq = f0
    while freq <= f1:
        sdr.center_freq = freq
        n = int(rate * dwell)
        iq = sdr.read_samples(n)
        pk = psd_peaks(iq, rate, freq, n_peaks=n_peaks)
        all_peaks.extend(pk)
        print(f"  @{freq/1e6:.3f} MHz top: " + ", ".join(f"{f/1e6:.3f}({p:.0f}dB)" for f, p in pk[:3]))
        freq += step
    sdr.close()
    # dedupe sort by power
    all_peaks.sort(key=lambda t: -t[1])
    out, seen = [], set()
    for f, p in all_peaks:
        key = round(f / max(step / 2, 1))
        if key in seen:
            continue
        seen.add(key)
        out.append((f, p))
        if len(out) >= n_peaks:
            break
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, help="existing .c64 capture")
    ap.add_argument("--freq-start", type=float, default=88e6)
    ap.add_argument("--freq-stop", type=float, default=108e6)
    ap.add_argument("--step", type=float, default=100e3)
    ap.add_argument("--rate", type=float, default=1.024e6)
    ap.add_argument("--dwell", type=float, default=0.4)
    ap.add_argument("--gain", type=float, default=30.0)
    ap.add_argument("--peaks", type=int, default=8)
    args = ap.parse_args()

    if args.input:
        peaks = scan_from_file(args.input, args.peaks)
        src = str(args.input)
    else:
        print(f"[*] scanning {args.freq_start/1e6}–{args.freq_stop/1e6} MHz ...")
        peaks = scan_rtlsdr(args.freq_start, args.freq_stop, args.step,
                            args.rate, args.dwell, args.gain, args.peaks)
        src = "rtlsdr"

    print(f"[+] peaks from {src}:")
    for f, p in peaks:
        print(f"    {f/1e6:10.4f} MHz   {p:7.1f} dB")


if __name__ == "__main__":
    main()
