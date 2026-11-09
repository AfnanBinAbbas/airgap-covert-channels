"""IQ file helpers (complex64 raw + simple header) for SDR captures."""

from __future__ import annotations

from pathlib import Path

import numpy as np


def save_iq(path: str | Path, iq: np.ndarray, fs: float, center_hz: float, meta: dict | None = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    iq = np.asarray(iq, dtype=np.complex64)
    # sidecar meta json
    import json

    m = {"fs": fs, "center_hz": center_hz, "n": int(iq.size), "dtype": "complex64", **(meta or {})}
    path.with_suffix(path.suffix + ".json").write_text(json.dumps(m, indent=2))
    iq.tofile(path)


def load_iq(path: str | Path) -> tuple[np.ndarray, dict]:
    import json

    path = Path(path)
    meta = {}
    j = path.with_suffix(path.suffix + ".json")
    if j.exists():
        meta = json.loads(j.read_text())
    iq = np.fromfile(path, dtype=np.complex64)
    return iq, meta


def downconvert(iq: np.ndarray, offset_hz: float, fs: float) -> np.ndarray:
    n = np.arange(iq.size)
    return iq * np.exp(-1j * 2 * np.pi * offset_hz * n / fs)


def lowpass(x: np.ndarray, cutoff_hz: float, fs: float, order: int = 5) -> np.ndarray:
    from scipy.signal import butter, filtfilt

    nyq = fs / 2
    b, a = butter(order, min(cutoff_hz / nyq, 0.99), btype="low")
    return filtfilt(b, a, x)
