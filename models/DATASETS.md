# Datasets de grãos de arroz (para YOLO)

Curadoria para o assistente híbrido ESTEIRA. **Evitar** datasets de *folha/doença*.

## Em uso neste repo

| Dataset | Local | Licença | Notas |
|---------|-------|---------|-------|
| **rice_object_detection** (Roboflow `bits`) | `datasets/rice_object_detection/` | **CC BY 4.0** | YOLO v8 · 7 classes · ~4224/480/272 |

Atribuição obrigatória: [Roboflow — rice_object_detection](https://universe.roboflow.com/bits/rice_object_detection/dataset/1).

### Treino

- Máquina atual sem GPU → script usa `fraction=0.15` + 5 epochs (protótipo).  
- Treino completo (recomendado): GPU / Google Colab com `fraction=1.0`, `epochs=50`, `imgsz=640`.  
- Saída: `models/grain-nano.pt` + `models/grain-nano.onnx`.

### Classes do dataset (qualidade)

`Broken`, `Chalky`, `Clean`, `Damaged`, `Discolored`, `Immature`, `Organic Foreign Matters`  

Para a esteira, o árbitro pode contar **qualquer** detecção como grão; classes extras ajudam depois (quebrado vs inteiro — alinhado ao preprint YOLOv8).

## Outros candidatos

| Dataset | Link | Notas |
|---------|------|-------|
| Rice OD 75k (Ali Khalili / Koklu) | [Kaggle](https://www.kaggle.com/datasets/alikhalilit98/rice-image-dataset-for-object-detection) | CC0 base; precisa `kaggle.json` |
| Koklu rice images | [Kaggle](https://www.kaggle.com/datasets/muratkokludataset/rice-image-dataset) | CC0; 1 grão/foto (classificação) |
| RiceLCNN (fundo preto) | [GitHub](https://github.com/5120191452/RiceLCNN) | Ideal domínio esteira; verificar release de dados |
| Roboflow rice grain | [Universe](https://universe.roboflow.com/search?q=rice%20grain) | Inspecionar fundo/densidade |

## Não usar

- Datasets de **rice leaf disease** (folhas).

## Comandos

```bash
py -3.12 scripts/fetch_rice_datasets.py   # baixa/prepara
py -3.12 scripts/train_grain_yolo.py      # treina yolov8n → models/grain-nano.onnx
```

`datasets/`, `runs/`, `*.pt` e `models/*.onnx` estão no `.gitignore` (pesados).
