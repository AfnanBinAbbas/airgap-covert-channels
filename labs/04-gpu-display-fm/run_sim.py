#!/usr/bin/env python3
"""Lab 04 end-to-end: AirHopper-class FM covert channel BER sweep."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(LAB))

from common.metrics import save_result  # noqa: E402

from channel_sim import fm_channel  # noqa: E402
from emitter import FS, fm_modulate_bits, payload_to_bits  # noqa: E402
from receiver import receive_fm  # noqa: E402


def run_once(msg: bytes, snr_db: float, cfo_hz: float, seed: int) -> dict:
    bits = payload_to_bits(msg, fec=True)
    tx = fm_modulate_bits(bits, fs=FS)
    rx = fm_channel(tx, FS, snr_db=snr_db, cfo_hz=cfo_hz, seed=seed)
    ok, body, stats = receive_fm(rx, fs=FS)
    return {"snr_db": snr_db, "cfo_hz": cfo_hz, "ok": ok,
            "payload": body.decode("utf-8", "replace") if ok else None,
            "stats": stats}


def main() -> None:
    msg = b"AIRHOPPER-FM-LAB-PING-04"
    print(f"[*] Lab 04 GPU/display FM covert channel, with payload={msg!r}")
    snrs = [25, 20, 15, 10, 5]
    cfos = [0.0, 500.0, -800.0]
    results = []
    for snr in snrs:
        for cfo in cfos:
            oks = [run_once(msg, snr, cfo, seed=4000 + snr * 11 + int(cfo) + t)["ok"]
                   for t in range(3)]
            row = {"snr_db": snr, "cfo_hz": cfo, "decode_success_rate": float(np.mean(oks))}
            results.append(row)
            print(f"  SNR={snr:2d} CFO={cfo:+.0f} Hz  success={row['decode_success_rate']:.0%}")

    final = run_once(msg, snr_db=20, cfo_hz=300.0, seed=42)
    print(f"[+] final snr=20 cfo=300 ok={final['ok']} payload={final['payload']!r}")
    save_result("04-gpu-display-fm",
                {"payload": msg.decode(), "sweep": results, "final": final,
                 "pass": bool(final["ok"]) or any(r["decode_success_rate"] > 0 for r in results)},
                out_dir=str(ROOT / "results"))
    ok = final["ok"] or any(r["decode_success_rate"] > 0 for r in results)
    print(f"[{'PASS' if ok else 'FAIL'}] FM covert channel")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
