#!/usr/bin/env python3
"""FM discriminator demod for lab-04 style captures."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAB04 = ROOT / "labs" / "04-gpu-display-fm"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(LAB04))

from common.iq import load_iq  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("--fs", type=float, default=None)
    args = ap.parse_args()

    from receiver import receive_fm

    iq, meta = load_iq(args.input)
    fs = args.fs or float(meta.get("fs", 1.024e6))
    ok, body, st = receive_fm(iq, fs=fs)
    print(f"ok={ok} payload={body!r} stats={st}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
