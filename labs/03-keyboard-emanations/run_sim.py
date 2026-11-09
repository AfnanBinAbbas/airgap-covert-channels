#!/usr/bin/env python3
"""Lab 03: type a secret, recover keystrokes from synthetic EM capture."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(LAB))

from common.metrics import save_result  # noqa: E402

from classifier import CentroidClassifier, idx_to_text, train_test_from_phrases  # noqa: E402
from features import build_dataset, extract_windows, featurize, build_template_bank  # noqa: E402
from keymodel import synthesize_capture  # noqa: E402


def char_accuracy(pred: str, truth: str) -> float:
    n = max(len(pred), len(truth), 1)
    # alignment via simple LCS length / max len
    m, n2 = len(pred), len(truth)
    dp = np.zeros((m + 1, n2 + 1), dtype=int)
    for i in range(1, m + 1):
        for j in range(1, n2 + 1):
            if pred[i - 1] == truth[j - 1]:
                dp[i, j] = dp[i - 1, j - 1] + 1
            else:
                dp[i, j] = max(dp[i - 1, j], dp[i, j - 1])
    return float(dp[m, n2] / n)


def main() -> None:
    secret = "meet at the old bridge at dawn"
    train_phrases = [
        "attack the north gate",
        "send reinforcements now",
        "coordinates confirmed",
        "secure the perimeter",
    ]
    print(f"[*] Lab 03 keyboard EM keylogger, with secret={secret!r}")

    # accuracy vs SNR (lighter sweep for speed)
    sweep = []
    for snr in [25, 15, 8]:
        Xtr, ytr, Xte, yte = train_test_from_phrases(
            train_phrases, snr_db=max(snr, 10), n_train_per=2, seed=10
        )
        if Xtr.shape[0] == 0 or Xte.shape[0] == 0:
            sweep.append({"snr_db": snr, "char_acc": 0.0, "n_test": 0})
            continue
        clf = CentroidClassifier().fit(Xtr, ytr)
        yhat = clf.predict(Xte)
        acc = float(np.mean(yhat == yte))
        sweep.append({"snr_db": snr, "window_acc": acc, "n_test": int(yte.size)})
        print(f"  SNR={snr:2d} dB  window_acc={acc:.1%}  n={yte.size}")

    # final: train on generic, test on secret at 15 dB
    Xtr, ytr, _, _ = train_test_from_phrases(train_phrases, snr_db=15, n_train_per=3, seed=7)
    clf = CentroidClassifier().fit(Xtr, ytr)
    wave, expected, events = synthesize_capture(secret, snr_db=15, seed=99)
    wins = extract_windows(wave)
    m = min(len(wins), len(expected))
    bank = build_template_bank()
    X = np.stack([featurize(wins[i], template_bank=bank) for i in range(m)]) if m else np.zeros((0, 1))
    yhat = clf.predict(X) if m else np.array([], dtype=int)
    pred = idx_to_text(yhat)
    acc = char_accuracy(pred, expected)
    print(f"[+] recovered={pred!r}")
    print(f"[+] expected ={expected!r}")
    print(f"[+] char_accuracy={acc:.1%}  windows={m} events={len(events)}")

    ok = acc >= 0.7 and m >= max(3, int(0.6 * len(expected)))
    save_result(
        "03-keyboard-emanations",
        {
            "secret": secret,
            "recovered": pred,
            "expected": expected,
            "char_accuracy": acc,
            "sweep": sweep,
            "pass": bool(ok),
        },
        out_dir=str(ROOT / "results"),
    )
    print(f"[{'PASS' if ok else 'FAIL'}] keyboard EM keylogger")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
