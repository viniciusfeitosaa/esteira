#!/usr/bin/env python3
"""Run YOLO counting service: py -3.12 scripts/run_yolo_service.py --source 0"""

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
    args = p.parse_args()
    source: str | int = int(args.source) if str(args.source).isdigit() else args.source
    app = create_app(source=source, model=args.model)
    print(f"YOLO service http://localhost:{args.port}/health  ws://localhost:{args.port}/ws")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
