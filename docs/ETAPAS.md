# Etapas do projeto Esteira — registro completo

Documento para acompanhar **cada fase** do desenvolvimento.  
Última atualização: **2026-09-28**.

---

## Visão geral das etapas

| # | Etapa | Status | Entrega principal |
|---|--------|--------|-------------------|
| 0 | Ideia / protótipo browser | Feito | Contagem clássica (limiar + blobs + linha) |
| 1 | HTTPS local + celular | Feito | `server.mjs`, câmera no tripé |
| 2 | Assistente YOLO ONNX (arroz) | Feito | `grain-nano.onnx` no browser |
| 3 | Deploy demo Pages / Render | Feito | UI estática (sem motor de remédios) |
| 4 | Pivot: YOLO-primary comprimidos | Feito | Spec + plano 0,5% |
| 5 | Contador por linha + testes | Feito | `line_count.py` |
| 6 | Serviço PC FastAPI / WebSocket | Feito | `:8765` |
| 7 | Dataset pills + checklist captura | Feito | `CAPTURE-PILLS.md` |
| 8 | UI YOLO-first + validação 0,5% | Feito | badge PASS/FAIL |
| 9 | Bootstrap RF100 pills (público) | Feito | `fetch_pill_datasets.py` |
| 10 | Vídeos reais da esteira | Feito | pasta `treinamentoIA` |
| 11 | Auto-label + crop ROI + treino | Feito | `pill-nano.pt` domínio esteira |
| 12 | Tracker por centroides | Feito | contagem mais estável |
| 13 | Modo **lite** (8 GB RAM) | Feito | `--lite` / `run_lite.bat` |
| 14 | Meta 0,5% em lote N≥200 | Em aberto | mais vídeo + validação física |
| 15 | Novo comprimido + webcam fixa | Feito | `pills_fixed` + sintéticos, direção **rtl** |
| 16 | UI só YOLO + área de contagem editável | Feito | sem limiarização; desenhar área / arrastar linha |

---

## Etapa 0 — Protótipo clássico (browser)

**Objetivo:** provar contagem sem IA em esteira preta / objetos claros.

**O que foi feito**
- `index.html` / `app.js` / `vision.mjs`
- Limiar, ROI, morfologia, tracking simples, cruzamento de linha
- Modos: esteira vs instantâneo

**Limitação:** grãos/objetos colados e iluminação irregular degradam a contagem.

---

## Etapa 1 — Acesso no celular

**Objetivo:** câmera no tripé via celular na mesma rede.

**O que foi feito**
- `server.mjs` com HTTPS (`npm start`) e HTTP (`npm run http`)
- Certificado local `.certs/`
- Documentação de IP / firewall

---

## Etapa 2 — Assistente híbrido (arroz / ONNX)

**Objetivo:** YOLO no browser só para “dúvidas” do clássico.

**O que foi feito**
- Dataset Roboflow rice (CC BY)
- `train_grain_yolo.py` → `models/grain-nano.onnx`
- `yolo-assist.mjs` + `onnxruntime-web`

**Limitação:** domínio arroz ≠ medicamentos; Pages só carrega ONNX se o arquivo estiver no deploy.

---

## Etapa 3 — Demo hospedada

**Objetivo:** mostrar a UI sem instalar nada.

**O que foi feito**
- GitHub Pages: https://viniciusfeitosaa.github.io/esteira/
- `render.yaml` Static Site (opcional)

**Importante:** Pages/Render **não** rodam o YOLO de comprimidos. Só a interface.

---

## Etapa 4 — Pivot para medicamentos (0,5%)

**Objetivo:** trocar o motor principal para YOLO no PC, meta de lote ≤ 0,5%.

**Docs**
- Spec: `docs/superpowers/specs/2026-09-14-yolo-pill-counting-design.md`
- Plano: `docs/superpowers/plans/2026-09-14-yolo-pill-counting.md`

**Decisões**
- 1 classe: `pill`
- Inferência de produção no **PC**
- Browser = UI + validação de lote
- `grain-nano` deixa de ser o motor

---

## Etapa 5 — Contagem por linha (testável)

**Arquivos**
- `services/yolo_counter/line_count.py`
- `tests/test_line_count.py`
- `requirements-yolo.txt`

**Aceite:** testes unitários PASS (LTR/RTL/reset).

---

## Etapa 6 — Serviço YOLO no PC

**Arquivos**
- `pipeline.py`, `server.py`, `scripts/run_yolo_service.py`
- Endpoints: `/health`, `/ws`, `/frame.jpg`, `/reset`, `/config`

**Porta padrão:** `8765`

---

## Etapa 7 — Dataset e captura

**Arquivos**
- `datasets/pills/README.md`
- `docs/CAPTURE-PILLS.md`
- `docs/BOOTSTRAP-PILLS.md`

**Meta de dados:** 800–1500 imagens anotadas da esteira real (ainda incompleto).

---

## Etapa 8 — UI YOLO-first

**Arquivos**
- `index.html`, `app.js`, `styles.css`
- Motor: YOLO (PC) | Clássico
- Campo **Lote esperado N** + badge PASS/FAIL (≤ 0,5%)
- CLI: `scripts/validate_lot.py`

---

## Etapa 9 — Bootstrap público (RF100 pills)

**O que foi feito**
- `scripts/fetch_pill_datasets.py` (Hugging Face LibreYOLO/pills-sxdht, CC BY)
- Remapeamento de classes → `pill`
- Primeiro treino CPU → `models/pill-nano.pt` (bom em domain público, fraco na esteira real)

---

## Etapa 10 — Vídeos da esteira real

**Fonte:** `C:\Users\vinic\Downloads\treinamentoIA` (3 vídeos WhatsApp ~30 s)

**Problemas cobertos nos vídeos (úteis para treino)**
- fragmento irregular (não comprimido “perfeito”)
- glare / reflexo na esteira
- poeira e riscos
- densidade variável
- rolamentos / frame mecânico no enquadramento
- compressão WhatsApp / FPS alto

---

## Etapa 11 — Treino no domínio da esteira

**Pipeline**
1. `prepare_belt_dataset.py` — extrai frames, auto-label clássico multi-pass, crop da faixa preta
2. `train_pill_yolo.py` com `PILL_DATA=datasets/pills_belt/data.yaml`
3. Saída: `models/pill-nano.pt` (domínio esteira)

**Resultado típico (val):** mAP50 ~0,88–0,89 (labels ainda automáticas).

**Script de avaliação:** `scripts/eval_belt_count.py`

---

## Etapa 12 — Contagem mais estável

**Problema:** ByteTrack trocava muitos IDs em vídeo comprimido (~100+ IDs com ~15 objetos).

**Solução**
- YOLO só **detecta** (`predict`)
- `centroid_track.py` associa centros entre frames
- `belt_roi.py` corta rolamentos
- Direção nestes clips: **btt** (baixo → cima)

---

## Etapa 13 — Modo lite (hardware limitado)

**Contexto:** Galaxy Book S, 8 GB RAM — sem GPU dedicada.

**Como rodar**
```bash
py -3.12 scripts/run_yolo_service.py --source 0 --direction rtl --lite
```
Ou duplo clique: `scripts/run_lite.bat`

**O que o lite faz**
| Parâmetro | Normal | Lite |
|-----------|--------|------|
| `imgsz` | 640 | 416 (era 320; ver etapa 15) |
| Frames processados | todos | 1 de 2 |
| Webcam | nativa | force 640×480 @ ~15 FPS |
| WebSocket | ~33 Hz | ~12 Hz |
| JPEG preview | qualidade 80 | 55 |
| `conf` default | 0.3 | 0.3 |

**Dicas 8 GB**
1. Feche Chrome com muitas abas / outras IDEs
2. Não treine YOLO nessa máquina
3. UI: `npm run http` → `http://localhost:8080` → Conectar YOLO
4. Se travar: teste com `--source caminho\video.mp4` antes da webcam

**Onde NÃO roda o motor de remédios:** GitHub Pages / Render (só UI).

---

## Etapa 14 — Próximos passos (meta 0,5%)

1. Gravar 2–5 min por velocidade (lenta/média/rápida) — ver `CAPTURE-PILLS.md`
2. Revisar labels (Roboflow/CVAT) — auto-label ainda erra glare
3. Retreinar com `PILL_TRAIN_FULL=1` (idealmente com mais RAM/GPU)
4. Validar lote N ≥ 200: `validate_lot.py` + badge na UI
5. Calibrar `direction` / `line_pos` na esteira física

---

## Etapa 15 — Novo comprimido e webcam fixa (2026-09-28)

**Mudança:** o comprimido passou a ser **branco, oblongo** (~27 px de comprimento no vídeo 848×478) e a
esteira aparece **na horizontal**, com a webcam fixa ao lado. Os comprimidos andam da **direita para a
esquerda** (`rtl`, ~1,3 px/frame a 58 FPS).

**Fonte:** `C:\Users\vinic\Downloads\WhatsApp Unknown 2026-09-28 at 20.33.47`
- 5 fotos: formato do comprimido (usadas como recortes extras para sintéticos)
- 5 vídeos (16–28 s, 58 FPS): treino e avaliação

**Problemas nestes vídeos**
- reflexo forte (glare) no centro da esteira, com textura hachurada da borracha
- mão segurando comprimidos no canto (não pode contar)
- parafusos/eixos metálicos brilhantes
- câmera do celular balança (na produção a webcam fica fixa)

**Auto-label** (`services/yolo_counter/white_pill.py`)
1. Top-hat no canal V (remove fundo largo) + branco (V alto, S baixo)
2. Filtros de forma: área, alongamento 1,25–3,8, preenchimento ≥ 0,6, contraste com o anel ao redor
3. Dentro do reflexo: mediana 7×7 apaga a hachura; só núcleos lisos e muito claros passam, e o
   candidato precisa ter **sombra escura logo abaixo** (luz vem de cima; reflexo não tem sombra)
4. Frames com blob “incerto” (ex.: comprimidos encostados) são descartados (118 de 632)

**Por que não multiplicar cópias idênticas**
Copiar o mesmo arquivo N vezes equivale a treinar mais épocas: a rede vê exatamente os mesmos pixels e
tende a decorar (overfitting). O que funciona é multiplicar **com variação**:
- **Cópias variadas** (`--aug-copies`): blur de movimento, ruído, brilho/gama, reflexo artificial,
  compressão JPEG, escala, rotação, espelhamento
- **Sintéticos copy-paste** (`--synthetic`): recortes reais de comprimidos (vídeos + fotos) colados
  em frames sem comprimidos, com sombra, de 1 a 30 por imagem, incluindo comprimidos encostados;
  cada label é exata porque sabemos onde colamos
- O Ultralytics ainda aplica mosaic/HSV/escala a cada época por cima disso

**Dataset** (`scripts/prepare_fixedcam_dataset.py` → `datasets/pills_fixed/`)
| Parte | Imagens |
|-------|---------|
| Frames reais (treino) | 452 |
| Cópias variadas | 452 |
| Sintéticos | 900 |
| **Validação** (trecho final de cada vídeo, nunca visto no treino) | 62 |

```powershell
$d = "C:\Users\vinic\Downloads\WhatsApp Unknown 2026-09-28 at 20.33.47"
py -3.12 scripts/prepare_fixedcam_dataset.py --videos $d --photos $d --aug-copies 1 --synthetic 900
$env:PILL_DATA="datasets/pills_fixed/data.yaml"; $env:PILL_EPOCHS="15"; $env:PILL_IMGSZ="640"; $env:PILL_BATCH="8"
$env:PILL_BASE="models/pill-nano-v1-esteira-antiga.pt"
py -3.12 scripts/train_pill_yolo.py
```
Modelo antigo preservado em `models/pill-nano-v1-esteira-antiga.pt`.

**Resultado do treino** (CPU, ~10,5 min/época, 15 épocas ≈ 2,5 h): mAP50 ≈ 0,89–0,90 desde a
época 1; mAP50-95 subiu de 0,60 para 0,66.

**Resultado de contagem** (gabarito 30):
| Modelo | Normal (640 px, ~30 fps) | Lite (416 px, ~7,5 fps) |
|--------|--------------------------|-------------------------|
| Referência clássica (sem IA) | 28 | — |
| **Época 4 → `models/pill-nano.pt`** | **30 (7/8/5/2/8, exato)** | 29 |
| Época 15 → `models/pill-nano-e15.pt` | 26 | 29 |
| Época 4 com lite a 320 px | — | 21 (comprimido pequeno demais) |

**Por que a época 15 conta pior:** a linha de contagem fica no meio da esteira, onde está o reflexo;
o auto-label perde comprimidos ali e, com mais épocas, o modelo aprende a ignorá-los (detecta 12%
menos na faixa central e 17% mais no resto). O "best.pt" do Ultralytics é escolhido pelo mAP na
validação auto-rotulada, não pela contagem — por isso a escolha final foi feita com
`eval_belt_count.py` contra o gabarito.

**Próxima rodada (corrige os buracos do reflexo):** re-rotular os frames reais com o modelo atual
(pseudo-labels) e retreinar:
```powershell
py -3.12 scripts/prepare_fixedcam_dataset.py --videos $d --photos $d --aug-copies 1 --synthetic 900 --relabel-model models/pill-nano.pt
```

**Gabarito de contagem (slit-scan)**
Empilhando a coluna de pixels da linha de contagem frame a frame, cada comprimido que cruza vira uma
mancha branca — dá para contar a olho. Gabarito: 7 + 8 + 5 + 2 + 8 = **30** comprimidos.
Referência clássica (sem IA): 28 (−6,7%).

**Contador:** `LineCounter` agora mantém a última posição de um track sumido por até 30 frames
(reflexo/oclusão), para não perder o cruzamento.

**Serviço:** padrão `--direction rtl --line-pos 0.5 --conf 0.3`; novo `--roi X0 Y0 X1 Y1` (frações do
frame) para inferir só na esteira; `--crop-belt` mantém o recorte antigo (esteira vertical).

---

## Etapa 16 — UI só YOLO e área de contagem editável (2026-09-28)

**Pedido:** tirar a limiarização (motor clássico por limiar de brilho), ver o que o YOLO enxerga e
poder escolher a área de contagem.

**O que mudou**
- `index.html` / `app.js` reescritos só para YOLO: sai o motor clássico (limiar, máscara, sliders de
  área/contraste, assistente ONNX). `vision.mjs`/`assist.mjs` ficam só para os testes em Node.
- O vídeo é o frame limpo da câmera (`/frame.jpg?raw=1`) com as detecções desenhadas pela UI:
  verde = comprimido visto, azul = já contado, rótulo `#id confiança%`.
- **Desenhar área de contagem:** clicar no botão e arrastar um retângulo no vídeo. Só essa região vai
  para o YOLO (`roi` enviado ao serviço); fora dela fica escurecido.
- **Linha:** arrastar a linha amarela (a seta mostra o sentido); fica sempre dentro da área.
- Painel: URL, direção, posição da linha, **confiança mínima** (efeito visível na hora).
- Área, linha, direção e confiança ficam salvas no navegador (`localStorage`) e são reenviadas ao
  conectar.
- Serviço: `/frame.jpg?raw=1` e campo `counted` em cada caixa do estado.

---

## Mapa rápido de arquivos

| Caminho | Papel |
|---------|--------|
| `scripts/run_yolo_service.py` | Sobe o motor (`--lite` opcional) |
| `scripts/run_lite.bat` | Atalho Windows lite |
| `scripts/prepare_fixedcam_dataset.py` | Dataset webcam fixa + cópias variadas + sintéticos |
| `services/yolo_counter/white_pill.py` | Auto-label do comprimido branco |
| `scripts/prepare_belt_dataset.py` | Frames + labels da esteira antiga (vertical) |
| `scripts/train_pill_yolo.py` | Treino → `pill-nano.pt` |
| `scripts/eval_belt_count.py` | Avalia contagem em vídeos |
| `scripts/validate_lot.py` | PASS/FAIL 0,5% |
| `services/yolo_counter/` | Pipeline + API |
| `docs/CAPTURE-PILLS.md` | Como filmar |
| `docs/BOOTSTRAP-PILLS.md` | Dataset público / primeiros dados |
| `MAPA-DE-BORDO.md` | Resumo operacional |
| Este arquivo | Histórico detalhado por etapa |

---

## Commits / remoto (referência)

- Repo: https://github.com/viniciusfeitosaa/esteira  
- Branch: `main`  
- Demo UI: https://viniciusfeitosaa.github.io/esteira/
