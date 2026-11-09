"""Metrics + result writing helpers."""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np


def ber(a, b) -> float:
    a = np.asarray(a).ravel()
    b = np.asarray(b).ravel()
    n = min(a.size, b.size)
    if n == 0:
        return 1.0
    return float(np.mean(a[:n] != b[:n]))


def save_result(lab: str, payload: dict, out_dir: str | Path = "results") -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = out / f"{lab}_{ts}.json"
    payload = {"lab": lab, "timestamp": ts, **payload}
    path.write_text(json.dumps(payload, indent=2, default=str))
    print(f"[results] wrote {path}")
    return path
