#!/usr/bin/env python3
"""Train YOLOv8n on datasets/pills → models/pill-nano.pt"""

from pathlib import Path
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "datasets" / "pills" / "data.yaml"
OUT = ROOT / "models"


def main():
    if not DATA.exists():
        raise SystemExit(
            f"Falta {DATA}\nCopie data.yaml.example → data.yaml e adicione imagens/labels.\n"
            "Ver docs/CAPTURE-PILLS.md"
        )
    text = DATA.read_text(encoding="utf-8")
    abs_path = DATA.parent.as_posix()
    lines = []
    for line in text.splitlines():
        if line.startswith("path:"):
            lines.append(f"path: {abs_path}")
        else:
            lines.append(line)
    DATA.write_text("\n".join(lines) + "\n", encoding="utf-8")

    OUT.mkdir(exist_ok=True)
    model = YOLO("yolov8n.pt")
    model.train(
        data=str(DATA),
        epochs=50,
        imgsz=640,
        batch=8,
        project=str(ROOT / "runs"),
        name="pill-nano",
        exist_ok=True,
        patience=15,
    )
    best = ROOT / "runs" / "pill-nano" / "weights" / "best.pt"
    if not best.exists():
        raise SystemExit("best.pt não gerado")
    dest = OUT / "pill-nano.pt"
    dest.write_bytes(best.read_bytes())
    print("OK:", dest)


if __name__ == "__main__":
    main()
