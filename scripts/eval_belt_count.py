#!/usr/bin/env python3
"""Avalia contagem (deteccao + centroid track + linha) nos videos da esteira.

  py -3.12 scripts/eval_belt_count.py --videos <pasta>                      # YOLO, rtl
  py -3.12 scripts/eval_belt_count.py --videos <pasta> --method classical   # referencia sem IA
  py -3.12 scripts/eval_belt_count.py --videos <pasta> --save-dir .cache/eval  # MP4 anotado
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.yolo_counter.belt_roi import crop_belt_bgr  # noqa: E402
from services.yolo_counter.centroid_track import CentroidTracker  # noqa: E402
from services.yolo_counter.line_count import LineCounter  # noqa: E402
from services.yolo_counter.white_pill import detect_white_pills  # noqa: E402


def list_videos(folder: Path) -> list[Path]:
    exts = {".mp4", ".mov", ".avi", ".mkv"}
    if folder.is_file():
        return [folder.resolve()]
    return sorted({p.resolve() for p in folder.iterdir() if p.suffix.lower() in exts}, key=lambda p: p.name.lower())


def count_video(detect, path: Path, args, save_dir: Path | None) -> dict:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"nao abriu {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    counter = LineCounter(direction=args.direction, line_pos=args.line_pos)
    tracker = CentroidTracker(max_dist=args.max_dist, max_lost=args.max_lost, direction=args.direction)
    writer = None
    total = frames = used = max_visible = 0
    unique_ids: set[int] = set()
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames += 1
        if (frames - 1) % args.stride:
            continue
        used += 1
        if args.resize:
            fh, fw = frame.shape[:2]
            frame = cv2.resize(frame, (args.resize, round(fh * args.resize / fw)))
        h, w = frame.shape[:2]
        ox = oy = 0
        infer = frame
        if args.roi:
            x0, y0 = int(args.roi[0] * w), int(args.roi[1] * h)
            x1, y1 = int(args.roi[2] * w), int(args.roi[3] * h)
            infer, ox, oy = frame[y0:y1, x0:x1], x0, y0
        elif args.crop_belt:
            infer, (ox, oy, _, _) = crop_belt_bgr(frame)
        boxes = [(x1 + ox, y1 + oy, x2 + ox, y2 + oy) for x1, y1, x2, y2 in detect(infer)]
        centers = [((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for b in boxes]
        if not args.fixed_radius:
            tracker.fit_pill_size([max(b[2] - b[0], b[3] - b[1]) for b in boxes])
        tracks = tracker.update(centers)
        unique_ids.update(t.id for t in tracks)
        total += counter.count_frame(tracks, w, h)
        max_visible = max(max_visible, len(centers))
        if save_dir is not None:
            if writer is None:
                save_dir.mkdir(parents=True, exist_ok=True)
                out = save_dir / f"{path.stem}_eval.mp4"
                writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), fps / args.stride, (w, h))
            vis = frame.copy()
            if args.direction in ("ltr", "rtl"):
                x = int(w * args.line_pos)
                cv2.line(vis, (x, 0), (x, h), (0, 220, 255), 2)
            else:
                y = int(h * args.line_pos)
                cv2.line(vis, (0, y), (w, y), (0, 220, 255), 2)
            for x1, y1, x2, y2 in boxes:
                cv2.rectangle(vis, (int(x1), int(y1)), (int(x2), int(y2)), (0, 200, 80), 2)
            cv2.putText(vis, f"contagem: {total}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
            writer.write(vis)
    cap.release()
    if writer is not None:
        writer.release()
    return {
        "file": path.name,
        "frames": frames,
        "used": used,
        "counted": total,
        "max_visible": max_visible,
        "unique_ids": len(unique_ids),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", type=Path, required=True)
    ap.add_argument("--model", type=Path, default=ROOT / "models" / "pill-nano.pt")
    ap.add_argument("--method", choices=("yolo", "classical"), default="yolo")
    ap.add_argument("--conf", type=float, default=0.3)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--direction", default="rtl", choices=("ltr", "rtl", "ttb", "btt"))
    ap.add_argument("--line-pos", type=float, default=0.5)
    ap.add_argument("--stride", type=int, default=2, help="1 de N frames (58 fps -> ~30 fps com 2)")
    ap.add_argument("--max-dist", type=float, default=56.0)
    ap.add_argument("--max-lost", type=int, default=25)
    ap.add_argument("--roi", type=float, nargs=4, default=None)
    ap.add_argument("--crop-belt", action="store_true")
    ap.add_argument("--save-dir", type=Path, default=None)
    ap.add_argument("--resize", type=int, default=None, help="largura do frame (simula outra webcam)")
    ap.add_argument("--fixed-radius", action="store_true", help="nao adapta --max-dist ao tamanho do comprimido")
    args = ap.parse_args()

    vids = list_videos(args.videos)
    if not vids:
        raise SystemExit(f"sem videos em {args.videos}")

    if args.method == "yolo":
        from ultralytics import YOLO

        if not args.model.exists():
            raise SystemExit(f"modelo ausente: {args.model}")
        model = YOLO(str(args.model))

        def detect(img):
            r0 = model.predict(img, conf=args.conf, imgsz=args.imgsz, iou=0.45, verbose=False)[0]
            if r0.boxes is None or not len(r0.boxes):
                return []
            return [tuple(map(float, b)) for b in r0.boxes.xyxy.cpu().numpy()]

        print(f"model={args.model} conf={args.conf} dir={args.direction} line={args.line_pos} stride={args.stride}")
    else:

        def detect(img):
            return detect_white_pills(img)[0]

        print(f"classical dir={args.direction} line={args.line_pos} stride={args.stride}")

    grand = 0
    for v in vids:
        r = count_video(detect, v, args, args.save_dir)
        grand += r["counted"]
        print(
            f"{r['file']}: frames={r['frames']} usados={r['used']} line={r['counted']} "
            f"unique_ids={r['unique_ids']} max_visible={r['max_visible']}"
        )
    print(f"TOTAL line_counted={grand}")


if __name__ == "__main__":
    main()
