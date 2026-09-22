#!/usr/bin/env python3
"""Extrai frames de videos da esteira e gera labels YOLO (classe pill=0).

Otimizado para videos dificeis: glare, poeira, fragmentos irregulares, densidade.

  py -3.12 scripts/prepare_belt_dataset.py --videos C:\\Users\\vinic\\Downloads\\treinamentoIA --method classical --fps 8 --belt-only
"""
from __future__ import annotations

import argparse
import random
import re
import shutil
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT))
from services.yolo_counter.belt_roi import crop_belt_bgr, estimate_belt_x_range

DEFAULT_OUT = ROOT / "datasets" / "pills_belt"
DEFAULT_MODEL = ROOT / "models" / "pill-nano.pt"


def slug(name: str) -> str:
    s = re.sub(r"[^\w\-]+", "_", name, flags=re.UNICODE).strip("_")
    return s[:80] or "vid"


def list_videos(videos: Path) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for pat in ("*.mp4", "*.MP4", "*.mov", "*.MOV", "*.avi", "*.AVI"):
        for p in videos.glob(pat):
            key = str(p.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
    return sorted(out, key=lambda x: x.name.lower())


def extract_frames(videos: Path, raw_dir: Path, fps_target: float) -> list[Path]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    files = list_videos(videos)
    if not files:
        raise SystemExit(f"Nenhum video em {videos}")

    for vp in files:
        cap = cv2.VideoCapture(str(vp))
        if not cap.isOpened():
            print(f"aviso: nao abriu {vp.name}")
            continue
        src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        step = max(1, int(round(src_fps / fps_target)))
        stem = slug(vp.stem)
        idx = 0
        kept = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % step == 0:
                out = raw_dir / f"{stem}_{kept:05d}.jpg"
                cv2.imwrite(str(out), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
                saved.append(out)
                kept += 1
            idx += 1
        cap.release()
        print(f"{vp.name}: {kept} frames (step={step}, src_fps={src_fps:.1f})")
    return saved


def _nms_xyxy(boxes: list[tuple[float, float, float, float]], iou_thr: float = 0.35):
    if not boxes:
        return []
    arr = np.array(boxes, dtype=np.float32)
    x1, y1, x2, y2 = arr.T
    areas = (x2 - x1) * (y2 - y1)
    order = areas.argsort()[::-1]
    keep: list[int] = []
    while order.size:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        rest = order[1:]
        xx1 = np.maximum(x1[i], x1[rest])
        yy1 = np.maximum(y1[i], y1[rest])
        xx2 = np.minimum(x2[i], x2[rest])
        yy2 = np.minimum(y2[i], y2[rest])
        inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
        iou = inter / (areas[i] + areas[rest] - inter + 1e-6)
        order = rest[iou <= iou_thr]
    return [boxes[i] for i in keep]


def _components_to_boxes(
    bw: np.ndarray,
    gray_roi: np.ndarray,
    x0: int,
    y0: int,
    full_h: int,
    belt_w: int,
    min_area: int,
    max_area: int,
    min_peak: float,
) -> list[tuple[float, float, float, float]]:
    n, _, stats, _ = cv2.connectedComponentsWithStats(bw, connectivity=8)
    boxes: list[tuple[float, float, float, float]] = []
    for i in range(1, n):
        x, y, bw_, bh_, area = stats[i]
        if area < min_area or area > max_area:
            continue
        if bw_ > 0.42 * belt_w:
            continue
        if bh_ > 0.15 * full_h:
            continue
        aspect = bw_ / max(1, bh_)
        if aspect > 3.2 or aspect < 0.28:
            continue
        # glare vertical: muito alto e estreito
        if bh_ >= 4 * bw_:
            continue
        patch = gray_roi[y : y + bh_, x : x + bw_]
        if patch.size == 0:
            continue
        peak = float(patch.max())
        if peak < min_peak:
            continue
        # preenchimento: poeira/risco tem poucos pixels brancos no bbox
        fill = area / max(1, bw_ * bh_)
        if fill < 0.28:
            continue
        # media do patch deve ser bem acima do fundo tipico da esteira
        if float(patch.mean()) < min_peak * 0.55:
            continue
        boxes.append(
            (
                float(x0 + x),
                float(y0 + y),
                float(x0 + x + bw_),
                float(y0 + y + bh_),
            )
        )
    return boxes


def classical_boxes(
    bgr: np.ndarray,
    min_area: int = 12,
    max_area: int = 4500,
    bright_offset: int = 55,
    bright_thr: int | None = 125,
) -> list[tuple[float, float, float, float]]:
    """Passos: limiar alto + residual local restrito (menos glare/poeira)."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    x0, x1 = estimate_belt_x_range(gray)
    y0, y1 = int(h * 0.12), int(h * 0.88)
    roi = gray[y0:y1, x0:x1]
    belt_w = max(1, x1 - x0)
    floor = float(np.percentile(roi, 30))

    thr_hi = float(bright_thr if bright_thr is not None else min(245, floor + bright_offset))
    thr_lo = max(105.0, thr_hi - 12.0)

    boxes: list[tuple[float, float, float, float]] = []

    _, bw_hi = cv2.threshold(roi, thr_hi, 255, cv2.THRESH_BINARY)
    bw_hi = cv2.morphologyEx(bw_hi, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), 1)
    boxes += _components_to_boxes(
        bw_hi, roi, x0, y0, h, belt_w, min_area, max_area, min_peak=thr_hi + 25
    )

    blur = cv2.GaussianBlur(roi, (41, 41), 0)
    residual = cv2.subtract(roi, blur)
    _, bw_res = cv2.threshold(residual, 40, 255, cv2.THRESH_BINARY)
    _, bw_abs = cv2.threshold(roi, thr_lo, 255, cv2.THRESH_BINARY)
    bw_res = cv2.bitwise_and(bw_res, bw_abs)
    bw_res = cv2.morphologyEx(bw_res, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), 1)
    boxes += _components_to_boxes(
        bw_res, roi, x0, y0, h, belt_w, min_area, max_area, min_peak=thr_lo + 30
    )

    return _nms_xyxy(boxes, iou_thr=0.30)


def crop_belt_sample(
    bgr: np.ndarray, boxes: list[tuple[float, float, float, float]]
) -> tuple[np.ndarray, list[tuple[float, float, float, float]]]:
    crop, (x0, y0, x1, y1) = crop_belt_bgr(bgr)
    mapped: list[tuple[float, float, float, float]] = []
    for bx1, by1, bx2, by2 in boxes:
        nx1 = max(0, min(crop.shape[1] - 1, bx1 - x0))
        ny1 = max(0, min(crop.shape[0] - 1, by1 - y0))
        nx2 = max(0, min(crop.shape[1] - 1, bx2 - x0))
        ny2 = max(0, min(crop.shape[0] - 1, by2 - y0))
        if nx2 - nx1 < 2 or ny2 - ny1 < 2:
            continue
        mapped.append((nx1, ny1, nx2, ny2))
    return crop, mapped


def write_yolo_label(path: Path, boxes_xyxy: list[tuple[float, float, float, float]], w: int, h: int):
    lines: list[str] = []
    for x1, y1, x2, y2 in boxes_xyxy:
        cx = ((x1 + x2) / 2) / w
        cy = ((y1 + y2) / 2) / h
        bw = (x2 - x1) / w
        bh = (y2 - y1) / h
        if bw <= 0 or bh <= 0:
            continue
        lines.append(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def split_and_place(raw_images: Path, raw_labels: Path, out: Path, val_ratio: float, seed: int):
    imgs = sorted(raw_images.glob("*.jpg"))
    rng = random.Random(seed)
    rng.shuffle(imgs)
    n_val = max(1, int(len(imgs) * val_ratio)) if len(imgs) >= 5 else max(1, len(imgs) // 5)
    val_set = set(imgs[:n_val])
    for split in ("train", "val"):
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)
    for img in imgs:
        split = "val" if img in val_set else "train"
        shutil.copy2(img, out / "images" / split / img.name)
        lab = raw_labels / (img.stem + ".txt")
        dst = out / "labels" / split / (img.stem + ".txt")
        if lab.exists():
            shutil.copy2(lab, dst)
        else:
            dst.write_text("", encoding="utf-8")
    print(f"split: train={len(imgs)-n_val} val={n_val}")


def write_belt_yaml(out: Path) -> None:
    out.joinpath("data.yaml").write_text(
        f"""path: {out.as_posix()}
train: images/train
val: images/val
nc: 1
names:
  - pill
""",
        encoding="utf-8",
    )


def merge_into_pills(belt: Path, pills: Path) -> None:
    for split_src, split_dst in (("train", "train"), ("val", "val")):
        idir = pills / "images" / split_dst
        ldir = pills / "labels" / split_dst
        idir.mkdir(parents=True, exist_ok=True)
        ldir.mkdir(parents=True, exist_ok=True)
        for old in idir.glob("belt_*"):
            old.unlink(missing_ok=True)
        for old in ldir.glob("belt_*"):
            old.unlink(missing_ok=True)
        for img in (belt / "images" / split_src).glob("*.jpg"):
            name = f"belt_{img.name}"
            shutil.copy2(img, idir / name)
            lab = belt / "labels" / split_src / (img.stem + ".txt")
            dst_lab = ldir / f"belt_{img.stem}.txt"
            if lab.exists():
                shutil.copy2(lab, dst_lab)
            else:
                dst_lab.write_text("", encoding="utf-8")
    pills.joinpath("data.yaml").write_text(
        f"""path: {pills.as_posix()}
train: images/train
val: images/val
test: images/test
nc: 1
names:
  - pill
""",
        encoding="utf-8",
    )
    n_train = len(list((pills / "images" / "train").glob("*")))
    n_val = len(list((pills / "images" / "val").glob("*")))
    print(f"merge OK em {pills}: train={n_train} val={n_val}")


def save_debug_overlay(img_path: Path, boxes, out_path: Path):
    im = cv2.imread(str(img_path))
    if im is None:
        return
    for x1, y1, x2, y2 in boxes:
        cv2.rectangle(im, (int(x1), int(y1)), (int(x2), int(y2)), (0, 220, 80), 2)
    cv2.imwrite(str(out_path), im)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    ap.add_argument("--fps", type=float, default=8.0)
    ap.add_argument("--conf", type=float, default=0.2)
    ap.add_argument("--method", choices=("classical", "yolo"), default="classical")
    ap.add_argument("--min-area", type=int, default=10)
    ap.add_argument("--max-area", type=int, default=5500)
    ap.add_argument("--bright-offset", type=int, default=55)
    ap.add_argument("--bright-thr", type=int, default=125)
    ap.add_argument("--val-ratio", type=float, default=0.18)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--belt-only", action="store_true")
    ap.add_argument("--crop-belt", action="store_true", default=True, help="Salva crop da esteira")
    ap.add_argument("--no-crop-belt", action="store_true")
    args = ap.parse_args()
    crop_belt = not args.no_crop_belt

    for sub in ("images", "labels", "_raw", "_preview"):
        p = args.out / sub
        if p.exists():
            shutil.rmtree(p)

    raw_img = args.out / "_raw" / "images"
    raw_lab = args.out / "_raw" / "labels"
    frames = extract_frames(args.videos, raw_img, args.fps)
    print(f"total frames: {len(frames)}")

    if args.method == "classical":
        labeled = empty = total_boxes = 0
        raw_lab.mkdir(parents=True, exist_ok=True)
        # se crop: reescreve imagens raw com crop + labels no espaco do crop
        for img_path in frames:
            bgr = cv2.imread(str(img_path))
            if bgr is None:
                empty += 1
                continue
            boxes = classical_boxes(
                bgr,
                args.min_area,
                args.max_area,
                args.bright_offset,
                bright_thr=args.bright_thr,
            )
            if crop_belt:
                crop, boxes = crop_belt_sample(bgr, boxes)
                cv2.imwrite(str(img_path), crop, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
                h, w = crop.shape[:2]
            else:
                h, w = bgr.shape[:2]
            write_yolo_label(raw_lab / (img_path.stem + ".txt"), boxes, w, h)
            total_boxes += len(boxes)
            if boxes:
                labeled += 1
            else:
                empty += 1
        print(f"classical: {labeled} com boxes, {empty} vazios, {total_boxes} boxes total (crop={crop_belt})")
        dbg = args.out / "_preview"
        dbg.mkdir(parents=True, exist_ok=True)
        step = max(1, len(frames) // 8)
        for i, img in enumerate(frames[::step][:8]):
            bgr = cv2.imread(str(img))
            # ja pode estar cropped
            h, w = bgr.shape[:2]
            lab = raw_lab / (img.stem + ".txt")
            boxes = []
            if lab.exists():
                for line in lab.read_text(encoding="utf-8").splitlines():
                    p = line.split()
                    if len(p) < 5:
                        continue
                    _, cx, cy, bw, bh = map(float, p)
                    x1 = (cx - bw / 2) * w
                    y1 = (cy - bh / 2) * h
                    x2 = (cx + bw / 2) * w
                    y2 = (cy + bh / 2) * h
                    boxes.append((x1, y1, x2, y2))
            save_debug_overlay(img, boxes, dbg / f"label_preview_{i}.jpg")
        print(f"previews em {dbg}")
    else:
        from ultralytics import YOLO

        if not args.model.exists():
            raise SystemExit(f"Modelo ausente: {args.model}")
        model = YOLO(str(args.model))
        raw_lab.mkdir(parents=True, exist_ok=True)
        labeled = empty = 0
        for img_path in frames:
            results = model.predict(str(img_path), conf=args.conf, verbose=False)
            r0 = results[0]
            h, w = r0.orig_shape
            boxes = []
            if r0.boxes is not None and len(r0.boxes):
                for box in r0.boxes.xyxy.cpu().numpy():
                    boxes.append(tuple(map(float, box)))
            write_yolo_label(raw_lab / (img_path.stem + ".txt"), boxes, w, h)
            if boxes:
                labeled += 1
            else:
                empty += 1
        print(f"yolo: {labeled} com boxes, {empty} vazios")

    split_and_place(raw_img, raw_lab, args.out, args.val_ratio, args.seed)
    write_belt_yaml(args.out)

    if args.merge and not args.belt_only:
        merge_into_pills(args.out, ROOT / "datasets" / "pills")
        print("Treino mesclado: py -3.12 scripts/train_pill_yolo.py")
    else:
        print(
            "Treino so esteira: "
            "$env:PILL_DATA='datasets/pills_belt/data.yaml'; py -3.12 scripts/train_pill_yolo.py"
        )


if __name__ == "__main__":
    main()
