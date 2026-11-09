#!/usr/bin/env python3
"""Record IQ from RTL-SDR or synthesize a capture for offline demod."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "labs" / "02-rf-mem-bus"))

from common.iq import save_iq  # noqa: E402


def capture_rtlsdr(freq: float, rate: float, seconds: float, gain: float,
                   out: Path, ppm: int = 0) -> np.ndarray:
    try:
        from rtlsdr import RtlSdr
    except ImportError as e:
        raise SystemExit("pyrtlsdr is not installed; use --simulate or run `pip3 install pyrtlsdr`") from e

    sdr = RtlSdr()
    sdr.sample_rate = rate
    sdr.center_freq = freq
    sdr.gain = gain
    if ppm:
        sdr.freq_correction = ppm
    n = int(rate * seconds)
    # read in chunks
    chunks = []
    left = n
    while left > 0:
        m = min(left, 262144)
        chunks.append(sdr.read_samples(m))
        left -= m
    sdr.close()
    iq = np.concatenate(chunks).astype(np.complex64)
    save_iq(out, iq, fs=rate, center_hz=freq, meta={"source": "rtlsdr", "gain": gain})
    print(f"[capture] {iq.size} samples → {out}")
    return iq


def simulate(mod: str, payload: bytes, out: Path, rate: float = 1.024e6,
             center: float = 100.2e6, snr_db: float = 15.0) -> np.ndarray:
    # reuse lab 02 emitter/channel
    from emitter import payload_to_bits, synthesize_bus_radiation
    from channel_sim import rf_channel

    bits = payload_to_bits(payload, fec=True)
    if mod == "fm":
        sys.path.insert(0, str(ROOT / "labs" / "04-gpu-display-fm"))
        from emitter import fm_modulate_bits  # type: ignore
        from channel_sim import fm_channel  # type: ignore

        tx = fm_modulate_bits(bits, fs=rate)
        rx = fm_channel(tx, rate, snr_db=snr_db, seed=1)
        center = 97.9e6
    else:
        tx = synthesize_bus_radiation(bits, mod=mod if mod in ("ask", "bpsk", "fsk") else "ask",
                                      fc=center, fs=rate)
        rx = rf_channel(tx, rate, snr_db=snr_db, seed=1)
    save_iq(out, rx, fs=rate, center_hz=center,
            meta={"source": "simulate", "mod": mod, "payload": payload.decode(), "snr_db": snr_db})
    print(f"[simulate] {rx.size} samples → {out}")
    return rx


def main() -> None:
    ap = argparse.ArgumentParser(description="IQ capture / simulate for air-gap labs")
    ap.add_argument("--freq", type=float, default=100.2e6, help="center frequency Hz")
    ap.add_argument("--rate", type=float, default=1.024e6, help="sample rate Hz")
    ap.add_argument("--seconds", type=float, default=3.0)
    ap.add_argument("--gain", type=float, default=30.0)
    ap.add_argument("--ppm", type=int, default=0)
    ap.add_argument("-o", "--out", type=Path, default=ROOT / "recordings" / "capture.c64")
    ap.add_argument("--simulate", action="store_true", help="synthetic capture instead of HW")
    ap.add_argument("--mod", default="ask", choices=["ask", "bpsk", "fsk", "fm"])
    ap.add_argument("--payload", default="SIM-CAPTURE-OK")
    args = ap.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.simulate:
        simulate(args.mod, args.payload.encode(), args.out, rate=args.rate, center=args.freq)
    else:
        capture_rtlsdr(args.freq, args.rate, args.seconds, args.gain, args.out, args.ppm)


if __name__ == "__main__":
    main()
