from dataclasses import dataclass, field


@dataclass
class TrackBox:
    id: int
    cx: float
    cy: float


@dataclass
class LineCounter:
    direction: str = "ltr"
    line_pos: float = 0.5
    keep_lost: int = 30
    counted_ids: set = field(default_factory=set)
    _prev: dict = field(default_factory=dict)
    _miss: dict = field(default_factory=dict)

    def reset(self) -> None:
        self.counted_ids.clear()
        self._prev.clear()
        self._miss.clear()

    def _axis(self, x: float, y: float) -> float:
        return x if self.direction in ("ltr", "rtl") else y

    def _line(self, w: int, h: int) -> float:
        return (w if self.direction in ("ltr", "rtl") else h) * self.line_pos

    def _crossed(self, prev: float, curr: float, line: float) -> bool:
        if self.direction in ("ltr", "ttb"):
            return prev < line <= curr
        return prev > line >= curr

    def count_frame(self, tracks: list, frame_w: int, frame_h: int) -> int:
        line = self._line(frame_w, frame_h)
        delta = 0
        seen = set()
        for t in tracks:
            seen.add(t.id)
            curr = self._axis(t.cx, t.cy)
            prev_xy = self._prev.get(t.id)
            if prev_xy is not None and t.id not in self.counted_ids:
                prev = self._axis(prev_xy[0], prev_xy[1])
                if self._crossed(prev, curr, line):
                    self.counted_ids.add(t.id)
                    delta += 1
            self._prev[t.id] = (t.cx, t.cy)
            self._miss.pop(t.id, None)
        # track sumido por alguns frames (reflexo, oclusao) mantem a ultima posicao
        for k in list(self._prev.keys()):
            if k not in seen:
                self._miss[k] = self._miss.get(k, 0) + 1
                if self._miss[k] > self.keep_lost:
                    self._prev.pop(k, None)
                    self._miss.pop(k, None)
        return delta
