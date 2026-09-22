# Bootstrap — modelo de comprimidos

Até ter dataset próprio da esteira (≥800 imagens anotadas), use um destes caminhos.

## Opção A — primeiras capturas da esteira (recomendado)

1. Siga `docs/CAPTURE-PILLS.md` (tripé, luz, 3 velocidades).
2. Extraia 200–400 frames e anote boxes da classe `pill` (Roboflow / Label Studio / CVAT).
3. Monte `datasets/pills/` conforme `datasets/pills/README.md`.
4. Copie `data.yaml.example` → `data.yaml`.
5. Treine:

```bash
py -3.12 -m pip install -r requirements-yolo.txt
py -3.12 scripts/train_pill_yolo.py
```

Saída: `models/pill-nano.pt`.

## Opção B — dataset público (só licença CC / permissiva)

Bootstrap automático (RF100 pills, CC BY 4.0, ~450 imgs, classes → `pill`):

```bash
py -3.12 scripts/fetch_pill_datasets.py
py -3.12 scripts/train_pill_yolo.py
# → models/pill-nano.pt
```

Ou procure no [Roboflow Universe](https://universe.roboflow.com/) por *pill* / *tablet* / *capsule* com fundo escuro.

- Confirme licença (CC BY / CC0 / MIT).
- Exporte YOLO v8, 1 classe ou mapeie todas para `pill`.
- Coloque em `datasets/pills/` e treine como na opção A.

**Não** use pesos de arroz (`grain-nano`) como motor de medicamentos.

Atribuição RF100: [roboflow-100/pills-sxdht](https://universe.roboflow.com/roboflow-100/pills-sxdht) (Mohamed Attia).

## Sem pesos de pill

O serviço aceita fallback `yolov8n.pt` (COCO) só para fumaça de integração — **não** atinge a meta 0,5%.

```bash
py -3.12 scripts/run_yolo_service.py --source 0 --model yolov8n.pt
```

## Aceite de precisão

Com lote conhecido N ≥ 200:

```bash
py -3.12 scripts/validate_lot.py --expected 200 --counted 199
```

PASS se `|contado − N| / N ≤ 0,005`. Repita em 3 velocidades de esteira.
