# Mapa de bordo — Esteira

Documento de bordo do projeto.  
Última atualização: **2026-09-14**.

---

## 1. Objetivo do produto

Contar **comprimidos/cápsulas** em esteira preta com erro de lote **≤ 0,5%** (`|contado − N| / N ≤ 0,005`, N ≥ 200).

**Motor de produção:** YOLO (Ultralytics) no **PC** — detect + ByteTrack + cruzamento de linha.  
**Browser:** UI (overlay, validação PASS/FAIL, calibração de linha/direção).

O pipeline clássico (limiar/blobs) e o ONNX de arroz são legado/fallback.

---

## 2. Arquitetura atual

```
[Câmera / vídeo]
      │
      ▼
[PC — scripts/run_yolo_service.py]
      │  Ultralytics YOLO.track + LineCounter
      │  FastAPI :8765  (WS /ws, /frame.jpg, /health)
      ▼
[Browser — index.html / app.js]
      │  overlay + lote N + badge 0,5%
      ▼
[Operador]
```

---

## 3. O que já foi feito

- [x] Contagem por linha testável (`services/yolo_counter/line_count.py`)
- [x] Serviço YOLO + WebSocket (`pipeline.py`, `server.py`)
- [x] Layout dataset pills + checklist de captura
- [x] Script de treino `train_pill_yolo.py` + `data.yaml.example`
- [x] UI YOLO-first + validação de lote 0,5%
- [x] CLI `validate_lot.py` + docs alinhados
- [x] Bootstrap pills (`docs/BOOTSTRAP-PILLS.md`)
- [x] Legado: clássico browser, assistente ONNX arroz, deploy Pages/Render (demo)

---

## 4. Para atingir 0,5%

1. Capturar/anotar dataset da esteira real (`docs/CAPTURE-PILLS.md`)
2. Treinar `models/pill-nano.pt`
3. Rodar serviço com esse peso
4. Validar 3 velocidades com N ≥ 200

Até lá, `yolov8n.pt` só serve para smoke de integração.

---

## 5. Comandos úteis

```bash
py -3.12 -m pip install -r requirements-yolo.txt
py -3.12 -m pytest tests/test_line_count.py -v
py -3.12 scripts/run_yolo_service.py --source 0
py -3.12 scripts/train_pill_yolo.py
py -3.12 scripts/validate_lot.py --expected 200 --counted 199
npm start
```

---

## 6. Histórico resumido

| Etapa | Descrição |
|--------|-----------|
| Protótipo | Contagem clássica no browser (grãos) |
| Híbrido | Assistente YOLO ONNX arroz |
| Pivot | YOLO-primary para comprimidos, meta 0,5%, inferência no PC |
