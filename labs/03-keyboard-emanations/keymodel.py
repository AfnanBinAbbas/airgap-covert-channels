"""Per-key EM impulse model + scancode stream for Keysweeper-class lab."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Simplified QWERTY → impulse class id (not full scancode set; lab alphabet)
KEY_CLASSES = list("ETAOINSHRDLCUMWFGYPBVKJXQZ0123456789 .,;:!?'-")
# map char -> class index
CHAR_TO_IDX = {c: i for i, c in enumerate(KEY_CLASSES)}

FS = 100_000.0  # 100 kHz "scope" rate for impulse capture sim
IMPULSE_LEN = 512  # samples per key event capture window (≈5 ms)


def key_template(idx: int, n: int = IMPULSE_LEN, fs: float = FS,
                 seed: int | None = None) -> np.ndarray:
    """Deterministic waveform template for key class `idx`.
    Unique fundamental per class (500 + 45*idx Hz) → well-separated spectra.
    """
    rng = np.random.default_rng((seed or 0) + idx * 9973)
    f0 = 500.0 + 45.0 * (idx % len(KEY_CLASSES))  # 500–2065 Hz unique
    decay = 55.0 + 2.5 * (idx % 9)
    pol = 1.0 if idx % 2 == 0 else -1.0
    t = np.arange(n) / fs
    x = pol * np.exp(-decay * t) * np.sin(2 * np.pi * f0 * t)
    # class-dependent secondary resonance
    x += 0.35 * np.exp(-decay * 1.7 * t) * np.sin(2 * np.pi * f0 * 1.61 * t + 0.4 * (idx % 5))
    # tiny per-press jitter (fixed when seed=0 for bank templates)
    shift = int(rng.integers(-3, 4)) if seed else 0
    x = np.roll(x, shift)
    return x


def phrase_to_events(phrase: str, wpm: float = 60.0,
                     seed: int | None = None) -> list[tuple[int, int]]:
    """Return list of (class_idx, start_sample) for a typed phrase.
    Inter-key interval from WPM (chars per minute ≈ wpm for words of 5).
    """
    rng = np.random.default_rng(seed)
    cpm = wpm * 5.0  # chars per minute
    samples_per_char = int(FS * 60.0 / cpm)
    events = []
    t = int(0.05 * FS)  # start delay
    for ch in phrase.upper():
        if ch not in CHAR_TO_IDX:
            continue
        events.append((CHAR_TO_IDX[ch], t))
        # human jitter ±15%
        jitter = int(samples_per_char * rng.uniform(-0.15, 0.15))
        t += max(samples_per_char + jitter, int(0.03 * FS))
    return events


def synthesize_capture(phrase: str, snr_db: float = 20.0,
                       seed: int | None = None) -> tuple[np.ndarray, str, list]:
    """Full capture: sum of impulses + noise. Returns (wave, expected_upcase, events)."""
    rng = np.random.default_rng(seed)
    events = phrase_to_events(phrase, seed=seed)
    if not events:
        return np.zeros(1), "", []
    end = events[-1][1] + IMPULSE_LEN + 16
    wave = np.zeros(end)
    for idx, start in events:
        amp = rng.uniform(0.8, 1.15)
        # fixed template (seed=0) so presses match the bank; amplitude still varies
        tmpl = key_template(idx, seed=0)
        # amplitude varies slightly
        amp = rng.uniform(0.8, 1.15)
        seg_end = min(start + tmpl.size, wave.size)
        wave[start:seg_end] += amp * tmpl[: seg_end - start]
    # noise
    p_sig = np.mean(wave**2) + 1e-15
    p_noise = p_sig / (10 ** (snr_db / 10))
    wave = wave + rng.normal(0, np.sqrt(p_noise), wave.size)
    expected = "".join(c for c in phrase.upper() if c in CHAR_TO_IDX)
    return wave, expected, events


if __name__ == "__main__":
    w, exp, ev = synthesize_capture("attack at dawn", snr_db=25, seed=1)
    print(f"wave={w.size} expected={exp!r} events={len(ev)}")
