# Esteira — contagem de comprimidos (YOLO)

Contagem de **comprimidos/cápsulas** em esteira com **YOLO no PC** (detect + track + linha). O browser é a UI. Meta de aceite: `|contado − N| / N ≤ 0,005` com N ≥ 200.

O pipeline clássico no browser e o ONNX de arroz (`grain-nano`) são **legado / fallback** — não são o motor de medicamentos.

## Fluxo principal (PC)

```bash
py -3.12 -m pip install -r requirements-yolo.txt
# com models/pill-nano.pt (após treino) ou fallback yolov8n.pt:
py -3.12 scripts/run_yolo_service.py --source 0
```

Em outro terminal, UI:

```bash
npm start
# ou: npm run http  →  http://localhost:8080
```

Abra o app → **Conectar YOLO**. WebSocket: `ws://localhost:8765/ws`.

| Endpoint | Uso |
|----------|-----|
| `GET /health` | status + total |
| `WS /ws` | stream `{type:"state", total, fps, boxes…}` |
| `GET /frame.jpg` | preview anotado |
| `POST /reset` | zera contagem |
| `POST /config` | `direction`, `line_pos`, `conf` |

## Dataset e treino

1. Checklist: [`docs/CAPTURE-PILLS.md`](docs/CAPTURE-PILLS.md)
2. Bootstrap até ter dados: [`docs/BOOTSTRAP-PILLS.md`](docs/BOOTSTRAP-PILLS.md)
3. Layout: [`datasets/pills/README.md`](datasets/pills/README.md)
4. Treino:

```bash
# copiar datasets/pills/data.yaml.example → data.yaml
py -3.12 scripts/train_pill_yolo.py
# → models/pill-nano.pt
```

Sem dataset anotado o treino **não roda**.

## Validação 0,5%

No HUD: informe **Lote esperado N** — badge PASS/FAIL (limite 0,5%).

CLI:

```bash
py -3.12 scripts/validate_lot.py --expected 200 --counted 199
```

Repita em **3 velocidades** de esteira.

## UI / HTTPS (opcional)

Node.js para servir a UI; câmera no celular (modo clássico) exige HTTPS.

```bash
npm start          # https://localhost:8443
npm run http       # http://localhost:8080
```

**Motor** no painel: `YOLO (PC)` (padrão) ou `Clássico (fallback)`.

## Legado

| Item | Papel |
|------|--------|
| Limiar / blobs no browser | Fallback / demo |
| `models/grain-nano.onnx` | Assistente ONNX de arroz (não pill) |
| Pages / Render estático | Demo UI; precisão 0,5% exige PC + `pill-nano` |

## Spec / plano

- Spec: `docs/superpowers/specs/2026-09-14-yolo-pill-counting-design.md`
- Plano: `docs/superpowers/plans/2026-09-14-yolo-pill-counting.md`
