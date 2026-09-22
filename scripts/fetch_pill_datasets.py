#!/usr/bin/env python3
"""Bootstrap dataset de comprimidos (RF100 pills, CC BY 4.0) via Hugging Face.

Baixa LibreYOLO/pills-sxdht, remapeia todas as classes → `pill` (id 0)
e monta datasets/pills no layout do projeto.

Uso: py -3.12 scripts/fetch_pill_datasets.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "datasets" / "pills"
HF_REPO = "LibreYOLO/pills-sxdht"


def _remap_labels(src_labels: Path, dst_labels: Path) -> int:
    dst_labels.mkdir(parents=True, exist_ok=True)
    n = 0
    for lab in src_labels.glob("*.txt"):
        lines_out = []
        for line in lab.read_text(encoding="utf-8").splitlines():
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            # class_id x y w h  →  sempre pill=0
            parts[0] = "0"
            lines_out.append(" ".join(parts))
        dst_labels.joinpath(lab.name).write_text(
            "\n".join(lines_out) + ("\n" if lines_out else ""),
            encoding="utf-8",
        )
        n += 1
    return n


def _copy_images(src_images: Path, dst_images: Path) -> int:
    dst_images.mkdir(parents=True, exist_ok=True)
    n = 0
    for img in src_images.iterdir():
        if img.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
            continue
        shutil.copy2(img, dst_images / img.name)
        n += 1
    return n


def write_yaml(dest: Path) -> None:
    dest.joinpath("data.yaml").write_text(
        f"""path: {dest.as_posix()}
train: images/train
val: images/val
test: images/test
nc: 1
names:
  - pill
""",
        encoding="utf-8",
    )


def main() -> None:
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("Instalando huggingface_hub…")
        import subprocess

        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "huggingface_hub", "-q"]
        )
        from huggingface_hub import snapshot_download

    cache = ROOT / ".cache" / "hf-pills-sxdht"
    print(f"Baixando {HF_REPO} (CC BY 4.0)...")
    src = Path(
        snapshot_download(
            repo_id=HF_REPO,
            repo_type="dataset",
            local_dir=str(cache),
        )
    )

    # limpa imagens/labels anteriores, preserva README
    for sub in ("images", "labels"):
        p = DEST / sub
        if p.exists():
            shutil.rmtree(p)

    splits = {
        "train": "train",
        "valid": "val",
        "test": "test",
    }
    total_img = 0
    total_lab = 0
    for src_split, dst_split in splits.items():
        simg = src / src_split / "images"
        slab = src / src_split / "labels"
        if not simg.exists():
            print(f"aviso: sem {src_split}/images")
            continue
        total_img += _copy_images(simg, DEST / "images" / dst_split)
        if slab.exists():
            total_lab += _remap_labels(slab, DEST / "labels" / dst_split)

    write_yaml(DEST)
    print(f"OK: {DEST} - {total_img} imagens, {total_lab} labels -> classe unica pill")
    print("Atribuicao: Roboflow 100 / Mohamed Attia - https://universe.roboflow.com/roboflow-100/pills-sxdht")
    print("Proximo: py -3.12 scripts/train_pill_yolo.py")


if __name__ == "__main__":
    main()
