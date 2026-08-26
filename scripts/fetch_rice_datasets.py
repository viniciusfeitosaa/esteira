"""
Busca / prepara datasets de rice grain para YOLO.
- Preferência: Roboflow rice_object_detection (já em YOLO) via mirror GitHub DeeThunder
- Alternativa: Kaggle (requer ~/.kaggle/kaggle.json)
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASETS = ROOT / "datasets"
TARGET = DATASETS / "rice_object_detection"

ROBOFLOW_MIRROR = "https://github.com/DeeThunder/Rice-object-detection-esp32-cam.git"
KAGGLE_OD = "alikhalilit98/rice-image-dataset-for-object-detection"


def write_yaml(dest: Path) -> None:
    yaml = dest / "data.yaml"
    yaml.write_text(
        """path: {path}
train: train/images
val: valid/images
test: test/images
nc: 7
names:
  - Broken
  - Chalky
  - Clean
  - Damaged
  - Discolored
  - Immature
  - Organic Foreign Matters
""".format(path=dest.as_posix()),
        encoding="utf-8",
    )


def fetch_roboflow_mirror() -> bool:
    tmp = Path(subprocess.check_output(["powershell", "-NoProfile", "-Command", "$env:TEMP"], text=True).strip()) / "rice-esp32-fetch"
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    print("Clonando mirror Roboflow (CC BY 4.0)…")
    subprocess.check_call(["git", "clone", "--depth", "1", ROBOFLOW_MIRROR, str(tmp)])
    src = tmp / "dataset" / "rice_object_detection.v1i.yolov8"
    if not src.exists():
        print("Estrutura inesperada no mirror")
        return False
    if TARGET.exists():
        shutil.rmtree(TARGET)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, TARGET)
    write_yaml(TARGET)
    n = len(list((TARGET / "train" / "images").glob("*")))
    print(f"OK: {TARGET} ({n} imagens train)")
    return True


def fetch_kaggle() -> bool:
    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    if not kaggle_json.exists():
        print("Sem ~/.kaggle/kaggle.json — pulando Kaggle OD (75k).")
        return False
    out = DATASETS / "rice_od_kaggle"
    out.mkdir(parents=True, exist_ok=True)
    print("Baixando Kaggle object detection…")
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "kaggle",
            "datasets",
            "download",
            "-d",
            KAGGLE_OD,
            "-p",
            str(out),
            "--unzip",
        ]
    )
    print(f"OK: {out}")
    return True


def main() -> None:
    DATASETS.mkdir(exist_ok=True)
    ok = False
    if TARGET.exists() and (TARGET / "train" / "images").exists():
        write_yaml(TARGET)
        print(f"Dataset já presente: {TARGET}")
        ok = True
    else:
        try:
            ok = fetch_roboflow_mirror()
        except Exception as e:
            print("Falha mirror:", e)
    try:
        fetch_kaggle()
    except Exception as e:
        print("Kaggle opcional falhou:", e)
    if not ok:
        raise SystemExit(1)
    print("\nPróximo: py -3.12 scripts/train_grain_yolo.py")


if __name__ == "__main__":
    main()
