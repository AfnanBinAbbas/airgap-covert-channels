"""Nearest-centroid classifier for key EM classes (template-correlation features)."""

from __future__ import annotations

import numpy as np

from keymodel import KEY_CLASSES


class CentroidClassifier:
    def __init__(self) -> None:
        self.classes_: np.ndarray | None = None
        self.centroids_: np.ndarray | None = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> "CentroidClassifier":
        classes = np.unique(y)
        cents = np.stack([X[y == c].mean(axis=0) for c in classes])
        norms = np.linalg.norm(cents, axis=1, keepdims=True) + 1e-12
        self.classes_ = classes
        self.centroids_ = cents / norms
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        assert self.centroids_ is not None and self.classes_ is not None
        Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-12)
        sims = Xn @ self.centroids_.T
        return self.classes_[np.argmax(sims, axis=1)]


def idx_to_text(idxs: np.ndarray) -> str:
    out = []
    for i in idxs:
        if 0 <= i < len(KEY_CLASSES):
            out.append(KEY_CLASSES[i])
    return "".join(out)


def train_test_from_phrases(phrases: list[str], snr_db: float = 20.0,
                            n_train_per: int = 3, seed: int = 0):
    from features import build_dataset
    from keymodel import synthesize_capture

    train_pairs = []
    test_pairs = []
    for pi, ph in enumerate(phrases):
        for k in range(n_train_per + 2):
            w, exp, _ = synthesize_capture(ph, snr_db=snr_db, seed=seed + pi * 100 + k)
            if k < n_train_per:
                train_pairs.append((w, exp))
            else:
                test_pairs.append((w, exp))
    Xtr, ytr = build_dataset(train_pairs)
    Xte, yte = build_dataset(test_pairs)
    return Xtr, ytr, Xte, yte
