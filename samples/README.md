# Vídeos de teste (esteira real, 2026-09-28)

Comprimido branco oblongo, esteira horizontal, comprimidos andando da **direita para a esquerda**.
848×478, ~58 FPS, 16–28 s cada.

| Arquivo | Comprimidos que cruzam a linha (50%) |
|---------|--------------------------------------|
| `esteira-2026-09-28-1.mp4` | 7 |
| `esteira-2026-09-28-2.mp4` | 8 |
| `esteira-2026-09-28-3.mp4` | 5 |
| `esteira-2026-09-28-4.mp4` | 2 |
| `esteira-2026-09-28-5.mp4` | 8 |
| **Total** | **30** |

Gabarito contado a olho em imagens slit-scan (ver `docs/ETAPAS.md`, etapa 15).

```bash
npm run eval:samples   # deve dar TOTAL line_counted=30 com models/pill-nano.pt
npm run yolo:demo      # serviço usando o vídeo 1 no lugar da webcam; depois npm run http
```
