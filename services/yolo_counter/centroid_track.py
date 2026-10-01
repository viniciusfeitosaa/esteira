"""Associacao de centros entre frames com o movimento da esteira.

Todos os comprimidos andam juntos com a esteira: a cada frame estima-se um unico
deslocamento (votacao entre pares rastro->deteccao, so no sentido da contagem) e cada
deteccao e associada a posicao prevista. Sem isso, com FPS baixo ou esteira rapida o
vizinho mais proximo vira o comprimido de tras e o da frente nasce com ID novo ja
depois da linha (nunca e contado).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .line_count import TrackBox

_FORWARD = {"ltr": (1.0, 0.0), "rtl": (-1.0, 0.0), "ttb": (0.0, 1.0), "btt": (0.0, -1.0)}


@dataclass
class CentroidTracker:
    max_dist: float = 48.0
    max_lost: int = 20
    # deslocamento maximo da esteira entre dois frames processados
    max_jump: float = 240.0
    direction: Optional[str] = None
    next_id: int = 1
    # velocidade da esteira em px por unidade de dt
    vel: tuple[float, float] = (0.0, 0.0)
    # pares rastro->deteccao ja usados para medir a velocidade
    _vel_hits: int = 0
    _size: Optional[float] = None
    _prev: dict[int, tuple[float, float]] = field(default_factory=dict)
    _lost: dict[int, int] = field(default_factory=dict)
    _age: dict[int, float] = field(default_factory=dict)

    def reset(self) -> None:
        self._prev.clear()
        self._lost.clear()
        self._age.clear()
        self.next_id = 1
        self.vel = (0.0, 0.0)
        self._vel_hits = 0
        self._size = None

    def fit_pill_size(self, long_sides: list[float]) -> None:
        """Raios em funcao do tamanho do comprimido na imagem (muda com resolucao e zoom da camera).

        56 px de raio foi calibrado com comprimido de ~27 px: raio = 2x o lado maior da caixa.
        """
        if not long_sides:
            return
        s = float(np.median(long_sides))
        self._size = s if self._size is None else 0.9 * self._size + 0.1 * s
        self.max_dist = float(np.clip(2.0 * self._size, 16.0, 260.0))
        self.max_jump = 4.5 * self.max_dist

    @property
    def _vel_known(self) -> bool:
        return self._vel_hits >= 3

    def _shift_ok(self, d: np.ndarray) -> np.ndarray:
        """Mascara de deslocamentos compativeis com o sentido da esteira."""
        fwd = _FORWARD.get(self.direction or "")
        if fwd is None:
            return np.ones(d.shape[:-1], dtype=bool)
        along = d[..., 0] * fwd[0] + d[..., 1] * fwd[1]
        across = np.abs(d[..., 0] * fwd[1] - d[..., 1] * fwd[0])
        # para tras so o tremor da caixa: aceitar mais casaria cada rastro com o comprimido de tras
        return (along >= -0.1 * self.max_dist) & (across <= self.max_dist)

    def _estimate_shift(self, P: np.ndarray, gaps: np.ndarray, D: np.ndarray, dt: float) -> tuple[np.ndarray, int]:
        """Deslocamento da esteira em dt; rastros perdidos votam com o deslocamento proporcional."""
        prior = np.array(self.vel) * dt
        recent = gaps <= 3 * dt + 1e-9
        if not recent.any():
            return prior, 0
        Pr, steps = P[recent], gaps[recent] / dt
        disp = (D[None, :, :] - Pr[:, None, :]) / steps[:, None, None]
        ok = (np.hypot(disp[..., 0], disp[..., 1]) <= self.max_jump) & self._shift_ok(disp)
        cands = np.vstack([disp[ok], prior[None, :]])
        # so o tremor da caixa: tolerancia larga faz qualquer deslocamento "encaixar" numa fila regular
        tol = 0.15 * self.max_dist
        # (K, T, N): distancia de cada deteccao a cada rastro deslocado pelo candidato k
        moved = Pr[None, :, None, :] + cands[:, None, None, :] * steps[None, :, None, None]
        dist = np.linalg.norm(moved - D[None, None, :, :], axis=-1)
        support = (dist.min(axis=2) <= tol).sum(axis=1)
        # fila regular admite "andou 1 comprimido a mais": depois de aprendida, a velocidade da
        # esteira (quase constante) pesa; desviar 1/4 de max_dist dela custa um voto
        scale = 0.25 * self.max_dist if self._vel_known else self.max_jump * 4
        score = support - np.linalg.norm(cands - prior, axis=1) / scale
        k = int(np.argmax(score))
        best = int(support[k])
        if best <= 0:
            return prior, 0
        return cands[k], best

    def update(self, centers: list[tuple[float, float]], dt: float = 1.0) -> list[TrackBox]:
        dt = max(float(dt), 1e-6)
        ids = list(self._prev.keys())
        for tid in ids:
            self._age[tid] = self._age.get(tid, 0.0) + dt

        out: list[TrackBox] = []
        assigned_prev: set[int] = set()
        assigned_det: set[int] = set()
        if ids and centers:
            P = np.array([self._prev[t] for t in ids], dtype=float)
            gaps = np.array([self._age[t] for t in ids], dtype=float)
            D = np.array(centers, dtype=float)
            shift, _ = self._estimate_shift(P, gaps, D, dt)
            # rastro perdido por k frames anda k vezes o deslocamento
            pred = P + shift[None, :] * (gaps / dt)[:, None]
            dist = np.linalg.norm(pred[:, None, :] - D[None, :, :], axis=-1)
            # com a velocidade conhecida a previsao erra pouco; raio largo pegaria o vizinho
            gate = 0.6 * self.max_dist if self._vel_known else self.max_dist
            # rastro visto agora ha pouco tem prioridade: um perdido ha muitos frames, com a previsao
            # caindo sobre um comprimido ja rastreado (e contado), roubaria a deteccao e contaria de novo
            missed = np.maximum(0.0, gaps / dt - 1.0)
            # previsao de rastro perdido so vale para um trecho curto (esteira parada: sem limite)
            travel = np.hypot(shift[0], shift[1]) * gaps / dt
            trusted = travel <= self.max_jump
            penalty = 0.5 * self.max_dist * missed
            pairs = [
                (float(dist[a, b] + penalty[a]), b, ids[a], True)
                for a in range(len(ids))
                for b in range(len(centers))
                if dist[a, b] <= gate and trusted[a]
            ]
            # alternativa mais cara: casa pela ultima posicao (camera tremendo foge da previsao da
            # esteira), sem aceitar recuo, que trocaria o rastro pelo comprimido de tras
            moved = D[None, :, :] - P[:, None, :]
            still = np.linalg.norm(moved, axis=-1)
            fwd_ok = self._shift_ok(moved)
            pairs += [
                (float(still[a, b] + penalty[a] + 0.5 * self.max_dist), b, ids[a], False)
                for a in range(len(ids))
                for b in range(len(centers))
                if still[a, b] <= self.max_dist and fwd_ok[a, b]
            ]
            pairs.sort()
            row = {t: a for a, t in enumerate(ids)}
            vels: list[np.ndarray] = []
            for _, i, tid, predicted in pairs:
                if i in assigned_det or tid in assigned_prev:
                    continue
                assigned_det.add(i)
                assigned_prev.add(tid)
                a = row[tid]
                if predicted:
                    vels.append((D[i] - P[a]) / gaps[a])
                cx, cy = centers[i]
                self._prev[tid] = (cx, cy)
                self._age[tid] = 0.0
                self._lost.pop(tid, None)
                out.append(TrackBox(tid, cx, cy))
            if vels:
                v = np.median(np.array(vels), axis=0)
                if self._vel_hits == 0:
                    self.vel = (float(v[0]), float(v[1]))
                else:
                    self.vel = (0.6 * self.vel[0] + 0.4 * float(v[0]), 0.6 * self.vel[1] + 0.4 * float(v[1]))
                self._vel_hits += len(vels)

        for i, (cx, cy) in enumerate(centers):
            if i in assigned_det:
                continue
            tid = self.next_id
            self.next_id += 1
            self._prev[tid] = (cx, cy)
            self._age[tid] = 0.0
            out.append(TrackBox(tid, cx, cy))

        for tid in ids:
            if tid in assigned_prev:
                continue
            self._lost[tid] = self._lost.get(tid, 0) + 1
            if self._lost[tid] > self.max_lost:
                self._prev.pop(tid, None)
                self._lost.pop(tid, None)
                self._age.pop(tid, None)

        return out
