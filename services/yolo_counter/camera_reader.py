"""Le a camera numa thread propria e guarda so o frame mais recente.

Ler a camera no mesmo laco da inferencia deixa o driver sem leitor enquanto o YOLO
roda: o buffer enche, a imagem chega atrasada e aos saltos, e o FPS da camera cai.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

import cv2
import numpy as np


class CameraReader:
    def __init__(self, cap: cv2.VideoCapture):
        self._cap = cap
        self._cond = threading.Condition()
        self._frame: Optional[np.ndarray] = None
        self._ts = 0.0
        self._seq = 0
        self.fps = 0.0
        self.failed = False
        self._stop = False
        self._thread = threading.Thread(target=self._run, name="camera-reader", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        misses = 0
        while not self._stop:
            ok, frame = self._cap.read()
            now = time.monotonic()
            if not ok or frame is None:
                misses += 1
                # camera desconectada: para de girar em falso e avisa quem espera
                if misses > 50:
                    with self._cond:
                        self.failed = True
                        self._cond.notify_all()
                    return
                time.sleep(0.01)
                continue
            misses = 0
            with self._cond:
                if self._ts:
                    inst = 1.0 / max(1e-3, now - self._ts)
                    self.fps = self.fps * 0.9 + inst * 0.1 if self.fps else inst
                self._frame = frame
                self._ts = now
                self._seq += 1
                self._cond.notify_all()

    def latest(self) -> tuple[int, Optional[np.ndarray], float]:
        with self._cond:
            return self._seq, self._frame, self._ts

    def wait_newer(self, seq: int, timeout: float = 0.5) -> tuple[int, Optional[np.ndarray], float]:
        """Espera um frame mais novo que `seq` (o anterior ja foi processado)."""
        with self._cond:
            self._cond.wait_for(lambda: self._seq > seq or self.failed or self._stop, timeout=timeout)
            return self._seq, self._frame, self._ts

    def stop(self) -> None:
        self._stop = True
        with self._cond:
            self._cond.notify_all()
        self._thread.join(timeout=2.0)
