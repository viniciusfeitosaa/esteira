#!/usr/bin/env python3
"""Run YOLO counting service: py -3.12 scripts/run_yolo_service.py --source 0

Modo lite (Galaxy Book / 8 GB RAM):
  py -3.12 scripts/run_yolo_service.py --source 0 --lite
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import uvicorn

from services.yolo_counter.server import create_app


def main():
    p = argparse.ArgumentParser(description="Esteira YOLO counter service")
    p.add_argument("--source", default="0", help="Webcam index or video path")
    p.add_argument("--model", default=None, help="Path to .pt (default pill-nano or yolov8n)")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--direction", default="rtl", choices=("ltr", "rtl", "ttb", "btt"))
    p.add_argument("--line-pos", type=float, default=0.5)
    p.add_argument("--conf", type=float, default=0.3)
    p.add_argument(
        "--roi",
        type=float,
        nargs=4,
        metavar=("X0", "Y0", "X1", "Y1"),
        default=None,
        help="Regiao da esteira em fracoes do frame, ex.: --roi 0.02 0.25 0.92 0.85",
    )
    p.add_argument(
        "--crop-belt",
        action="store_true",
        help="Recorte automatico antigo (esteira vertical, clipes de 21/09)",
    )
    p.add_argument(
        "--lite",
        action="store_true",
        help="Modo economia: imgsz 480, webcam 640x480, 1 de 2 frames em video de teste (8 GB RAM)",
    )
    args = p.parse_args()
    source: str | int = int(args.source) if str(args.source).isdigit() else args.source
    app = create_app(
        source=source,
        model=args.model,
        direction=args.direction,
        line_pos=args.line_pos,
        conf=args.conf,
        lite=args.lite,
        roi=tuple(args.roi) if args.roi else None,
        crop_belt=args.crop_belt,
    )
    mode = "LITE" if args.lite else "normal"
    print(
        f"YOLO service [{mode}] http://localhost:{args.port}/health  "
        f"ws://localhost:{args.port}/ws"
    )
    if args.lite:
        print("Lite: imgsz=480, processa 1/2 frames, preview JPEG 55, WS ~12 Hz")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
