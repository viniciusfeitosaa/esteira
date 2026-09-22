"""Camera/video → YOLO.predict → CentroidTracker → LineCounter → state."""

from __future__ import annotations

import time
from typing import Any, Optional

import cv2
import numpy as np
from ultralytics import YOLO

from .belt_roi import crop_belt_bgr
from .centroid_track import CentroidTracker
from .line_count import LineCounter, TrackBox


class YoloCountPipeline:
    def __init__(
        self,
        model_path: str,
        source: str | int = 0,
        direction: str = "btt",
        line_pos: float = 0.55,
        conf: float = 0.22,
        crop_belt: bool = True,
    ):
        self.model = YOLO(model_path)
        self.source = source
        self.conf = conf
        self.counter = LineCounter(direction=direction, line_pos=line_pos)
        self.tracker = CentroidTracker(max_dist=56.0, max_lost=25)
        self.total = 0
        self.fps = 0.0
        self._cap: Optional[cv2.VideoCapture] = None
        self._last_ts = 0.0
        self._boxes: list[dict[str, Any]] = []
        self.paused = False
        self.frame_w = 640
        self.frame_h = 480
        self.last_frame: Optional[np.ndarray] = None
        self.model_warning: Optional[str] = None
        self.crop_belt = crop_belt
        self._crop_box: Optional[tuple[int, int, int, int]] = None

    def open(self) -> None:
        src = int(self.source) if str(self.source).isdigit() else self.source
        self._cap = cv2.VideoCapture(src)
        if not self._cap.isOpened():
            raise RuntimeError(f"Nao abriu fonte: {self.source}")

    def close(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None

    def reset(self) -> None:
        self.counter.reset()
        self.tracker.reset()
        self.total = 0

    def set_config(
        self,
        direction: Optional[str] = None,
        line_pos: Optional[float] = None,
        conf: Optional[float] = None,
    ) -> None:
        if direction is not None:
            self.counter.direction = direction
        if line_pos is not None:
            self.counter.line_pos = float(line_pos)
        if conf is not None:
            self.conf = float(conf)

    def step(self) -> dict[str, Any]:
        if not self._cap:
            self.open()
        assert self._cap is not None

        if self.paused:
            return self._state()

        ok, frame = self._cap.read()
        if not ok or frame is None:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._cap.read()
            if not ok or frame is None:
                return self._state()

        self.last_frame = frame
        self.frame_h, self.frame_w = frame.shape[:2]

        infer = frame
        ox = oy = 0
        if self.crop_belt:
            infer, (x0, y0, x1, y1) = crop_belt_bgr(frame)
            self._crop_box = (x0, y0, x1, y1)
            ox, oy = x0, y0
        else:
            self._crop_box = None

        results = self.model.predict(
            infer,
            conf=self.conf,
            imgsz=640,
            iou=0.45,
            verbose=False,
        )
        centers: list[tuple[float, float]] = []
        raw_boxes: list[tuple[float, float, float, float, float]] = []
        r0 = results[0]
        if r0.boxes is not None and len(r0.boxes):
            xyxy = r0.boxes.xyxy.cpu().numpy()
            confs = r0.boxes.conf.cpu().numpy()
            for i, box in enumerate(xyxy):
                x1, y1, x2, y2 = map(float, box)
                X1, Y1, X2, Y2 = x1 + ox, y1 + oy, x2 + ox, y2 + oy
                centers.append(((X1 + X2) / 2, (Y1 + Y2) / 2))
                raw_boxes.append((X1, Y1, X2, Y2, float(confs[i])))

        tracks = self.tracker.update(centers)
        # associa track id ao box mais proximo
        boxes_out: list[dict[str, Any]] = []
        used = set()
        for t in tracks:
            best_i = None
            best_d = 1e9
            for i, (X1, Y1, X2, Y2, conf) in enumerate(raw_boxes):
                if i in used:
                    continue
                cx = (X1 + X2) / 2
                cy = (Y1 + Y2) / 2
                d = (cx - t.cx) ** 2 + (cy - t.cy) ** 2
                if d < best_d:
                    best_d = d
                    best_i = i
            if best_i is None:
                continue
            used.add(best_i)
            X1, Y1, X2, Y2, conf = raw_boxes[best_i]
            boxes_out.append(
                {
                    "id": t.id,
                    "x1": X1,
                    "y1": Y1,
                    "x2": X2,
                    "y2": Y2,
                    "conf": conf,
                }
            )

        delta = self.counter.count_frame(tracks, self.frame_w, self.frame_h)
        self.total += delta
        self._boxes = boxes_out

        now = time.time()
        if self._last_ts:
            inst = 1.0 / max(1e-3, now - self._last_ts)
            self.fps = self.fps * 0.85 + inst * 0.15 if self.fps else inst
        self._last_ts = now
        return self._state()

    def _state(self) -> dict[str, Any]:
        return {
            "type": "state",
            "total": self.total,
            "fps": round(self.fps, 1),
            "boxes": self._boxes,
            "line_pos": self.counter.line_pos,
            "direction": self.counter.direction,
            "frame_w": self.frame_w,
            "frame_h": self.frame_h,
            "paused": self.paused,
            "model_warning": self.model_warning,
        }
