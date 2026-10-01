#!/usr/bin/env python3
"""Train YOLOv8n on datasets/pills → models/pill-nano.pt

CPU bootstrap: epochs curtos.
Fine-tune completo: PILL_TRAIN_FULL=1
Usa models/pill-nano.pt como base se existir (adaptacao ao dominio esteira).
Override YAML: PILL_DATA=datasets/pills_fixed/data.yaml
Overrides opcionais: PILL_EPOCHS, PILL_IMGSZ, PILL_BATCH, PILL_BASE (pesos iniciais)
PILL_RUN=nome (pasta em runs/), PILL_SAVE_PERIOD=1 (checkpoint por epoca: escolher pela
contagem com eval_belt_count.py, nao pelo mAP), PILL_NO_INSTALL=1 (nao troca models/pill-nano.pt)
Antes de sobrescrever, o modelo anterior e salvo em models/pill-nano.prev.pt
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "datasets" / "pills" / "data.yaml"
OUT = ROOT / "models"
EXISTING = OUT / "pill-nano.pt"


def _env_int(name: str, default: int) -> int:
    v = os.environ.get(name, "").strip()
    return int(v) if v else default


def main():
    data = Path(os.environ.get("PILL_DATA", str(DATA)))
    if not data.exists():
        raise SystemExit(
            f"Falta {data}\n"
            "Rode: py -3.12 scripts/prepare_fixedcam_dataset.py --videos <pasta>\n"
            "ou: py -3.12 scripts/prepare_belt_dataset.py --videos <pasta> --merge\n"
            "Ver docs/CAPTURE-PILLS.md"
        )
    text = data.read_text(encoding="utf-8")
    if "path:" in text:
        abs_path = data.parent.as_posix()
        lines = [f"path: {abs_path}" if ln.startswith("path:") else ln for ln in text.splitlines()]
        data.write_text("\n".join(lines) + "\n", encoding="utf-8")
    run = os.environ.get("PILL_RUN", "").strip() or "pill-nano"

    OUT.mkdir(exist_ok=True)
    full = os.environ.get("PILL_TRAIN_FULL", "").strip() in {"1", "true", "yes"}
    weights = os.environ.get("PILL_BASE", "").strip() or (str(EXISTING) if EXISTING.exists() else "yolov8n.pt")
    print(f"base weights: {weights}")
    model = YOLO(weights)
    common = dict(
        data=str(data),
        project=str(ROOT / "runs"),
        name=run,
        exist_ok=True,
        workers=0,
        save_period=_env_int("PILL_SAVE_PERIOD", -1),
        close_mosaic=_env_int("PILL_CLOSE_MOSAIC", 10),
        hsv_v=0.3,
        degrees=5.0,
        translate=0.05,
        scale=0.3,
        fliplr=0.5,
        mosaic=0.8,
    )
    if full:
        model.train(
            epochs=_env_int("PILL_EPOCHS", 40),
            imgsz=_env_int("PILL_IMGSZ", 640),
            batch=_env_int("PILL_BATCH", 8),
            patience=12,
            **common,
        )
    else:
        model.train(
            epochs=_env_int("PILL_EPOCHS", 30),
            imgsz=_env_int("PILL_IMGSZ", 416),
            batch=_env_int("PILL_BATCH", 4),
            patience=8,
            device="cpu",
            **common,
        )
    best = ROOT / "runs" / run / "weights" / "best.pt"
    if not best.exists():
        raise SystemExit("best.pt nao gerado")
    if os.environ.get("PILL_NO_INSTALL", "").strip() in {"1", "true", "yes"}:
        print("PILL_NO_INSTALL: modelo em", best)
        return
    dest = OUT / "pill-nano.pt"
    if dest.exists():
        shutil.copy2(dest, OUT / "pill-nano.prev.pt")
    dest.write_bytes(best.read_bytes())
    print("OK:", dest)


if __name__ == "__main__":
    main()
