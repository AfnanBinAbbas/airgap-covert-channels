"""Windowing + template-correlation features for key EM pulses."""

from __future__ import annotations

import numpy as np
from scipy.signal import find_peaks

from keymodel import CHAR_TO_IDX, FS, IMPULSE_LEN, KEY_CLASSES, key_template


def extract_windows(wave: np.ndarray, threshold_ratio: float = 0.3,
                    min_gap: int = 8000) -> list[np.ndarray]:
    """Envelope-peak event detection → fixed-length windows locked to onsets."""
    x = np.asarray(wave, dtype=np.float64)
    # smooth |x| envelope
    env = np.convolve(np.abs(x), np.ones(24) / 24, mode="same")
    if env.size == 0 or env.max() <= 0:
        return []
    height = threshold_ratio * float(env.max())
    peaks, _ = find_peaks(env, height=height, distance=int(min_gap))
    windows = []
    onset_back = 16  # start slightly before peak so template onset aligns
    n = x.size
    for p in peaks:
        w0 = max(0, int(p) - onset_back)
        # back up a little more if leading energy is still rising
        w1 = min(n, w0 + IMPULSE_LEN)
        if w1 - w0 < IMPULSE_LEN // 2:
            continue
        win = np.zeros(IMPULSE_LEN)
        seg = x[w0:w1]
        win[: seg.size] = seg
        windows.append(win)
    return windows


def _normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / (n + 1e-12)


def _best_lag(a: np.ndarray, b: np.ndarray, max_lag: int = 32) -> tuple[float, int]:
    """Max normalized cross-correlation and lag of template b against window a."""
    a = _normalize(a)
    b = _normalize(b)
    best, best_lag = -1.0, 0
    for lag in range(-max_lag, max_lag + 1):
        if lag >= 0:
            aa, bb = a[lag:], b[: b.size - lag] if lag else b
        else:
            aa, bb = a[: a.size + lag], b[-lag:]
        m = min(aa.size, bb.size)
        if m < 32:
            continue
        c = float(np.dot(aa[:m], bb[:m]))
        if c > best:
            best, best_lag = c, lag
    return best, best_lag


def featurize(win: np.ndarray, fs: float = FS, template_bank: np.ndarray | None = None) -> np.ndarray:
    """Feature vector = lag-max correlation vs each key-class template (+ rms)."""
    x = np.asarray(win, dtype=np.float64)
    if template_bank is None:
        template_bank = build_template_bank()
    scores = np.array([_best_lag(x, template_bank[i])[0] for i in range(template_bank.shape[0])])
    rms = float(np.sqrt(np.mean(x**2)) + 1e-12)
    return np.concatenate([scores, np.array([rms], dtype=np.float64)])


_TEMPLATE_BANK: np.ndarray | None = None


def build_template_bank(refresh: bool = False) -> np.ndarray:
    """(n_classes, IMPULSE_LEN) unit-norm templates (cached)."""
    global _TEMPLATE_BANK
    if _TEMPLATE_BANK is None or refresh:
        bank = []
        for i in range(len(KEY_CLASSES)):
            t = key_template(i, seed=0)  # fixed per class
            bank.append(_normalize(t))
        _TEMPLATE_BANK = np.stack(bank)
    return _TEMPLATE_BANK


def build_dataset(waves_and_labels: list[tuple[np.ndarray, str]]) -> tuple[np.ndarray, np.ndarray]:
    bank = build_template_bank()
    X_list = []
    y_list = []
    for wave, expected in waves_and_labels:
        wins = extract_windows(wave)
        m = min(len(wins), len(expected))
        for i in range(m):
            X_list.append(featurize(wins[i], template_bank=bank))
            y_list.append(CHAR_TO_IDX[expected[i]])
    if not X_list:
        return np.zeros((0, len(KEY_CLASSES) + 1)), np.zeros(0, dtype=int)
    return np.stack(X_list), np.array(y_list, dtype=int)
