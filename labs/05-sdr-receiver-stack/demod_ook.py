#!/usr/bin/env python3
"""Generic OOK/ASK demod for a .c64 capture (lab 02-style)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAB02 = ROOT / "labs" / "02-rf-mem-bus"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(LAB02))

from common.iq import load_iq  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("--fc", type=float, default=None, help="override center Hz")
    ap.add_argument("--mod", default="ask", choices=["ask", "bpsk", "fsk"])
    args = ap.parse_args()

    from receiver import receive_iq

    iq, meta = load_iq(args.input)
    fs = float(meta.get("fs", 1.024e6))
    fc = args.fc if args.fc is not None else float(meta.get("center_hz", 100.2e6))
    ok, body, st = receive_iq(iq, fs=fs, fc=fc, mod=args.mod)
    print(f"ok={ok} payload={body!r} stats={st}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
