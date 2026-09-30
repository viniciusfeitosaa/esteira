"""Camera/video → YOLO.predict → CentroidTracker → LineCounter → state."""

from __future__ import annotations

import threading
import time
from typing import Any, Optional

import cv2
import numpy as np
from ultralytics import YOLO

from .belt_roi import crop_belt_bgr
from .sources import camera_backend, describe, is_camera
from .centroid_track import CentroidTracker
from .line_count import LineCounter, TrackBox


class YoloCountPipeline:
    def __init__(
        self,
        model_path: str,
        source: str | int = 0,
        direction: str = "rtl",
        line_pos: float = 0.5,
        conf: float = 0.3,
        crop_belt: bool = False,
        roi: Optional[tuple[float, float, float, float]] = None,
        lite: bool = False,
        imgsz: Optional[int] = None,
        frame_stride: Optional[int] = None,
    ):
        self.model = YOLO(model_path)
        self.source = source
        self.conf = conf
        self.counter = LineCounter(direction=direction, line_pos=line_pos)
        # lite: tracking um pouco mais tolerante (FPS baixo)
        self.tracker = CentroidTracker(
            max_dist=72.0 if lite else 56.0,
            max_lost=35 if lite else 25,
        )
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
        # roi em fracoes do frame (x0, y0, x1, y1): so a esteira entra na inferencia
        self.roi = roi
        self._crop_box: Optional[tuple[int, int, int, int]] = None
        self.lite = lite
        # 320 deixa o comprimido (~27 px em 848 de largura) pequeno demais: contagem cai de 29 para 21/30
        self.imgsz = imgsz if imgsz is not None else (416 if lite else 640)
        self.frame_stride = frame_stride if frame_stride is not None else (2 if lite else 1)
        self._stride_i = 0
        self.jpeg_quality = 55 if lite else 80
        # step() roda numa thread do servidor; a troca de camera nao pode cair no meio dele
        self._lock = threading.Lock()
        # video de teste chegou ao fim: segura o ultimo frame e o total para comparar com o gabarito
        self.ended = False
        self.no_signal = False

    def open(self) -> None:
        self.ended = False
        self.no_signal = False
        if is_camera(self.source):
            self._cap = cv2.VideoCapture(int(self.source), camera_backend())
        else:
            self._cap = cv2.VideoCapture(self.source)
        if not self._cap.isOpened():
            raise RuntimeError(f"Nao abriu fonte: {self.source}")
        if self.lite and str(self.source).isdigit():
            # webcam: baixa resolucao para poupar RAM/CPU (Galaxy Book / 8 GB)
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self._cap.set(cv2.CAP_PROP_FPS, 15)

    def close(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None

    def switch_source(self, source: str | int) -> None:
        """Troca camera/video sem reiniciar; volta para a anterior se a nova nao abrir.

        Camera -> camera mantem o total. Video sempre comeca do inicio com total zerado.
        """
        with self._lock:
            previous = self.source
            self.close()
            self.source = source
            try:
                self.open()
                ok, _ = self._cap.read() if self._cap else (False, None)
                if not ok:
                    raise RuntimeError(f"Fonte sem imagem: {source}")
                if not is_camera(source):
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            except RuntimeError:
                self.close()
                self.source = previous
                self.open()
                raise
            # posicoes/IDs da fonte antiga nao valem para a nova
            self.tracker.reset()
            self.counter.reset()
            if not is_camera(source) or not is_camera(previous):
                self.total = 0
            self.last_frame = None
            self._boxes = []
            self._stride_i = 0

    def reset(self) -> None:
        with self._lock:
            self.counter.reset()
            self.tracker.reset()
            self.total = 0
            # zerar num video de teste recomeca o video
            if self._cap is not None and not is_camera(self.source):
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self.ended = False
                self._stride_i = 0

    def set_config(
        self,
        direction: Optional[str] = None,
        line_pos: Optional[float] = None,
        conf: Optional[float] = None,
        roi: Optional[tuple[float, float, float, float]] = None,
    ) -> None:
        if roi is not None:
            self.roi = roi if roi[2] > roi[0] and roi[3] > roi[1] else None
        if direction is not None:
            self.counter.direction = direction
        if line_pos is not None:
            self.counter.line_pos = float(line_pos)
        if conf is not None:
            self.conf = float(conf)

    def step(self) -> dict[str, Any]:
        with self._lock:
            return self._step()

    def _step(self) -> dict[str, Any]:
        if not self._cap:
            self.open()
        assert self._cap is not None

        if self.paused or self.ended:
            return self._state()

        ok, frame = self._cap.read()
        if not ok or frame is None:
            if not is_camera(self.source):
                self.ended = True
            return self._state()

        self.last_frame = frame
        self.frame_h, self.frame_w = frame.shape[:2]
        # Iriun/iVCam sem o app do celular conectado entregam uma tela preta com aviso
        self.no_signal = float(frame[::8, ::8].mean()) < 8

        # lite: processa 1 de N frames (ainda avanca tracking menos vezes)
        self._stride_i += 1
        if self.frame_stride > 1 and (self._stride_i % self.frame_stride) != 0:
            now = time.time()
            if self._last_ts:
                inst = 1.0 / max(1e-3, now - self._last_ts)
                self.fps = self.fps * 0.85 + inst * 0.15 if self.fps else inst
            self._last_ts = now
            return self._state()

        infer = frame
        ox = oy = 0
        if self.roi is not None:
            fx0, fy0, fx1, fy1 = self.roi
            x0, y0 = int(fx0 * self.frame_w), int(fy0 * self.frame_h)
            x1, y1 = int(fx1 * self.frame_w), int(fy1 * self.frame_h)
            infer = frame[y0:y1, x0:x1]
            self._crop_box = (x0, y0, x1, y1)
            ox, oy = x0, y0
        elif self.crop_belt:
            infer, (x0, y0, x1, y1) = crop_belt_bgr(frame)
            self._crop_box = (x0, y0, x1, y1)
            ox, oy = x0, y0
        else:
            self._crop_box = None

        results = self.model.predict(
            infer,
            conf=self.conf,
            imgsz=self.imgsz,
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
        for b in boxes_out:
            b["counted"] = b["id"] in self.counter.counted_ids
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
            "lite": self.lite,
            "imgsz": self.imgsz,
            "roi": list(self.roi) if self.roi else None,
            "conf": self.conf,
            "source": describe(self.source),
            "ended": self.ended,
            "no_signal": self.no_signal,
        }
