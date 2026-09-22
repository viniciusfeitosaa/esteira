#!/usr/bin/env python3
"""Avalia contagem YOLO + centroid track + linha nos videos da esteira."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.yolo_counter.belt_roi import crop_belt_bgr
from services.yolo_counter.centroid_track import CentroidTracker
from services.yolo_counter.line_count import LineCounter, TrackBox


def list_videos(folder: Path) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for pat in ("*.mp4", "*.MP4", "*.mov", "*.avi"):
        for p in folder.glob(pat):
            key = str(p.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
    return sorted(out, key=lambda p: p.name.lower())


def count_video(model: YOLO, path: Path, conf: float, direction: str, line_pos: float) -> dict:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"nao abriu {path}")
    counter = LineCounter(direction=direction, line_pos=line_pos)
    tracker = CentroidTracker(max_dist=56.0, max_lost=25)
    total = 0
    frames = 0
    max_visible = 0
    unique_ids: set[int] = set()
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames += 1
        h, w = frame.shape[:2]
        infer, (x0, y0, _, _) = crop_belt_bgr(frame)
        r0 = model.predict(infer, conf=conf, imgsz=640, iou=0.45, verbose=False)[0]
        centers: list[tuple[float, float]] = []
        if r0.boxes is not None and len(r0.boxes):
            for box in r0.boxes.xyxy.cpu().numpy():
                x1, y1, x2, y2 = map(float, box)
                centers.append(((x1 + x2) / 2 + x0, (y1 + y2) / 2 + y0))
        tracks = tracker.update(centers)
        for t in tracks:
            unique_ids.add(t.id)
        total += counter.count_frame(tracks, w, h)
        max_visible = max(max_visible, len(centers))
    cap.release()
    return {
        "file": path.name,
        "frames": frames,
        "counted": total,
        "max_visible": max_visible,
        "unique_ids": len(unique_ids),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", type=Path, required=True)
    ap.add_argument("--model", type=Path, default=ROOT / "models" / "pill-nano.pt")
    ap.add_argument("--conf", type=float, default=0.22)
    ap.add_argument("--direction", default="btt", choices=("ltr", "rtl", "ttb", "btt"))
    ap.add_argument("--line-pos", type=float, default=0.55)
    args = ap.parse_args()

    if not args.model.exists():
        raise SystemExit(f"modelo ausente: {args.model}")
    vids = list_videos(args.videos)
    if not vids:
        raise SystemExit(f"sem videos em {args.videos}")

    print(f"model={args.model} conf={args.conf} dir={args.direction} line={args.line_pos}")
    model = YOLO(str(args.model))
    grand = 0
    for v in vids:
        r = count_video(model, v, args.conf, args.direction, args.line_pos)
        grand += r["counted"]
        print(
            f"{r['file']}: frames={r['frames']} line={r['counted']} "
            f"unique_ids={r['unique_ids']} max_visible={r['max_visible']}"
        )
    print(f"TOTAL line_counted={grand}")


if __name__ == "__main__":
    main()
