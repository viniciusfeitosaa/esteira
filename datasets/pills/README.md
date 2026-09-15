# Dataset pills (YOLO)

Layout esperado:

```
datasets/pills/
  images/train/
  images/val/
  images/test/
  labels/train/
  labels/val/
  labels/test/
  data.yaml
```

## data.yaml

```yaml
path: datasets/pills
train: images/train
val: images/val
test: images/test
nc: 1
names:
  - pill
```

Labels YOLO: um `.txt` por imagem, linhas `0 x_center y_center width height` (normalizado 0–1).

Ver checklist: `docs/CAPTURE-PILLS.md`.
