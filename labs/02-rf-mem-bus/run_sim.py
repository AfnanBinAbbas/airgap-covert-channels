#!/usr/bin/env python3
"""Lab 02 end-to-end: memory-bus RF covert channel BER sweep (sim)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(LAB))

from common.metrics import save_result  # noqa: E402

from channel_sim import rf_channel  # noqa: E402
from emitter import FC_HZ, FS, payload_to_bits, synthesize_bus_radiation  # noqa: E402
from receiver import receive_iq  # noqa: E402


def run_once(msg: bytes, snr_db: float, mod: str, seed: int) -> dict:
    bits = payload_to_bits(msg, fec=True)
    tx = synthesize_bus_radiation(bits, mod=mod, fc=FC_HZ, fs=FS)
    rx = rf_channel(tx, FS, snr_db=snr_db, seed=seed)
    ok, body, stats = receive_iq(rx, fs=FS, fc=FC_HZ, mod=mod)
    return {"snr_db": snr_db, "mod": mod, "ok": ok,
            "payload": body.decode("utf-8", "replace") if ok else None,
            "stats": stats}


def main() -> None:
    msg = b"MEMBUS-RF-LAB-PING-02"
    print(f"[*] Lab 02 RF memory-bus covert channel, with payload={msg!r}")
    mods = ["ask", "bpsk"]
    snrs = [20, 15, 10, 5, 0]
    trials = 4
    results = []
    for mod in mods:
        for snr in snrs:
            oks = []
            for t in range(trials):
                r = run_once(msg, snr, mod, seed=2000 + snr * 7 + t + (0 if mod == "ask" else 500))
                oks.append(r["ok"])
            row = {"mod": mod, "snr_db": snr, "decode_success_rate": float(np.mean(oks))}
            results.append(row)
            print(f"  {mod.upper():4s} SNR={snr:2d} dB  success={row['decode_success_rate']:.0%}")

    # final demo at a comfortable SNR
    final = run_once(msg, snr_db=15, mod="ask", seed=42)
    print(f"[+] final ask@15dB ok={final['ok']} payload={final['payload']!r}")
    save_result("02-rf-mem-bus",
                {"payload": msg.decode(), "sweep": results, "final": final,
                 "pass": bool(final["ok"]) or any(r["decode_success_rate"] > 0 for r in results)},
                out_dir=str(ROOT / "results"))
    ok = final["ok"] or any(r["decode_success_rate"] > 0 for r in results)
    print(f"[{'PASS' if ok else 'FAIL'}] RF mem-bus lab")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
