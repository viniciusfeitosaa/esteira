# models/

| Arquivo | Uso |
|---------|-----|
| `grain-nano.pt` | Ultralytics / treino (local) |
| `grain-nano.onnx` | Inferência no browser (fase 2) |
| `grain-nano.json` | Metadados (classes, imgsz) |

Dataset e atribuição: `DATASETS.md`.

O app carrega `./models/grain-nano.onnx` quando **Assistente IA → Só dúvidas**.
Sem o arquivo, cai no stub heurístico.
