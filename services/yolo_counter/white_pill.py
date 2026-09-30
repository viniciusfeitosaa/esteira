"""Detector classico de comprimido branco oblongo sobre esteira preta (auto-label).

Dois caminhos:
- fora do reflexo: top-hat no canal V (remove fundo largo) + forma + anel escuro;
- dentro de blobs grandes (reflexo texturizado da borracha): mediana 7x7 apaga a
  hachura e so os nucleos lisos e muito claros (comprimido) passam do limiar.
"""

from __future__ import annotations

import cv2
import numpy as np

Box = tuple[float, float, float, float]

_K41 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (41, 41))


def _ring_stats(img: np.ndarray, x: int, y: int, w: int, h: int, pad: int) -> float:
    H, W = img.shape[:2]
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(W, x + w + pad), min(H, y + h + pad)
    outer = img[y0:y1, x0:x1].astype(np.float32)
    inner = img[y : y + h, x : x + w].astype(np.float32)
    n = outer.size - inner.size
    return float((outer.sum() - inner.sum()) / max(1, n))


def _shape(lab: np.ndarray, i: int, x: int, y: int, w: int, h: int, area: int) -> tuple[float, float]:
    pts = np.column_stack(np.where(lab[y : y + h, x : x + w] == i))[:, ::-1].astype(np.float32)
    (_, _), (rw, rh), _ = cv2.minAreaRect(pts)
    aspect = max(rw, rh) / max(1.0, min(rw, rh))
    fill = area / max(1.0, rw * rh)
    return aspect, fill


def _glare_cores(
    vm: np.ndarray, v: np.ndarray, x: int, y: int, w: int, h: int, thr: int, min_area: int, max_area: int
) -> list[Box]:
    sub = (vm[y : y + h, x : x + w] >= thr).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(sub, connectivity=8)
    out: list[Box] = []
    for i in range(1, n):
        cx, cy, cw, ch, a = (int(v) for v in st[i])
        if a < min_area or a > max_area:
            continue
        aspect, fill = _shape(lab, i, cx, cy, cw, ch, a)
        if not (1.15 <= aspect <= 3.8 and fill >= 0.6):
            continue
        g = 3
        box = (float(x + cx - g), float(y + cy - g), float(x + cx + cw + g), float(y + cy + ch + g))
        if _has_shadow(v, box):
            out.append(box)
    return out


def _has_shadow(v: np.ndarray, box: Box, depth: int = 8, max_v: float = 130.0) -> bool:
    """Luz vem de cima: comprimido real projeta sombra escura logo abaixo; reflexo nao."""
    H, W = v.shape
    x1, y1, x2, y2 = (int(round(q)) for q in box)
    x1, x2 = max(0, x1), min(W, x2)
    ys, ye = min(H, max(0, y2 - 2)), min(H, y2 + depth)
    if ye <= ys or x2 <= x1:
        return False
    return float(np.percentile(v[ys:ye, x1:x2], 15)) <= max_v


def detect_white_pills(
    bgr: np.ndarray,
    min_area: int = 55,
    max_area: int = 700,
    max_side: int = 50,
    min_contrast: float = 70.0,
    ring_s_max: float = 90.0,
) -> tuple[list[Box], int]:
    """Retorna (boxes xyxy, n_incertos). Incerto = blob claro e liso em fundo escuro
    que nao passa como comprimido isolado (ex.: dois encostados) -> descartar frame."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    v, s = hsv[..., 2], hsv[..., 1]
    vm = cv2.medianBlur(v, 7)
    th = cv2.morphologyEx(v, cv2.MORPH_TOPHAT, _K41)
    m = ((th >= 60) & (v >= 170) & (s <= 70)).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)

    boxes: list[Box] = []
    uncertain = 0
    for i in range(1, n):
        x, y, w, h, area = (int(q) for q in st[i])
        if area < min_area:
            continue
        if area > max_area or w > max_side or h > max_side:
            if area <= 12000:
                boxes += _glare_cores(vm, v, x, y, w, h, 235, min_area, max_area)
            continue
        pad = max(5, int(0.4 * max(w, h)))
        ring_v = _ring_stats(v, x, y, w, h, pad)
        ring_s = _ring_stats(s, x, y, w, h, pad)
        mean_v = float(v[y : y + h, x : x + w][lab[y : y + h, x : x + w] == i].mean())
        if mean_v - ring_v < min_contrast or ring_s > ring_s_max:
            continue
        aspect, fill = _shape(lab, i, x, y, w, h, area)
        if 1.25 <= aspect <= 3.8 and fill >= 0.6 and mean_v >= 185:
            boxes.append((float(x - 1), float(y - 1), float(x + w + 1), float(y + h + 1)))
        elif fill >= 0.45 and mean_v >= 200 and area >= 1.5 * min_area:
            uncertain += 1
    return _dedupe(boxes), uncertain


def _dedupe(boxes: list[Box], iou_thr: float = 0.3) -> list[Box]:
    keep: list[Box] = []
    for b in sorted(boxes, key=lambda q: (q[2] - q[0]) * (q[3] - q[1]), reverse=True):
        if all(_iou(b, k) < iou_thr for k in keep):
            keep.append(b)
    return keep


def _iou(a: Box, b: Box) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0
