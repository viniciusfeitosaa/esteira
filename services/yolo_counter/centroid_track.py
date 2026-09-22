"""Associacao simples de centros entre frames (estavel para objetos pequenos)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .line_count import TrackBox


@dataclass
class CentroidTracker:
    max_dist: float = 48.0
    max_lost: int = 20
    next_id: int = 1
    _prev: dict[int, tuple[float, float]] = field(default_factory=dict)
    _lost: dict[int, int] = field(default_factory=dict)

    def reset(self) -> None:
        self._prev.clear()
        self._lost.clear()
        self.next_id = 1

    def update(self, centers: list[tuple[float, float]]) -> list[TrackBox]:
        if not centers:
            dead = []
            for tid in list(self._lost.keys()):
                self._lost[tid] = self._lost.get(tid, 0) + 1
                if self._lost[tid] > self.max_lost:
                    dead.append(tid)
            for tid in dead:
                self._prev.pop(tid, None)
                self._lost.pop(tid, None)
            # tambem marca todos os vivos como lost+1
            for tid in list(self._prev.keys()):
                if tid not in self._lost:
                    self._lost[tid] = 1
            return []

        ids = list(self._prev.keys())
        assigned_prev: set[int] = set()
        assigned_det: set[int] = set()
        pairs: list[tuple[float, int, int]] = []
        for i, (cx, cy) in enumerate(centers):
            for tid in ids:
                px, py = self._prev[tid]
                d = float(np.hypot(cx - px, cy - py))
                if d <= self.max_dist:
                    pairs.append((d, i, tid))
        pairs.sort()
        out: list[TrackBox] = []
        for d, i, tid in pairs:
            if i in assigned_det or tid in assigned_prev:
                continue
            assigned_det.add(i)
            assigned_prev.add(tid)
            cx, cy = centers[i]
            self._prev[tid] = (cx, cy)
            self._lost.pop(tid, None)
            out.append(TrackBox(tid, cx, cy))

        for i, (cx, cy) in enumerate(centers):
            if i in assigned_det:
                continue
            tid = self.next_id
            self.next_id += 1
            self._prev[tid] = (cx, cy)
            out.append(TrackBox(tid, cx, cy))

        for tid in ids:
            if tid in assigned_prev:
                continue
            self._lost[tid] = self._lost.get(tid, 0) + 1
            if self._lost[tid] > self.max_lost:
                self._prev.pop(tid, None)
                self._lost.pop(tid, None)

        return out
