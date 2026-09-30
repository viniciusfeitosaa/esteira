#!/usr/bin/env python3
"""Dataset YOLO para a webcam fixa (esteira horizontal, comprimido branco oblongo).

1. Extrai frames dos videos e gera labels com o detector classico (white_pill).
   Frames com blobs incertos (ex.: comprimidos encostados) sao descartados.
2. Split por tempo: o trecho final de cada video vai para val (frames vizinhos
   sao quase identicos; split aleatorio vazaria treino para a validacao).
3. Multiplica o treino com copias *variadas* (blur de movimento, ruido, brilho,
   reflexo artificial, JPEG, escala, rotacao, espelhamento).
4. Gera sinteticos copy-paste: recortes reais de comprimidos (videos + fotos)
   colados em frames sem comprimidos, com sombra, varias quantidades e
   comprimidos encostados — cada label e exata por construcao.

  py -3.12 scripts/prepare_fixedcam_dataset.py --videos "C:\\...\\WhatsApp Unknown ..." --photos "C:\\...\\WhatsApp Unknown ..."
"""
from __future__ import annotations

import argparse
import random
import re
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.yolo_counter.white_pill import Box, detect_white_pills  # noqa: E402

DEFAULT_OUT = ROOT / "datasets" / "pills_fixed"


def slug(name: str) -> str:
    return (re.sub(r"[^\w\-]+", "_", name).strip("_") or "vid")[:60]


def list_files(folder: Path, exts: tuple[str, ...]) -> list[Path]:
    return sorted({p.resolve() for p in folder.iterdir() if p.suffix.lower() in exts}, key=lambda p: p.name.lower())


# ---------------------------------------------------------------- labels I/O

def write_label(path: Path, boxes: list[Box], w: int, h: int) -> None:
    lines = []
    for x1, y1, x2, y2 in boxes:
        x1, y1 = max(0.0, x1), max(0.0, y1)
        x2, y2 = min(float(w), x2), min(float(h), y2)
        if x2 - x1 < 2 or y2 - y1 < 2:
            continue
        lines.append(f"0 {(x1 + x2) / 2 / w:.6f} {(y1 + y2) / 2 / h:.6f} {(x2 - x1) / w:.6f} {(y2 - y1) / h:.6f}")
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def read_label(path: Path, w: int, h: int) -> list[Box]:
    out: list[Box] = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        p = line.split()
        if len(p) < 5:
            continue
        _, cx, cy, bw, bh = map(float, p[:5])
        out.append(((cx - bw / 2) * w, (cy - bh / 2) * h, (cx + bw / 2) * w, (cy + bh / 2) * h))
    return out


# ---------------------------------------------------------------- 1+2: frames

def _merge_boxes(a: list[Box], b: list[Box], iou_thr: float = 0.3) -> list[Box]:
    out = list(a)
    for q in b:
        if all(_iou(q, k) < iou_thr for k in out):
            out.append(q)
    return out


def _iou(a: Box, b: Box) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def extract_and_label(
    videos: list[Path], out: Path, fps: float, val_tail: float, relabel=None
) -> dict[str, list[Path]]:
    """relabel: funcao frame -> boxes de um YOLO ja treinado; completa o que o
    detector classico perde (principalmente comprimidos dentro do reflexo)."""
    split_imgs: dict[str, list[Path]] = {"train": [], "val": []}
    stats = {"frames": 0, "kept": 0, "skipped_uncertain": 0, "boxes": 0}
    for vp in videos:
        cap = cv2.VideoCapture(str(vp))
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        step = max(1, int(round(src_fps / fps)))
        val_from = int(n * (1.0 - val_tail))
        stem = slug(vp.stem)
        idx = kept = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % step == 0:
                stats["frames"] += 1
                boxes, unc = detect_white_pills(frame)
                if relabel is not None:
                    boxes = _merge_boxes(boxes, relabel(frame))
                    unc = 0
                if unc:
                    stats["skipped_uncertain"] += 1
                else:
                    split = "val" if idx >= val_from else "train"
                    name = f"{stem}_{idx:05d}"
                    img = out / "images" / split / f"{name}.jpg"
                    cv2.imwrite(str(img), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
                    h, w = frame.shape[:2]
                    write_label(out / "labels" / split / f"{name}.txt", boxes, w, h)
                    split_imgs[split].append(img)
                    stats["kept"] += 1
                    stats["boxes"] += len(boxes)
                    kept += 1
            idx += 1
        cap.release()
        print(f"{vp.name}: {kept} frames uteis (step={step})")
    print(
        f"frames={stats['frames']} uteis={stats['kept']} descartados_incertos={stats['skipped_uncertain']} "
        f"boxes={stats['boxes']} train={len(split_imgs['train'])} val={len(split_imgs['val'])}"
    )
    return split_imgs


# ---------------------------------------------------------------- 3: augment

def _affine_boxes(boxes: list[Box], M: np.ndarray, w: int, h: int) -> list[Box]:
    out: list[Box] = []
    for x1, y1, x2, y2 in boxes:
        pts = np.array([[x1, y1, 1], [x2, y1, 1], [x2, y2, 1], [x1, y2, 1]], np.float32)
        t = pts @ M.T
        nx1, ny1 = t[:, 0].min(), t[:, 1].min()
        nx2, ny2 = t[:, 0].max(), t[:, 1].max()
        # encolhe o excesso do bbox de um retangulo girado (comprimido e eliptico)
        cx, cy = (nx1 + nx2) / 2, (ny1 + ny2) / 2
        sw = (nx2 - nx1) * 0.92 / 2
        sh = (ny2 - ny1) * 0.92 / 2
        b = (cx - sw, cy - sh, cx + sw, cy + sh)
        vis_w = min(b[2], w) - max(b[0], 0)
        vis_h = min(b[3], h) - max(b[1], 0)
        if vis_w <= 0 or vis_h <= 0 or vis_w * vis_h < 0.5 * (b[2] - b[0]) * (b[3] - b[1]):
            continue
        out.append(b)
    return out


def _motion_blur(img: np.ndarray, rng: random.Random) -> np.ndarray:
    k = rng.choice([5, 7, 9, 11])
    kern = np.zeros((k, k), np.float32)
    kern[k // 2, :] = 1.0 / k
    ang = rng.uniform(-20, 20)
    M = cv2.getRotationMatrix2D((k / 2 - 0.5, k / 2 - 0.5), ang, 1.0)
    kern = cv2.warpAffine(kern, M, (k, k))
    kern /= max(1e-6, kern.sum())
    return cv2.filter2D(img, -1, kern)


def _fake_glare(img: np.ndarray, rng: random.Random) -> np.ndarray:
    h, w = img.shape[:2]
    ov = np.zeros((h, w), np.float32)
    cx, cy = rng.uniform(0.2, 0.8) * w, rng.uniform(0.3, 0.7) * h
    ax, ay = rng.uniform(0.08, 0.25) * w, rng.uniform(0.04, 0.12) * h
    cv2.ellipse(ov, (int(cx), int(cy)), (int(ax), int(ay)), rng.uniform(-15, 15), 0, 360, 1.0, -1)
    ov = cv2.GaussianBlur(ov, (0, 0), sigmaX=max(3.0, ax / 3))
    gain = rng.uniform(60, 130)
    out = img.astype(np.float32) + ov[..., None] * gain
    return np.clip(out, 0, 255).astype(np.uint8)


def augment_once(img: np.ndarray, boxes: list[Box], rng: random.Random) -> tuple[np.ndarray, list[Box]]:
    h, w = img.shape[:2]
    if rng.random() < 0.5:
        img = img[:, ::-1].copy()
        boxes = [(w - x2, y1, w - x1, y2) for x1, y1, x2, y2 in boxes]
    if rng.random() < 0.25:
        img = img[::-1].copy()
        boxes = [(x1, h - y2, x2, h - y1) for x1, y1, x2, y2 in boxes]
    ang = rng.uniform(-8, 8)
    sc = rng.uniform(0.8, 1.25)
    M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, sc)
    M[0, 2] += rng.uniform(-0.06, 0.06) * w
    M[1, 2] += rng.uniform(-0.06, 0.06) * h
    img = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=(114, 114, 114))
    boxes = _affine_boxes(boxes, M, w, h)

    f = img.astype(np.float32)
    f = f * rng.uniform(0.7, 1.3) + rng.uniform(-30, 30)
    gamma = rng.uniform(0.75, 1.35)
    f = 255.0 * np.power(np.clip(f, 0, 255) / 255.0, gamma)
    if rng.random() < 0.3:
        f += np.array([rng.uniform(-12, 12) for _ in range(3)], np.float32)
    img = np.clip(f, 0, 255).astype(np.uint8)
    if rng.random() < 0.35:
        img = _fake_glare(img, rng)
    r = rng.random()
    if r < 0.35:
        img = _motion_blur(img, rng)
    elif r < 0.55:
        img = cv2.GaussianBlur(img, (0, 0), rng.uniform(0.6, 1.6))
    if rng.random() < 0.35:
        noise = np.random.default_rng(rng.randrange(1 << 30)).normal(0, rng.uniform(3, 10), img.shape)
        img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    if rng.random() < 0.5:
        q = rng.randint(35, 80)
        img = cv2.imdecode(cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), q])[1], cv2.IMREAD_COLOR)
    return img, boxes


def make_augmented(out: Path, train_imgs: list[Path], copies: int, rng: random.Random) -> int:
    n = 0
    for img_p in train_imgs:
        img = cv2.imread(str(img_p))
        h, w = img.shape[:2]
        boxes = read_label(out / "labels" / "train" / f"{img_p.stem}.txt", w, h)
        for k in range(copies):
            aimg, aboxes = augment_once(img, boxes, rng)
            name = f"aug{k}_{img_p.stem}"
            cv2.imwrite(str(out / "images" / "train" / f"{name}.jpg"), aimg, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            write_label(out / "labels" / "train" / f"{name}.txt", aboxes, w, h)
            n += 1
    print(f"augment: {n} copias variadas")
    return n


# ---------------------------------------------------------------- 4: synthetic

def _sprite_from_patch(patch: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    v = cv2.medianBlur(hsv[..., 2], 3)
    thr = max(150, int(np.percentile(v, 97)) - 45)
    m = ((v >= thr) & (hsv[..., 1] <= 80)).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    if n < 2:
        return None
    i = 1 + int(np.argmax(st[1:, 4]))
    mask = (lab == i).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    mask = np.zeros_like(mask)
    cv2.drawContours(mask, cnts, -1, 255, -1)
    x, y, w, h = cv2.boundingRect(mask)
    if w < 6 or h < 6:
        return None
    (_, _), (rw, rh), _ = cv2.minAreaRect(max(cnts, key=cv2.contourArea))
    aspect = max(rw, rh) / max(1.0, min(rw, rh))
    fill = float((mask > 0).sum()) / max(1.0, rw * rh)
    if not (1.3 <= aspect <= 3.8 and fill >= 0.7):
        return None
    return patch[y : y + h, x : x + w].copy(), mask[y : y + h, x : x + w].copy()


def collect_sprites(out: Path, train_imgs: list[Path], photos: list[Path], max_video: int, rng: random.Random):
    sprites: list[tuple[np.ndarray, np.ndarray]] = []
    pool = train_imgs[:]
    rng.shuffle(pool)
    for img_p in pool:
        if len(sprites) >= max_video:
            break
        img = cv2.imread(str(img_p))
        h, w = img.shape[:2]
        for x1, y1, x2, y2 in read_label(out / "labels" / "train" / f"{img_p.stem}.txt", w, h):
            g = 3
            xa, ya, xb, yb = int(max(0, x1 - g)), int(max(0, y1 - g)), int(min(w, x2 + g)), int(min(h, y2 + g))
            s = _sprite_from_patch(img[ya:yb, xa:xb])
            if s is not None and s[1].sum() / 255 >= 40:
                sprites.append(s)
    n_video = len(sprites)
    for ph in photos:
        img = cv2.imread(str(ph))
        if img is None:
            continue
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        m = ((hsv[..., 2] >= 170) & (hsv[..., 1] <= 60)).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        n, _, st, _ = cv2.connectedComponentsWithStats(m)
        for i in range(1, n):
            x, y, bw, bh, a = (int(q) for q in st[i])
            asp = max(bw, bh) / max(1, min(bw, bh))
            if not (800 <= a <= 60000 and 1.2 <= asp <= 3.8):
                continue
            g = 6
            s = _sprite_from_patch(img[max(0, y - g) : y + bh + g, max(0, x - g) : x + bw + g])
            if s is not None:
                sprites.append(s)
    print(f"sprites: {n_video} dos videos + {len(sprites) - n_video} das fotos")
    return sprites, n_video


def _paste(bg: np.ndarray, sprite: np.ndarray, mask: np.ndarray, x: int, y: int, rng: random.Random) -> None:
    h, w = mask.shape
    H, W = bg.shape[:2]
    if x < 0 or y < 0 or x + w > W or y + h > H:
        return
    a = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (3, 3), 0)[..., None]
    # sombra: luz de cima, sombra desloca para baixo
    sy = max(2, int(0.25 * h))
    sh_mask = np.zeros((h + sy, w + 2), np.float32)
    sh_mask[sy : sy + h, 1 : 1 + w] = mask.astype(np.float32) / 255.0
    sh_mask = cv2.GaussianBlur(sh_mask, (0, 0), 2.0)[..., None]
    ys, ye = y, min(H, y + h + sy)
    xs, xe = max(0, x - 1), min(W, x + w + 1)
    region = bg[ys:ye, xs:xe].astype(np.float32)
    shm = sh_mask[: ye - ys, : xe - xs]
    region *= 1.0 - shm * rng.uniform(0.45, 0.75)
    bg[ys:ye, xs:xe] = np.clip(region, 0, 255).astype(np.uint8)
    roi = bg[y : y + h, x : x + w].astype(np.float32)
    bg[y : y + h, x : x + w] = np.clip(roi * (1 - a) + sprite.astype(np.float32) * a, 0, 255).astype(np.uint8)


def _transform_sprite(sprite: np.ndarray, mask: np.ndarray, target_long: float, rng: random.Random):
    h, w = mask.shape
    sc = target_long / max(h, w)
    sprite = cv2.resize(sprite, (max(3, int(w * sc)), max(3, int(h * sc))), interpolation=cv2.INTER_AREA)
    mask = cv2.resize(mask, (sprite.shape[1], sprite.shape[0]), interpolation=cv2.INTER_LINEAR)
    ang = rng.uniform(0, 180)
    h, w = mask.shape
    d = int(np.ceil(np.hypot(h, w))) + 2
    M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
    M[0, 2] += (d - w) / 2
    M[1, 2] += (d - h) / 2
    sprite = cv2.warpAffine(sprite, M, (d, d), flags=cv2.INTER_LINEAR)
    mask = cv2.warpAffine(mask, M, (d, d), flags=cv2.INTER_LINEAR)
    ys, xs = np.where(mask > 127)
    if len(xs) == 0:
        return None
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    b = sprite[y0:y1, x0:x1]
    f = rng.uniform(0.85, 1.1)
    b = np.clip(b.astype(np.float32) * f, 0, 255).astype(np.uint8)
    return b, mask[y0:y1, x0:x1]


def _belt_ok(bg: np.ndarray, x: int, y: int, w: int, h: int) -> bool:
    H, W = bg.shape[:2]
    g = 8
    xa, ya, xb, yb = max(0, x - g), max(0, y - g), min(W, x + w + g), min(H, y + h + g)
    hsv = cv2.cvtColor(bg[ya:yb, xa:xb], cv2.COLOR_BGR2HSV)
    return float(hsv[..., 1].mean()) < 55 and float(np.median(hsv[..., 2])) < 215 and float((hsv[..., 2] < 140).mean()) > 0.5


def _video_key(img_p: Path) -> str:
    return img_p.stem.rsplit("_", 1)[0]


def pill_zones(out: Path, train_imgs: list[Path]) -> dict[str, np.ndarray]:
    """Por video: mascara do fecho convexo dos centros de comprimidos reais (= esteira)."""
    centers: dict[str, list[tuple[float, float]]] = {}
    shape: dict[str, tuple[int, int]] = {}
    for img_p in train_imgs:
        key = _video_key(img_p)
        if key not in shape:
            h, w = cv2.imread(str(img_p)).shape[:2]
            shape[key] = (h, w)
        h, w = shape[key]
        for x1, y1, x2, y2 in read_label(out / "labels" / "train" / f"{img_p.stem}.txt", w, h):
            centers.setdefault(key, []).append(((x1 + x2) / 2, (y1 + y2) / 2))
    zones: dict[str, np.ndarray] = {}
    for key, pts in centers.items():
        if len(pts) < 10:
            continue
        h, w = shape[key]
        hull = cv2.convexHull(np.array(pts, np.float32)).astype(np.int32)
        m = np.zeros((h, w), np.uint8)
        cv2.fillConvexPoly(m, hull, 255)
        zones[key] = cv2.erode(m, np.ones((15, 15), np.uint8))
    return zones


def make_backgrounds(
    out: Path, train_imgs: list[Path], max_bg: int, rng: random.Random
) -> list[tuple[np.ndarray, np.ndarray | None]]:
    zones = pill_zones(out, train_imgs)
    pool = train_imgs[:]
    rng.shuffle(pool)
    bgs: list[tuple[np.ndarray, np.ndarray | None]] = []
    for img_p in pool[: max_bg]:
        img = cv2.imread(str(img_p))
        h, w = img.shape[:2]
        mask = np.zeros((h, w), np.uint8)
        for x1, y1, x2, y2 in read_label(out / "labels" / "train" / f"{img_p.stem}.txt", w, h):
            cv2.rectangle(mask, (int(x1) - 3, int(y1) - 3), (int(x2) + 3, int(y2) + 8), 255, -1)
        clean = cv2.inpaint(img, mask, 5, cv2.INPAINT_TELEA) if mask.any() else img
        bgs.append((clean, zones.get(_video_key(img_p))))
    return bgs


def make_synthetic(out: Path, train_imgs: list[Path], photos: list[Path], count: int, rng: random.Random) -> int:
    if count <= 0:
        return 0
    sprites, _ = collect_sprites(out, train_imgs, photos, 400, rng)
    if not sprites:
        print("sinteticos: sem sprites, pulando")
        return 0
    lens = []
    for img_p in train_imgs[:200]:
        img = cv2.imread(str(img_p))
        h, w = img.shape[:2]
        lens += [max(b[2] - b[0], b[3] - b[1]) for b in read_label(out / "labels" / "train" / f"{img_p.stem}.txt", w, h)]
    med_len = float(np.median(lens)) if lens else 24.0
    bgs = make_backgrounds(out, train_imgs, 150, rng)
    made = 0
    for k in range(count):
        bg, zone = bgs[k % len(bgs)]
        bg = bg.copy()
        H, W = bg.shape[:2]
        n_target = rng.choice([1, 2, 3, 5, 8, 12, 16, 20, 25, 30])
        boxes: list[Box] = []
        tries = 0
        while len(boxes) < n_target and tries < n_target * 25:
            tries += 1
            spr = rng.choice(sprites)
            t = _transform_sprite(spr[0], spr[1], med_len * rng.uniform(0.75, 1.3), rng)
            if t is None:
                continue
            s_img, s_mask = t
            h, w = s_mask.shape
            if boxes and rng.random() < 0.3:
                bx = rng.choice(boxes)
                x = int(rng.choice([bx[2] - 2, bx[0] - w + 2, (bx[0] + bx[2]) / 2 - w / 2]))
                y = int(rng.choice([bx[3] - 2, bx[1] - h + 2, (bx[1] + bx[3]) / 2 - h / 2]))
            else:
                x, y = rng.randint(0, W - w - 1), rng.randint(0, H - h - 1)
            if x < 0 or y < 0 or x + w >= W or y + h >= H:
                continue
            nb = (float(x), float(y), float(x + w), float(y + h))
            if any(_overlap_frac(nb, b) > 0.25 for b in boxes):
                continue
            if zone is not None and not zone[y + h // 2, x + w // 2]:
                continue
            if not _belt_ok(bg, x, y, w, h):
                continue
            _paste(bg, s_img, s_mask, x, y, rng)
            boxes.append(nb)
        if not boxes:
            continue
        if rng.random() < 0.6:
            bg, boxes = augment_once(bg, boxes, rng)
        name = f"syn_{k:05d}"
        cv2.imwrite(str(out / "images" / "train" / f"{name}.jpg"), bg, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        write_label(out / "labels" / "train" / f"{name}.txt", boxes, W, H)
        made += 1
    print(f"sinteticos: {made} imagens (comprimido ~{med_len:.0f}px)")
    return made


def _overlap_frac(a: Box, b: Box) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    area = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return ix * iy / area if area > 0 else 0.0


# ---------------------------------------------------------------- previews

def save_previews(out: Path, n: int = 12) -> None:
    prev = out / "_preview"
    prev.mkdir(parents=True, exist_ok=True)
    for prefix in ("", "aug0_", "syn_"):
        imgs = sorted(p for p in (out / "images" / "train").glob(f"{prefix}*.jpg")
                      if prefix or not p.name.startswith(("aug", "syn")))
        if not imgs:
            continue
        step = max(1, len(imgs) // n)
        tiles = []
        for p in imgs[::step][:n]:
            im = cv2.imread(str(p))
            h, w = im.shape[:2]
            for x1, y1, x2, y2 in read_label(out / "labels" / "train" / f"{p.stem}.txt", w, h):
                cv2.rectangle(im, (int(x1) - 1, int(y1) - 1), (int(x2) + 1, int(y2) + 1), (0, 0, 255), 1)
            tiles.append(cv2.resize(im, (424, 239)))
        while len(tiles) % 3:
            tiles.append(np.zeros_like(tiles[0]))
        grid = np.vstack([np.hstack(tiles[i : i + 3]) for i in range(0, len(tiles), 3)])
        cv2.imwrite(str(prev / f"{prefix or 'real_'}grid.jpg"), grid)
    print(f"previews em {prev}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", type=Path, required=True)
    ap.add_argument("--photos", type=Path, default=None, help="Fotos dos comprimidos (sprites extras)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--fps", type=float, default=6.0)
    ap.add_argument("--val-tail", type=float, default=0.2)
    ap.add_argument("--aug-copies", type=int, default=2, help="Copias variadas por frame de treino")
    ap.add_argument("--synthetic", type=int, default=1200, help="Imagens copy-paste sinteticas")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--relabel-model", type=Path, default=None, help="YOLO treinado para completar as labels")
    ap.add_argument("--relabel-conf", type=float, default=0.5)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    for sub in ("images", "labels", "_preview"):
        shutil.rmtree(args.out / sub, ignore_errors=True)
    for split in ("train", "val"):
        (args.out / "images" / split).mkdir(parents=True, exist_ok=True)
        (args.out / "labels" / split).mkdir(parents=True, exist_ok=True)

    videos = list_files(args.videos, (".mp4", ".mov", ".avi", ".mkv"))
    if not videos:
        raise SystemExit(f"Nenhum video em {args.videos}")
    photos = list_files(args.photos, (".jpg", ".jpeg", ".png")) if args.photos else []

    relabel = None
    if args.relabel_model:
        from ultralytics import YOLO

        yolo = YOLO(str(args.relabel_model))

        def relabel(frame):
            r0 = yolo.predict(frame, conf=args.relabel_conf, imgsz=640, iou=0.45, verbose=False)[0]
            if r0.boxes is None or not len(r0.boxes):
                return []
            return [tuple(map(float, b)) for b in r0.boxes.xyxy.cpu().numpy()]

    split = extract_and_label(videos, args.out, args.fps, args.val_tail, relabel)
    make_augmented(args.out, split["train"], args.aug_copies, rng)
    make_synthetic(args.out, split["train"], photos, args.synthetic, rng)

    (args.out / "data.yaml").write_text(
        f"path: {args.out.as_posix()}\ntrain: images/train\nval: images/val\nnc: 1\nnames:\n  - pill\n",
        encoding="utf-8",
    )
    n_tr = len(list((args.out / "images" / "train").glob("*.jpg")))
    n_va = len(list((args.out / "images" / "val").glob("*.jpg")))
    print(f"dataset: train={n_tr} val={n_va} -> {args.out / 'data.yaml'}")
    save_previews(args.out)


if __name__ == "__main__":
    main()
