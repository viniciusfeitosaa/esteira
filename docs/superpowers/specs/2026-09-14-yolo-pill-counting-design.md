# Design: YOLO principal — contagem de medicamentos (precisão ≤ 0,5%)

**Data:** 2026-09-14  
**Repo:** esteira  
**Status:** aprovado em diálogo — aguardando revisão do arquivo  
**Substitui / evolui:** `2026-08-26-yolo-assist-design.md` (clássico + YOLO árbitro)

## Objetivo

Contar **comprimidos/cápsulas** em esteira com **YOLO como detector principal** (não assistente).  
Meta de aceite: **erro relativo ≤ 0,5%** em lote conhecido (`|contado − N| / N ≤ 0,005`).

Escopo do MVP: **só contar** (1 classe: `pill`). Sem identificação de nome/SKU.

## Contexto

- Protótipo atual: visão clássica (limiar/blobs) + assistente YOLO opcional (arroz).  
- Clássico falha com domínio variado e não atinge meta industrial.  
- Velocidade da esteira afeta blur, frames por objeto e tracking — validação em 2–3 velocidades é obrigatória.  
- Modelo `grain-nano` (arroz) **não** é o motor de medicamentos; serve no máximo como referência de pipeline ONNX.

## Arquitetura

```
câmera
  → frames
  → YOLO (classe única: pill) a cada frame
  → tracker (ByteTrack / equivalente Ultralytics)
  → linha virtual no sentido da esteira
  → total += 1 por track ID que cruza uma vez
  → UI no browser (total, FPS, boxes, validação)
```

| Peça | Papel |
|------|--------|
| Inferência + track | PC local (Python / Ultralytics) — caminho da meta 0,5% |
| UI | Browser (HTTPS), consome stream/eventos do serviço |
| Modelo | `models/pill-nano.pt` (+ ONNX opcional depois) |
| Clássico (limiar) | Fora do caminho principal; debug opcional |
| Assistente stub/árbitro | Deprecado como cérebro |

### Por que PC e não só browser

Meta 0,5% + esteira em movimento exige FPS alto e tracking estável. ONNX no celular/Render fica como demo/fallback, não como garantia da meta.

## Dataset

| Item | Definição |
|------|-----------|
| Objeto | Comprimido / cápsula na esteira real do projeto |
| Classe | `pill` (1) |
| Volume inicial | 800–1500 imagens com bounding boxes |
| Diversidade | 2–3 velocidades; luz variada; densidade baixa/média; alguns colados |
| Negativos | Esteira vazia, mão, pó, reflexo |
| Split | 80% train / 10% val / 10% test |
| Ferramenta | Roboflow ou CVAT |
| Pasta | `datasets/pills/` (gitignored se pesado) |

Captura sugerida: vídeo contínuo → extrair 1–2 fps → anotar.

Bootstrap opcional: dataset público de pills **somente** para pipeline; fine-tune final **obrigatório** nas imagens da esteira.

## Treino

- Família: YOLOv8n / YOLO11n; subir para `s` se recall insuficiente.  
- Tracking: ByteTrack (Ultralytics `track`).  
- Contagem: cruzamento de linha por ID (anti-recontagem).  
- Scripts: `scripts/train_pill_yolo.py`, validação de lote `scripts/validate_lot.py`.  
- Export: `.pt` para PC; `.onnx` opcional para espelho web.

## Prova de precisão (0,5%)

1. Separar lote conhecido **N** (recomendado N ≥ 200).  
2. Passar na velocidade de produção.  
3. Aceite: `|contado − N| / N ≤ 0,005` (ex.: N=200 → no máximo 1 de erro).  
4. Repetir em velocidades **lenta / média / rápida**.  
5. Critério de “pronto”: PASS em pelo menos **2 de 3** corridas consecutivas na velocidade de produção.  
6. UI **Validação**: usuário informa N → app mostra erro % e PASS/FAIL.

## UX

- Overlay: boxes YOLO + ID do track + linha de contagem.  
- HUD: total, taxa/min, FPS, status do modelo.  
- Ações: Iniciar / Pausar / Zerar / direção / posição da linha.  
- Painel: confiança mínima, parâmetros de track, Validação (N esperado).  
- Remover ou esconder “Assistente IA (só dúvidas)” como modo principal.

## Fases de implementação

| Fase | Entrega |
|------|---------|
| **0** | Spec (este documento) + estrutura `datasets/pills/` + checklist de captura |
| **1** | Serviço PC: YOLO detect/track + contagem por linha + API/WebSocket para UI |
| **2** | Dataset próprio anotado + treino `pill-nano` |
| **3** | UI browser no modo YOLO-first + modo Validação 0,5% |
| **4** | Campanha de teste em 3 velocidades; ajustar modelo/linha até PASS |

Ordem prática: 0 → 1 (com modelo bootstrap ou pesos iniciais) → 2 → retreino → 3 → 4.

## Fora de escopo (MVP)

- Identificar nome/SKU do medicamento  
- Contagem por blister / cartela como unidade  
- Garantia de 0,5% só no GitHub Pages / Render sem PC de inferência  
- Manter clássico como motor principal

## Riscos

| Risco | Mitigação |
|-------|-----------|
| Blur em esteira rápida | Luz forte, exposição baixa, FPS alto, validar por velocidade |
| Colados | Dataset com adesão; se precisar, segunda linha / NMS mais agressivo |
| Domínio diferente do treino | Fine-tune só com imagens da esteira real |
| FPS baixo no PC fraco | Modelo nano; ROI; resolução 640→480 se necessário |

## Relação com o código atual

- Reaproveitar: UI base, linha virtual, calibração de direção, servidor HTTPS, modo validação (a criar).  
- Deprecar como principal: `buildMask` / blobs / `assist` stub como cérebro.  
- Evoluir: `yolo-assist.mjs` / serviço Python passam a ser o caminho default.
