# Deploy no Render (Static Site)

1. Conta em https://dashboard.render.com (login GitHub).
2. **New → Static Site** (ou **Blueprint** com este `render.yaml`).
3. Conecte o repo `viniciusfeitosaa/esteira`, branch `main`.
4. **Publish directory:** `.` (raiz)
5. **Build command:** deixe vazio ou `echo ok`
6. Create Static Site → aguarde o deploy.

URL típica: `https://esteira-xxxx.onrender.com`

## YOLO no Render

O arquivo `models/grain-nano.onnx` (~12 MB) precisa estar no deploy.
No repo ele pode estar versionado ou baixado no build.

Assistente IA → Só dúvidas → carrega `./models/grain-nano.onnx`.
