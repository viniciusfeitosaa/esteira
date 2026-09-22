"""Helpers de ROI da esteira (fundo escuro)."""

from __future__ import annotations

import cv2
import numpy as np


def estimate_belt_x_range(gray: np.ndarray) -> tuple[int, int]:
    h, w = gray.shape
    col_mean = gray.mean(axis=0)
    k = max(5, w // 40 | 1)
    smooth = np.convolve(col_mean, np.ones(k) / k, mode="same")
    thr = float(np.percentile(smooth, 48))
    mask = smooth <= thr
    best_len = 0
    best = (int(w * 0.20), int(w * 0.80))
    i = 0
    while i < w:
        if not mask[i]:
            i += 1
            continue
        j = i
        while j < w and mask[j]:
            j += 1
        if j - i > best_len:
            best_len = j - i
            best = (i, j)
        i = j
    x0, x1 = best
    pad = max(1, (x1 - x0) // 50)
    return max(0, x0 + pad), min(w, x1 - pad)


def crop_belt_bgr(bgr: np.ndarray) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    """Retorna crop e (x0,y0,x1,y1) no frame original."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    x0, x1 = estimate_belt_x_range(gray)
    pad = max(4, (x1 - x0) // 15)
    x0 = max(0, x0 - pad)
    x1 = min(w, x1 + pad)
    y0, y1 = int(h * 0.10), int(h * 0.90)
    return bgr[y0:y1, x0:x1].copy(), (x0, y0, x1, y1)
