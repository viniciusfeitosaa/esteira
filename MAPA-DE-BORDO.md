# Mapa de bordo — Esteira

Documento operacional do projeto.  
Última atualização: **2026-09-28** (novo comprimido branco oblongo, webcam fixa, direção `rtl`).

**Histórico completo por etapa:** [`docs/ETAPAS.md`](docs/ETAPAS.md)

---

## 1. Objetivo

Contar **comprimidos/cápsulas** em esteira preta com erro de lote **≤ 0,5%** (`|contado − N| / N ≤ 0,005`, N ≥ 200).

| Papel | Onde |
|-------|------|
| Motor YOLO (`pill-nano`) | **PC local** (obrigatório) |
| UI + validação lote | Browser (`localhost`) |
| Pages / Render | Só demo da UI — **sem** motor de remédios |

---

## 2. Arquitetura atual

```
[Câmera / vídeo da esteira]
      │
      ▼
[PC — run_yolo_service.py]   ← use --lite no Galaxy Book (8 GB)
      │  YOLO predict + centroid track + LineCounter
      │  crop ROI esteira  ·  FastAPI :8765
      ▼
[Browser — Conectar YOLO]
      │  overlay · total · badge 0,5%
      ▼
[Operador]
```

---

## 3. Como rodar (Galaxy Book / 8 GB)

**Terminal 1 — motor (modo economia):**
```bash
py -3.12 scripts/run_yolo_service.py --source 0 --direction rtl --lite
```
Ou: `scripts\run_lite.bat`

**Terminal 2 — UI:**
```bash
npm run http
```
Abra `http://localhost:8080` → **Conectar YOLO**.

Feche apps pesados. Não treine YOLO nessa máquina.

---

## 4. Checklist de etapas (status)

- [x] 0 Protótipo clássico browser  
- [x] 1 HTTPS / celular  
- [x] 2 Assistente ONNX arroz (legado)  
- [x] 3 Pages / Render demo UI  
- [x] 4 Spec YOLO-primary 0,5%  
- [x] 5 LineCounter + testes  
- [x] 6 Serviço FastAPI / WS  
- [x] 7 Dataset layout + captura  
- [x] 8 UI YOLO-first + validate_lot  
- [x] 9 Bootstrap RF100 pills  
- [x] 10 Vídeos esteira real  
- [x] 11 Treino domínio esteira (`pill-nano`)  
- [x] 12 Centroid tracker + ROI  
- [x] 13 Modo `--lite` (8 GB)  
- [ ] 14 Aceite 0,5% com N≥200 em 3 velocidades  
- [x] 15 Novo comprimido + webcam fixa (`pills_fixed`, sintéticos, `rtl`)  

Detalhes de cada item: **`docs/ETAPAS.md`**.

---

## 5. Comandos úteis

```bash
py -3.12 -m pip install -r requirements-yolo.txt
py -3.12 -m pytest tests/test_line_count.py -v

# inferência
py -3.12 scripts/run_yolo_service.py --source 0 --lite

# dados / treino (máquina com mais RAM ou Colab)
py -3.12 scripts/prepare_fixedcam_dataset.py --videos <pasta> --photos <pasta> --aug-copies 1 --synthetic 900
$env:PILL_DATA="datasets/pills_fixed/data.yaml"; $env:PILL_EPOCHS="15"; $env:PILL_IMGSZ="640"; py -3.12 scripts/train_pill_yolo.py
py -3.12 scripts/eval_belt_count.py --videos <pasta>                 # YOLO, rtl
py -3.12 scripts/eval_belt_count.py --videos <pasta> --method classical
py -3.12 scripts/validate_lot.py --expected 200 --counted 199
```

---

## 6. Arquivos-chave

| Arquivo | Função |
|---------|--------|
| `docs/ETAPAS.md` | Registro de todas as etapas |
| `docs/CAPTURE-PILLS.md` | Como filmar a esteira |
| `docs/BOOTSTRAP-PILLS.md` | Dataset público / primeiros pesos |
| `scripts/run_lite.bat` | Atalho Windows lite |
| `models/pill-nano.pt` | Pesos locais (não versionados no git) |
