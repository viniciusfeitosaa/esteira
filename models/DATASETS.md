# Datasets — esteira

## Medicamentos (motor atual)

Classe única: **`pill`**. Layout e captura:

- `datasets/pills/README.md`
- `docs/CAPTURE-PILLS.md`
- `docs/BOOTSTRAP-PILLS.md`

```bash
# data.yaml a partir de data.yaml.example
py -3.12 scripts/train_pill_yolo.py   # → models/pill-nano.pt
```

`grain-nano` (arroz) **não** substitui `pill-nano` para medicamentos.

---

# Datasets de grãos de arroz (legado / assistente ONNX)

Curadoria para o assistente híbrido ESTEIRA no browser. **Evitar** datasets de *folha/doença*.

## Em uso neste repo

| Dataset | Local | Licença | Notas |
|---------|-------|---------|-------|
| **rice_object_detection** (Roboflow `bits`) | `datasets/rice_object_detection/` | **CC BY 4.0** | YOLO v8 · 7 classes · ~4224/480/272 |

Atribuição obrigatória: [Roboflow — rice_object_detection](https://universe.roboflow.com/bits/rice_object_detection/dataset/1).

### Treino (legado)

- Saída: `models/grain-nano.pt` + `models/grain-nano.onnx`.

```bash
py -3.12 scripts/fetch_rice_datasets.py
py -3.12 scripts/train_grain_yolo.py
```

`datasets/`, `runs/`, `*.pt` e `models/*.onnx` estão no `.gitignore` (pesados).
