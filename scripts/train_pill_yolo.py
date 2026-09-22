#!/usr/bin/env python3
"""Train YOLOv8n on datasets/pills → models/pill-nano.pt

CPU bootstrap: epochs curtos.
Fine-tune completo: PILL_TRAIN_FULL=1
Usa models/pill-nano.pt como base se existir (adaptacao ao dominio esteira).
Override YAML: PILL_DATA=datasets/pills_belt/data.yaml
"""

from __future__ import annotations

import os
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "datasets" / "pills" / "data.yaml"
OUT = ROOT / "models"
EXISTING = OUT / "pill-nano.pt"


def main():
    data = Path(os.environ.get("PILL_DATA", str(DATA)))
    if not data.exists():
        raise SystemExit(
            f"Falta {data}\n"
            "Rode: py -3.12 scripts/fetch_pill_datasets.py\n"
            "ou: py -3.12 scripts/prepare_belt_dataset.py --videos <pasta> --merge\n"
            "Ver docs/CAPTURE-PILLS.md"
        )
    text = data.read_text(encoding="utf-8")
    abs_path = data.parent.as_posix()
    lines = []
    for line in text.splitlines():
        if line.startswith("path:"):
            lines.append(f"path: {abs_path}")
        else:
            lines.append(line)
    data.write_text("\n".join(lines) + "\n", encoding="utf-8")

    OUT.mkdir(exist_ok=True)
    full = os.environ.get("PILL_TRAIN_FULL", "").strip() in {"1", "true", "yes"}
    weights = str(EXISTING) if EXISTING.exists() else "yolov8n.pt"
    print(f"base weights: {weights}")
    model = YOLO(weights)
    if full:
        model.train(
            data=str(data),
            epochs=40,
            imgsz=640,
            batch=4,
            project=str(ROOT / "runs"),
            name="pill-nano",
            exist_ok=True,
            patience=12,
            workers=0,
        )
    else:
        model.train(
            data=str(data),
            epochs=30,
            imgsz=416,
            batch=4,
            project=str(ROOT / "runs"),
            name="pill-nano",
            exist_ok=True,
            patience=8,
            workers=0,
            device="cpu",
            hsv_v=0.3,
            degrees=5.0,
            translate=0.05,
            scale=0.3,
            fliplr=0.0,
            mosaic=0.8,
        )
    best = ROOT / "runs" / "pill-nano" / "weights" / "best.pt"
    if not best.exists():
        raise SystemExit("best.pt nao gerado")
    dest = OUT / "pill-nano.pt"
    dest.write_bytes(best.read_bytes())
    print("OK:", dest)


if __name__ == "__main__":
    main()
