# YOLO Pill Counting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Contar comprimidos/cápsulas com YOLO como motor principal, tracking + linha, meta de erro ≤ 0,5% em lote conhecido.

**Architecture:** Serviço Python no PC (Ultralytics detect/track + contagem por linha) expõe WebSocket/HTTP; browser mostra overlay e modo Validação. Dataset `pill` próprio; clássico/assistente deixam de ser o cérebro.

**Tech Stack:** Python 3.12, Ultralytics YOLO, FastAPI/WebSockets, HTML/JS existente, Node HTTPS opcional para UI.

**Spec:** `docs/superpowers/specs/2026-09-14-yolo-pill-counting-design.md`

## Global Constraints

- 1 classe: `pill` (sem SKU/nome no MVP)
- Aceite: `|contado − N| / N ≤ 0,005` com N ≥ 200
- Inferência de produção no **PC**; browser é UI
- Modelo arroz `grain-nano` não é o motor de medicamentos
- Responder UI e commits em português/inglês conforme estilo do repo (mensagens de commit em inglês, curtas)
- Não garantir 0,5% só em Pages/Render sem PC

## File map

| Path | Responsibility |
|------|----------------|
| `docs/CAPTURE-PILLS.md` | Checklist de captura/anotação |
| `datasets/pills/README.md` | Layout YOLO do dataset |
| `services/yolo_counter/` | Pacote Python: track, line count, API |
| `services/yolo_counter/line_count.py` | Contagem por cruzamento de ID |
| `services/yolo_counter/server.py` | FastAPI + WebSocket + MJPEG/JPEG |
| `scripts/train_pill_yolo.py` | Treino Ultralytics `pill` |
| `scripts/validate_lot.py` | CLI: esperado N vs contado |
| `tests/test_line_count.py` | Testes unitários da contagem |
| `app.js` / `index.html` | Modo YOLO-first + Validação |
| `README.md` / `MAPA-DE-BORDO.md` | Alinhar docs ao novo fluxo |

---

### Task 1: Contagem por linha (puro, testável)

**Files:**
- Create: `services/yolo_counter/__init__.py`
- Create: `services/yolo_counter/line_count.py`
- Create: `tests/test_line_count.py`
- Create: `requirements-yolo.txt`

**Interfaces:**
- Produces: `LineCounter.count_frame(tracks: list[TrackBox], frame_w: int, frame_h: int) -> int` onde retorno é **delta** (novos cruzamentos neste frame)
- `TrackBox`: `id: int, cx: float, cy: float` (centro em pixels)
- Config: `direction: str` (`ltr|rtl|ttb|btt`), `line_pos: float` (0–1)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_line_count.py
from services.yolo_counter.line_count import LineCounter, TrackBox

def test_ltr_counts_once_when_crossing():
    c = LineCounter(direction="ltr", line_pos=0.5)
    w, h = 200, 100
    # approaching from left
    d0 = c.count_frame([TrackBox(1, 80, 50)], w, h)
    assert d0 == 0
    d1 = c.count_frame([TrackBox(1, 110, 50)], w, h)
    assert d1 == 1
    d2 = c.count_frame([TrackBox(1, 150, 50)], w, h)
    assert d2 == 0  # same id not recounted

def test_reset_clears_counted_ids():
    c = LineCounter(direction="ltr", line_pos=0.5)
    c.count_frame([TrackBox(1, 80, 50)], 200, 100)
    c.count_frame([TrackBox(1, 110, 50)], 200, 100)
    c.reset()
    d = c.count_frame([TrackBox(1, 80, 50)], 200, 100)
    assert d == 0
    d = c.count_frame([TrackBox(1, 110, 50)], 200, 100)
    assert d == 1
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `py -3.12 -m pytest tests/test_line_count.py -v`  
Expected: import/module missing

- [ ] **Step 3: Implement `line_count.py`**

```python
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
    counted_ids: set[int] = field(default_factory=set)
    _prev: dict[int, tuple[float, float]] = field(default_factory=dict)

    def reset(self) -> None:
        self.counted_ids.clear()
        self._prev.clear()

    def _axis(self, x: float, y: float) -> float:
        return x if self.direction in ("ltr", "rtl") else y

    def _line(self, w: int, h: int) -> float:
        return (w if self.direction in ("ltr", "rtl") else h) * self.line_pos

    def _crossed(self, prev: float, curr: float, line: float) -> bool:
        if self.direction in ("ltr", "ttb"):
            return prev < line <= curr
        return prev > line >= curr

    def count_frame(self, tracks: list[TrackBox], frame_w: int, frame_h: int) -> int:
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
        # drop stale
        for k in list(self._prev.keys()):
            if k not in seen:
                self._prev.pop(k, None)
        return delta
```

- [ ] **Step 4: Add `requirements-yolo.txt`**

```
ultralytics>=8.3.0
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
opencv-python-headless>=4.8.0
numpy>=1.26.0
pytest>=8.0.0
```

- [ ] **Step 5: Run tests — expect PASS**

Run: `py -3.12 -m pip install pytest -q && py -3.12 -m pytest tests/test_line_count.py -v`

- [ ] **Step 6: Commit**

```bash
git add services/yolo_counter tests/test_line_count.py requirements-yolo.txt
git commit -m "Add line-crossing counter for YOLO track IDs."
```

---

### Task 2: Estrutura de dataset + checklist de captura

**Files:**
- Create: `datasets/pills/README.md`
- Create: `docs/CAPTURE-PILLS.md`
- Modify: `.gitignore` (ensure `datasets/pills/**` images ignored but README kept)
- Modify: `docs/superpowers/specs/2026-09-14-yolo-pill-counting-design.md` status → approved

- [ ] **Step 1: Write `datasets/pills/README.md`** with YOLO layout:

```
datasets/pills/
  images/{train,val,test}/
  labels/{train,val,test}/
  data.yaml   # nc: 1, names: [pill]
```

- [ ] **Step 2: Write `docs/CAPTURE-PILLS.md`** — checklist: tripé, luz, 3 velocidades, 2–5 min vídeo cada, extrair 1–2 fps, anotar boxes, negativos, meta 800–1500 imgs

- [ ] **Step 3: Commit**

```bash
git add datasets/pills/README.md docs/CAPTURE-PILLS.md .gitignore
git commit -m "Add pill dataset layout and capture checklist."
```

---

### Task 3: Serviço YOLO track + WebSocket

**Files:**
- Create: `services/yolo_counter/server.py`
- Create: `services/yolo_counter/pipeline.py`
- Create: `scripts/run_yolo_service.py`
- Test: manual + unit for pipeline wiring with fake tracks

**Interfaces:**
- Consumes: `LineCounter`, Ultralytics `YOLO.track`
- Produces WebSocket JSON: `{type:"state", total:int, fps:float, boxes:[{id,x1,y1,x2,y2,conf}], line_pos:float, direction:str}`
- HTTP: `GET /health`, `POST /reset`, `POST /config` body `{line_pos, direction, conf}`
- Default model path: `models/pill-nano.pt` fallback `yolov8n.pt` with warning

- [ ] **Step 1: Implement `pipeline.py`** wrapping camera index / video file → track → `LineCounter` → total

- [ ] **Step 2: Implement FastAPI `server.py`** with WS `/ws` broadcasting state ~15–30 Hz

- [ ] **Step 3: `scripts/run_yolo_service.py`** entry: `py -3.12 scripts/run_yolo_service.py --source 0 --model models/pill-nano.pt`

- [ ] **Step 4: Smoke test**

Run: `py -3.12 scripts/run_yolo_service.py --source path/to/sample.mp4 --model yolov8n.pt`  
Expected: `/health` → `{"ok":true}`; WS messages with `total` field

- [ ] **Step 5: Commit**

```bash
git commit -m "Add YOLO tracking service with WebSocket count stream."
```

---

### Task 4: Script de treino `pill`

**Files:**
- Create: `scripts/train_pill_yolo.py`
- Create: `datasets/pills/data.yaml.example`
- Modify: `package.json` scripts optional note in README

- [ ] **Step 1: Script** mirrors `train_grain_yolo.py` but `data=datasets/pills/data.yaml`, `name=pill-nano`, export `models/pill-nano.pt`

- [ ] **Step 2: Document** in README: sem dataset → não treina; use checklist

- [ ] **Step 3: Commit**

```bash
git commit -m "Add pill YOLO training script and data.yaml example."
```

---

### Task 5: UI browser YOLO-first + Validação 0,5%

**Files:**
- Modify: `index.html` — modo fonte: `Classic` | `YOLO (PC)`; campo “Lote esperado N”; badge PASS/FAIL
- Modify: `app.js` — cliente WebSocket `ws://localhost:8765/ws` (configurável); overlay boxes do servidor; esconder assistente como principal
- Modify: `styles.css` se necessário

**Interfaces:**
- Consome mensagens `type:"state"` do Task 3
- Validação: `errorPct = Math.abs(total-N)/N`; PASS se `errorPct <= 0.005`

- [ ] **Step 1: UI controls** for YOLO mode + expected N + Connect

- [ ] **Step 2: Wire WS client** and draw boxes in overlay coords

- [ ] **Step 3: Validation panel** shows error % and PASS/FAIL

- [ ] **Step 4: Manual test** with service running

- [ ] **Step 5: Commit**

```bash
git commit -m "Switch UI to YOLO-first mode with 0.5% lot validation."
```

---

### Task 6: Validação CLI + docs alinhados

**Files:**
- Create: `scripts/validate_lot.py`
- Modify: `README.md`, `MAPA-DE-BORDO.md`, `models/DATASETS.md`

- [ ] **Step 1: CLI** `py -3.12 scripts/validate_lot.py --expected 200 --counted 199` → exit 0 if ≤0.5%

- [ ] **Step 2: Update docs** — fluxo PC+YOLO, meta 0,5%, captura pills, deprecar arroz como motor

- [ ] **Step 3: Commit + push** (se usuário pedir push)

```bash
git commit -m "Align docs and lot validation CLI with 0.5% accuracy goal."
```

---

### Task 7: Bootstrap de modelo (até ter dataset próprio)

**Files:**
- Create: `docs/BOOTSTRAP-PILLS.md`
- Optional: script search/download public pill detection dataset (CC license only)

- [ ] **Step 1: Document** caminho bootstrap (dataset público de pills OU treinar com primeiras 200 imgs da esteira)

- [ ] **Step 2: Se houver dataset CC disponível e downloadable**, script `scripts/fetch_pill_datasets.py`

- [ ] **Step 3: Commit**

---

## Spec coverage check

| Spec item | Task |
|-----------|------|
| YOLO principal + track + linha | 1, 3 |
| Dataset pill + captura | 2, 7 |
| Treino pill-nano | 4 |
| UI YOLO-first + Validação 0,5% | 5 |
| Prova 0,5% / 3 velocidades | 5, 6 (protocolo); execução física = usuário |
| Serviço PC | 3 |
| Deprecar clássico como motor | 5, 6 |

## Execution note

Após Task 1–3 o sistema já conta com pesos genéricos (baixa precisão). Tasks 2/4/7 desbloqueiam a meta 0,5% com dados reais da esteira.
