# Design: Assistente YOLO híbrido (clássico + árbitro no browser)

**Data:** 2026-08-26  
**Repo:** esteira  
**Status:** aprovado — fase 1 em implementação

## Objetivo

Manter a contagem clássica (limiar / blobs / linha) como caminho principal e usar um modelo YOLO nano **no navegador** apenas como suporte (“cérebro”) quando houver dúvida — evitando trocar o pipeline leve por inferência a todo frame.

## Arquitetura

```
frame
  → clássico (máscara → blobs → tracks → linha)
  → assessDoubt(blob, stats)
  → se dúvida e assistente ligado:
        crop → arbitrate()  [stub na fase 1 | ONNX na fase 2]
  → resolveCount: 0 | 1 | N
  → atualiza total / overlay
```

- Assistente **desligável** (Off / Só dúvidas).
- Sem modelo → fallback automático ao clássico (+ stub opcional).
- Sem backend e sem treino no browser.

## Critérios de dúvida

- área ≫ mediana × 2,5 → possível colado  
- área ≪ mediana × 0,4 → possível ruído  
- aspect ratio &gt; ~3,5 → reflexo / não-grão  
- tracks muito próximos na linha → risco de dupla contagem  
- poucos hits + cruzamento rápido → flash  

Modo Instantâneo: verificação sob demanda (“Verificar com IA”), não a cada frame.

## Modelo (fase 2+)

- YOLOv8n / YOLO11n fine-tune classe `grain`
- Export ONNX → `models/grain-nano.onnx`
- Runtime: `onnxruntime-web`
- Input: crop ~160–320 px

## UX

- Select **Assistente IA**: Off | Só dúvidas  
- Overlay: verde = clássico OK; âmbar = dúvida; azul = confirmado IA; vermelho = rejeitado  
- Status textual com último veredito e ms (quando houver modelo)

## Correção na contagem

1. Clássico propõe +1 no cruzamento.  
2. Sem dúvida → confirma +1.  
3. Com dúvida → `arbitrate` → conta `n` (0 rejeita, N separa colados).  

## Fases

| Fase | Entrega |
|------|---------|
| **1** | `assist.mjs`, UI, stub, overlay, testes sintéticos de dúvida |
| **2** | Dataset + treino + ONNX no browser |
| **3** | Validação esperada vs contada, bank de vídeos, polarização distância |
| **4** | Polish produto (PWA, QR, presets) |

## Fora de escopo (agora)

YOLO em todo frame, API nuvem, treino no dispositivo, app nativo.

## Testes

- `npm test` inclui cases: dúvida por área grande; stub retorna N; assistente off não altera clássico.
