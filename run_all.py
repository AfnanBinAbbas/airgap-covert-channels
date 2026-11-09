#!/usr/bin/env python3
"""Run every lab simulation end-to-end. Exit non-zero if any FAIL."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent

LABS = [
    "labs/01-acoustic-fan-channel/run_sim.py",
    "labs/02-rf-mem-bus/run_sim.py",
    "labs/03-keyboard-emanations/run_sim.py",
    "labs/04-gpu-display-fm/run_sim.py",
    "labs/06-tempest-nearfield/analyze_leak.py",
]


def main() -> int:
    results = []
    for rel in LABS:
        path = ROOT / rel
        print("\n" + "=" * 70)
        print(f"RUN {rel}")
        print("=" * 70)
        t0 = time.time()
        p = subprocess.run([sys.executable, str(path)], cwd=str(ROOT))
        dt = time.time() - t0
        status = "PASS" if p.returncode == 0 else "FAIL"
        results.append((rel, status, p.returncode, dt))
        print(f"→ {status} in {dt:.1f}s")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    fails = 0
    for rel, status, rc, dt in results:
        print(f"  [{status:4s}] {rel}  ({dt:.1f}s)")
        if status != "PASS":
            fails += 1
    print(f"\n{len(results)-fails}/{len(results)} passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
