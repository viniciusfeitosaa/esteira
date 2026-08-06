# Mapa de bordo — Esteira

Documento de bordo do projeto de contagem de grãos em esteira via navegador.  
Última atualização: **2026-08-05**.

---

## 1. Objetivo do produto

Sistema que roda no **navegador** (prioridade: **celular no tripé**) apontado para uma **esteira preta** com grãos claros (ex.: arroz). O software conta os grãos que passam, **sem modelo de IA** (sem YOLO), usando processamento de imagem clássico em tempo real.

Motivo da escolha sem IA: menor latência no celular, menos dependência de modelo treinado, protótipo mais barato e fácil de calibrar no local.

---

## 2. Contexto e histórico

| Etapa | Descrição |
|--------|-----------|
| Origem | Repo GitHub `viniciusfeitosaa/esteira` — protótipo HTML/CSS/JS |
| Máquina local | Clone/download em `C:\Users\vinic\esteira` (via ZIP; Git não estava no PATH no início) |
| Rede de teste | PC consumindo dados móveis do celular (hotspot); IP do PC muda a cada rede |
| Primeiro acesso mobile | Falhou em `10.50.71.132` (IP antigo) + firewall bloqueando 8443 |
| Correção de rede | IP atual da sessão de teste: `10.124.84.44`; regra de firewall **Esteira HTTPS 8443**; certificado self-signed em `.certs/` |
| Validação | Usuário confirmou: app abre no celular; detecção ainda imprecisa → pipeline de visão reforçado |

---

## 3. O que já foi feito

### 3.1 Base funcional (protótipo original + evolução)

- [x] UI mobile-first: vídeo, contador, FPS, pausar, zerar, painel de calibração  
- [x] Captura de câmera com `getUserMedia` (preferência câmera traseira)  
- [x] Processamento em resolução reduzida (performance no celular)  
- [x] Segmentação por brilho / contraste (esteira escura × grão claro)  
- [x] Blobs (componentes conectados) com filtro por área  
- [x] Rastreamento entre frames + contagem ao **cruzar linha virtual** (4 direções)  
- [x] Overlay: linha, ROI, círculos nos grãos, indicação de track contado  

### 3.2 Servidor e acesso no celular

- [x] `server.mjs` — servidor estático Node  
- [x] **HTTPS** na porta **8443** (necessário para câmera fora de localhost)  
- [x] Geração automática de certificado PFX (PowerShell + `.certs/dev.pfx`)  
- [x] Modo HTTP opcional: `npm run http` → porta 8080 (só com ressalvas para câmera)  
- [x] `package.json` com scripts `start` / `http`  
- [x] `.gitignore` incluindo `.certs/` e `node_modules/`  
- [x] Liberação de firewall de entrada na porta 8443 (regra Windows “Esteira HTTPS 8443”)  

### 3.3 Melhorias de detecção (v2 → v3)

- [x] **Modo contraste com a esteira** (recomendado): percentil escuro na ROI + offset  
- [x] **Modo limiar local**: comparação com média local (iluminação irregular)  
- [x] **Modo limiar absoluto** (clássico do protótipo)  
- [x] Blur em caixa + morfologia (abertura / separação de grãos)  
- [x] Faixa **ROI** central com preview  
- [x] Filtros de forma (aspect ratio, preenchimento do bounding box)  
- [x] Tracking com predição de velocidade + estabilidade mínima antes de contar  
- [x] **Auto calibrar** (histograma na ROI, Otsu de referência, ajuste de contraste e áreas)  
- [x] Correção de alinhamento vídeo/overlay (`object-fit: contain` + mapeamento)  
- [x] Métricas: taxa / min, tempo de sessão  
- [x] Persistência de calibração em `localStorage` (`esteira-calib-v3`)  
- [x] README atualizado com fluxo de calibração e HTTPS  

### 3.4 Documentação e ops

- [x] README.md operacional  
- [x] Este **mapa de bordo**  

---

## 4. Arquitetura atual

```
[Celular no tripé]
      │  HTTPS :8443 (mesma rede / hotspot)
      ▼
[PC — node server.mjs]
      │  arquivos estáticos
      ▼
[Browser]
  video → canvas processo (luminância → máscara → blobs)
       → tracking → contagem na linha
       → overlay + HUD
```

| Arquivo | Papel |
|---------|--------|
| `index.html` | Estrutura da UI e painel de calibração |
| `styles.css` | Layout e tema visual |
| `app.js` | Pipeline de visão, tracking, contagem, calibração |
| `server.mjs` | Host HTTP(S) local |
| `package.json` | Scripts npm |
| `.certs/` | Certificado de desenvolvimento (não versionar) |
| `README.md` | Como rodar e calibrar |
| `MAPA-DE-BORDO.md` | Estado do projeto (este arquivo) |

**Pipeline de visão (resumo):**  
frame → luminância → blur → máscara (contraste / local / absoluto) → ROI → morfologia → blobs → match de tracks → cruzamento da linha → total++.

---

## 5. Como rodar (referência rápida)

```bash
cd esteira
npm start
```

- PC: `https://localhost:8443`  
- Celular: `https://<IP-do-PC>:8443` (aceitar aviso de certificado)  
- Descobrir IP no Windows: `ipconfig` (IPv4 do Wi‑Fi / adaptador do hotspot)  
- IP **muda** se a rede/hotspot mudar — não reutilizar IP antigo  
- Firewall deve permitir TCP **8443** (entrada)

---

## 6. Pendências

Itens ainda **não resolvidos** ou só parcialmente válidos.

### 6.1 Qualidade da contagem

- [ ] Validar acurácia com lotes de tamanho conhecido (ex.: 50, 100 grãos) e registrar erro  
- [ ] Ajuste fino em cenários reais: grãos colados, esteira com pó, reflexos, luz fraca  
- [ ] Separação mais forte de **grãos grudados** (watershed / distance transform) quando morfologia não basta  
- [ ] Distinguir grão partido vs grão inteiro (se o negócio exigir)  
- [ ] Testar tipos de grão além de arroz (feijão, milho — tamanhos e cores diferentes)

### 6.2 Infra e setup

- [ ] Instalar/configurar Git de forma estável na máquina de desenvolvimento (no início da sessão não estava no PATH)  
- [ ] Certificado confiável local (mkcert) para evitar “site não seguro” no celular  
- [ ] Hotspot: em alguns Androids, isolamento de clientes ainda pode atrapalhar o acesso — documentar workaround (túnel Cloudflare / USB + adb reverse) se voltar a falhar  
- [ ] Script único “primeiro uso” (abrir firewall + gerar cert + printar QR com URL)  
- [ ] Empacotar como PWA (ícone, tela cheia, instalação no celular)

### 6.3 Produto / UX

- [ ] Modo “só visualizar detecção” sem contar (já há pausa; falta UX de calibração guiada passo a passo)  
- [ ] Feedback sonoro/háptico a cada contagem  
- [ ] Exportar contagem (CSV / compartilhar) com timestamp e parâmetros de calibração  
- [ ] Presets salvos por tipo de grão / iluminação (“arroz – luz de cima”)  
- [ ] Bloqueio de orientação / dica de enquadramento no tripé  

### 6.4 Git / repositório

- [ ] (Este item fecha com o commit/push deste mapa, se bem-sucedido) Garantir histórico limpo na `main` com a stack atual completa  

---

## 7. Novas ideias para implementar

Prioridade sugerida (P0 = logo, P2 = depois).

| Prioridade | Ideia | Por quê |
|------------|--------|---------|
| **P0** | **Modo validação**: usuário digita “contei N grãos manualmente” e o sistema mostra desvio | Fecha o loop de qualidade da detecção |
| **P0** | **Túnel HTTPS opcional** (Cloudflare Tunnel / similar) | Evita dor de IP/firewall/hotspot em campo |
| **P0** | **QR Code na tela do PC** com a URL `https://IP:8443` | Setup em 5 segundos no tripé |
| **P1** | **Subtração de fundo / frame de referência** da esteira vazia | Mais robusto a manchas na correia |
| **P1** | **Watershed / DT** para separar blobs grandes em N grãos estimados | Densidade alta na correia |
| **P1** | **Taxa em janela móvel + alarme** se taxa cair (obstrução / fim de batelada) | Uso industrial/demo mais sério |
| **P1** | **Roi arrastável** (não só largura centrada) e linha arrastável no toque | Calibração mais intuitiva |
| **P1** | **Perfil de câmera**: fixar foco/exposição se o browser expuser constraints | Menos “respiração” do auto-ISO |
| **P2** | **Backend leve** (opcional) para log de turnos e multi-dispositivo | Dashboard de produção |
| **P2** | **WebWorker / WebGL** no pipeline | FPS mais estável em celulares fracos |
| **P2** | **Fallback com modelo leve** (TF.js / ONNX) só se contraste falhar | Híbrido, sem abandonar o modo clássico |
| **P2** | **Contagem por “gate” múltiplo** (2 linhas) para rejeitar contagem ambígua | Menos falso positivo |
| **P2** | **Simulador offline** com vídeo gravado da esteira | Regredir algoritmo sem hardwares |
| **P2** | App Android wrapper (Capacitor/TWA) só se PWA + HTTPS local não bastar | Distribuição a operadores |

### Ideias de produto (fora do núcleo técnico)

- Meta de produção por turno + gráfico simples  
- Multilíngua (pt/en)  
- Modo kiosk (esconder calibração atrás de PIN)  
- Integração com balança / PLC (serial/socket) se o cenário industrial exigir  

---

## 8. Riscos conhecidos

| Risco | Efeito | Mitigação atual / futura |
|-------|--------|---------------------------|
| IP do hotspot muda | Link do celular quebra | Sempre ler IP novo; QR automático |
| Certificado self-signed | Aviso assustador / bloqueio em alguns browsers | mkcert ou túnel com cert válido |
| Grãos colados | Subcontagem | Morfologia + (futuro) watershed |
| Luz lateral / reflexo | Contagem a mais | ROI estreita, filtro de forma, contraste |
| `getUserMedia` sem HTTPS | Câmera não abre | Servidor HTTPS padrão |
| Isolamento de hotspot Android | Celular não acessa o PC | Túnel / USB reverse / outra rede |
| Git ausente na máquina | Dificulta commit/push | Instalar Git e versionar este mapa |

---

## 9. Decisões técnicas (não reabrir sem motivo)

1. **Sem YOLO na v1** — prioridade real-time no browser.  
2. **Tudo no cliente** para contagem — sem backend obrigatório.  
3. **HTTPS local** em vez de gambiarra HTTP + flags de browser.  
4. **Linha virtual + tracking** em vez de “só contar blobs no frame” (evita multi-contagem do mesmo grão).  
5. **Calibração manual + auto** — operador no campo sempre precisa poder ajustar.

---

## 10. Checklist de sessão de teste em campo

1. `npm start` no PC  
2. Confirmar IP (`ipconfig`) e firewall 8443  
3. Celular: abrir HTTPS, aceitar cert, iniciar câmera  
4. Enquadrar esteira na ROI  
5. Ver máscara → Auto calibrar → ajustar contraste/área  
6. Zerar → passar lote conhecido → anotar erro  
7. Salvar calibração no dispositivo  

---

## 11. Changelog resumido desta evolução local

1. Download do repo e organização em `esteira/`  
2. Servidor HTTPS + firewall + documentção de IP do hotspot  
3. Pipeline v3 (contraste esteira, local, auto, ROI, tracking melhorado)  
4. UI/HUD (taxa, sessão, modos, auto calibrar)  
5. Mapa de bordo + commit planejado na `main`  

---

## 12. Próximo passo recomendado

1. Sessão de **validação com lote conhecido** e anotar % de erro.  
2. Se erro > ~5–10%, priorizar **subtração de fundo** + **separação de blobs**.  
3. Se setup de rede continuar frágil em campo, priorizar **QR + túnel HTTPS**.  

---

*Este arquivo é vivo: atualize a data no topo e marque checkboxes conforme o projeto avançar.*
