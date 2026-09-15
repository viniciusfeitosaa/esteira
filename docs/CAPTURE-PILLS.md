# Captura de dataset — comprimidos/cápsulas

Meta: **800–1500** imagens anotadas, classe única `pill`, para erro ≤ 0,5% na esteira.

## Setup

1. Celular/câmera fixa no tripé, vista de cima.
2. Luz forte e estável (evitar blur).
3. Esteira no enquadramento (ROI central).

## Gravação

Para cada velocidade (**lenta / média / rápida**):

- [ ] 2–5 minutos de vídeo contínuo com fluxo de comprimidos
- [ ] Trecho com esteira **vazia** (negativos)
- [ ] Alguns momentos com **colados** / mão / sombra

## Extração

- Extrair **1–2 frames por segundo** (Roboflow, ffmpeg, etc.)
- Descartar frames muito borrados

## Anotação

- Ferramenta: Roboflow ou CVAT
- Box em **cada** comprimido/cápsula visível
- Classe: `pill` (id 0)
- Export formato **YOLOv8**

## Organização

Colocar em `datasets/pills/` conforme `datasets/pills/README.md`.

## Treino

```bash
py -3.12 -m pip install -r requirements-yolo.txt
# criar data.yaml a partir do example
py -3.12 scripts/train_pill_yolo.py
```

## Validação de lote (meta 0,5%)

```bash
py -3.12 scripts/validate_lot.py --expected 200 --counted 199
```
