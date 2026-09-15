"""Camera/video → YOLO.track → LineCounter → state dict."""

from __future__ import annotations

import time
from typing import Any, Optional

import cv2
import numpy as np
from ultralytics import YOLO

from .line_count import LineCounter, TrackBox


class YoloCountPipeline:
    def __init__(
        self,
        model_path: str,
        source: str | int = 0,
        direction: str = "ltr",
        line_pos: float = 0.5,
        conf: float = 0.35,
    ):
        self.model = YOLO(model_path)
        self.source = source
        self.conf = conf
        self.counter = LineCounter(direction=direction, line_pos=line_pos)
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

    def open(self) -> None:
        src = int(self.source) if str(self.source).isdigit() else self.source
        self._cap = cv2.VideoCapture(src)
        if not self._cap.isOpened():
            raise RuntimeError(f"Não abriu fonte: {self.source}")

    def close(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None

    def reset(self) -> None:
        self.counter.reset()
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
            # loop video files
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._cap.read()
            if not ok or frame is None:
                return self._state()

        self.last_frame = frame
        self.frame_h, self.frame_w = frame.shape[:2]
        results = self.model.track(
            frame,
            persist=True,
            conf=self.conf,
            verbose=False,
            tracker="bytetrack.yaml",
        )
        tracks: list[TrackBox] = []
        boxes_out: list[dict[str, Any]] = []
        r0 = results[0]
        if r0.boxes is not None and len(r0.boxes):
            xyxy = r0.boxes.xyxy.cpu().numpy()
            confs = r0.boxes.conf.cpu().numpy()
            ids = (
                r0.boxes.id.cpu().numpy().astype(int)
                if r0.boxes.id is not None
                else np.arange(len(xyxy))
            )
            for i, box in enumerate(xyxy):
                x1, y1, x2, y2 = map(float, box)
                tid = int(ids[i])
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2
                tracks.append(TrackBox(tid, cx, cy))
                boxes_out.append(
                    {
                        "id": tid,
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2,
                        "conf": float(confs[i]),
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
