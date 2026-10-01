#!/usr/bin/env python3
"""Dataset extra a partir de um video novo, sem mexer em datasets/pills_fixed.

Labels por concordancia: detector classico (white_pill, reescalado para o tamanho do
comprimido deste video) e o YOLO atual. O frame so entra se os dois acham as mesmas
caixas; aglomerados ambiguos, mao na cena etc. ficam de fora. Comprimidos encostados
vem dos sinteticos copy-paste feitos com recortes deste mesmo video.

  py -3.12 scripts/add_video_dataset.py --video "C:\\...\\Screen_Recording....mp4" --val-from 0.63
  -> datasets/pills_extra/ + datasets/pills_combined.yaml (pills_fixed + extra)
"""
from __future__ import annotations

import argparse
import random
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_fixedcam_dataset import (  # noqa: E402
    _iou,
    list_files,
    make_augmented,
    make_synthetic,
    save_previews,
    slug,
    write_label,
)
from services.yolo_counter.white_pill import detect_white_pills  # noqa: E402

# white_pill foi calibrado com o comprimido de ~27 px (lado maior) da webcam antiga
CLASSICAL_PILL_PX = 27.0


def _classical(frame: np.ndarray, scale: float) -> tuple[list, int]:
    small = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    boxes, unc = detect_white_pills(small)
    return [tuple(v / scale for v in b) for b in boxes], unc


def _on_border(b: tuple, w: int, h: int, g: float = 3.0) -> bool:
    return b[0] <= g or b[1] <= g or b[2] >= w - g or b[3] >= h - g


def _agree(classical: list, yolo: list[tuple], keep_conf: float, w: int, h: int) -> list | None:
    """Caixas finais (do YOLO, mais justas) se os dois concordam; None se nao."""
    # parafusos/roletes nos cantos sao brancos para o classico; comprimido cortado na borda
    # teria label incompleta: frame com YOLO confiante na borda fica de fora
    if any(cf >= keep_conf and _on_border(b, w, h) for b, cf in yolo):
        return None
    classical = [c for c in classical if not _on_border(c, w, h)]
    used: set[int] = set()
    out = []
    for c in classical:
        best, bi = 0.0, -1
        for i, (b, _) in enumerate(yolo):
            if i not in used and (v := _iou(c, b)) > best:
                best, bi = v, i
        if best < 0.4:
            return None
        used.add(bi)
        out.append(yolo[bi][0])
    # deteccao confiante do YOLO que o classico nao viu: um dos dois errou
    if any(i not in used and cf >= keep_conf for i, (_, cf) in enumerate(yolo)):
        return None
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=Path, required=True)
    ap.add_argument("--photos", type=Path, default=None)
    ap.add_argument("--model", type=Path, default=ROOT / "models" / "pill-nano.pt")
    ap.add_argument("--out", type=Path, default=ROOT / "datasets" / "pills_extra")
    ap.add_argument("--base", type=Path, default=ROOT / "datasets" / "pills_fixed")
    ap.add_argument("--fps", type=float, default=6.0)
    ap.add_argument("--val-from", type=float, default=0.8, help="fracao do video a partir da qual vai para val")
    ap.add_argument("--empty-keep", type=float, default=0.15, help="fracao dos frames sem comprimido mantidos")
    ap.add_argument("--keep-conf", type=float, default=0.45)
    ap.add_argument("--aug-copies", type=int, default=2)
    ap.add_argument("--synthetic", type=int, default=500)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    for sub in ("images", "labels", "_preview"):
        shutil.rmtree(args.out / sub, ignore_errors=True)
    for split in ("train", "val"):
        (args.out / "images" / split).mkdir(parents=True, exist_ok=True)
        (args.out / "labels" / split).mkdir(parents=True, exist_ok=True)

    model = YOLO(str(args.model))
    cap = cv2.VideoCapture(str(args.video))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, int(round((cap.get(cv2.CAP_PROP_FPS) or 30.0) / args.fps)))
    val_from = int(n * args.val_from)
    stem = slug(args.video.stem)

    scale = None
    sizes: list[float] = []
    imgs: dict[str, list[Path]] = {"train": [], "val": []}
    stats = {"sampled": 0, "pills": 0, "empty": 0, "disagree": 0, "boxes": 0}
    idx = -1
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        idx += 1
        if idx % step:
            continue
        stats["sampled"] += 1
        r0 = model.predict(frame, conf=0.25, imgsz=640, iou=0.45, verbose=False)[0]
        yolo = []
        if r0.boxes is not None and len(r0.boxes):
            yolo = [(tuple(map(float, b)), float(c)) for b, c in zip(r0.boxes.xyxy.cpu().numpy(), r0.boxes.conf.cpu().numpy())]
        sizes += [max(b[2] - b[0], b[3] - b[1]) for b, c in yolo if c >= 0.7]
        if scale is None:
            if len(sizes) < 20:
                continue
            scale = min(1.0, CLASSICAL_PILL_PX / float(np.median(sizes)))
            print(f"comprimido ~{np.median(sizes):.0f}px -> classico em escala {scale:.2f}")
        classical, unc = _classical(frame, scale)
        fh, fw = frame.shape[:2]
        boxes = None if unc else _agree(classical, yolo, args.keep_conf, fw, fh)
        if boxes is None:
            stats["disagree"] += 1
            continue
        if not boxes:
            if rng.random() > args.empty_keep:
                continue
            stats["empty"] += 1
        else:
            stats["pills"] += 1
        split = "val" if idx >= val_from else "train"
        name = f"{stem}_{idx:05d}"
        img = args.out / "images" / split / f"{name}.jpg"
        cv2.imwrite(str(img), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        h, w = frame.shape[:2]
        write_label(args.out / "labels" / split / f"{name}.txt", boxes, w, h)
        imgs[split].append(img)
        stats["boxes"] += len(boxes)
    cap.release()
    print(f"{stats} train={len(imgs['train'])} val={len(imgs['val'])}")

    photos = list_files(args.photos, (".jpg", ".jpeg", ".png")) if args.photos else []
    make_augmented(args.out, imgs["train"], args.aug_copies, rng)
    with_pills = [p for p in imgs["train"] if (args.out / "labels" / "train" / f"{p.stem}.txt").read_text().strip()]
    make_synthetic(args.out, with_pills, photos, args.synthetic, rng)
    save_previews(args.out)

    combined = ROOT / "datasets" / "pills_combined.yaml"
    b, e = args.base.as_posix(), args.out.as_posix()
    combined.write_text(
        f"train:\n  - {b}/images/train\n  - {e}/images/train\nval:\n  - {b}/images/val\n  - {e}/images/val\n"
        "nc: 1\nnames:\n  - pill\n",
        encoding="utf-8",
    )
    print(f"-> {combined}")


if __name__ == "__main__":
    main()
