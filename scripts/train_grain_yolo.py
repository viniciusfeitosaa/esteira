# Treino local YOLOv8n no dataset de grãos (Roboflow CC BY 4.0).
# Uso: py -3.12 scripts/train_grain_yolo.py
from pathlib import Path
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "datasets" / "rice_object_detection" / "data.yaml"
OUT_DIR = ROOT / "models"
OUT_DIR.mkdir(exist_ok=True)

def main():
    if not DATA.exists():
        raise SystemExit(f"Dataset não encontrado: {DATA}\nRode scripts/fetch_rice_datasets.py")

    # Ultralytics resolve paths relativos ao YAML; fixa path absoluto
    text = DATA.read_text(encoding="utf-8")
    abs_path = DATA.parent.as_posix()
    lines = []
    for line in text.splitlines():
        if line.startswith("path:"):
            lines.append(f"path: {abs_path}")
        else:
            lines.append(line)
    DATA.write_text("\n".join(lines) + "\n", encoding="utf-8")

    model = YOLO("yolov8n.pt")
    # CPU: subset rápido para gerar ONNX de protótipo; use GPU/Colab para treino completo
    model.train(
        data=str(DATA),
        epochs=5,
        imgsz=320,
        batch=8,
        fraction=0.15,
        project=str(ROOT / "runs"),
        name="grain-nano",
        exist_ok=True,
        patience=3,
        workers=0,
        device="cpu",
    )
    best = ROOT / "runs" / "grain-nano" / "weights" / "best.pt"
    if not best.exists():
        raise SystemExit("best.pt não gerado")

    dest_pt = OUT_DIR / "grain-nano.pt"
    dest_pt.write_bytes(best.read_bytes())
    export_model = YOLO(str(dest_pt))
    export_model.export(format="onnx", imgsz=320, simplify=True)
    onnx_src = dest_pt.with_suffix(".onnx")
    if onnx_src.exists():
        (OUT_DIR / "grain-nano.onnx").write_bytes(onnx_src.read_bytes())
    print("OK:", dest_pt, OUT_DIR / "grain-nano.onnx")

if __name__ == "__main__":
    main()
