# Esteira — contagem de grãos

Aplicação web para contar grãos em esteira **preta** com grãos **claros** (ex.: arroz), no navegador do celular ou PC — **sem IA**.

## Como funciona

1. Abre a câmera do dispositivo.
2. Reduz o frame, aplica blur leve e **limiar de brilho** (esteira some; grãos ficam).
3. Recorta uma **faixa ROI** central (só a esteira).
4. Limpa ruído com **morfologia** (abertura).
5. Encontra **blobs** por área e forma.
6. Rastreia centros entre frames (com predição de velocidade).
7. Soma **1** quando o centro **cruza a linha virtual** no sentido da esteira.

## Como rodar (esta máquina)

Node.js necessário. Câmera no celular exige **HTTPS** (exceto `localhost`).

```bash
cd esteira
npm start
```

No terminal aparecem os links, por exemplo:

- PC: `https://localhost:8443`
- Celular (mesma Wi‑Fi): `https://10.50.x.x:8443`

No celular, **aceite o aviso de certificado** (Avançado → continuar). Depois toque em **Iniciar câmera**.

Só no PC / localhost:

```bash
npm run http
```

Abre em `http://localhost:8080`.

## Calibração

| Controle | Uso |
|----------|-----|
| **Modo de contagem** | **Esteira** = cruza a linha; **Instantâneo** = quantos na tela (teste na mesa) |
| Limiar | Suba até a esteira sumir; grãos devem sobrar na máscara |
| Área min/max | Filtra pó (min) e pedaços/reflexos (max) |
| Linha | Cruza o fluxo dos grãos (só no modo Esteira) |
| ROI | Faixa central — ignore fundo fora da esteira |
| Morfologia | 1–2 remove ruído; 0 se grãos sumirem |
| Match | Distância máxima para reassociar o mesmo grão |
| Direção | Sentido real da esteira |
| Ver máscara | Confere se só os grãos estão brancos |

**Contar agora** (modo Instantâneo): fixa o total no número de grãos visíveis no momento.

Use **Salvar calibração** para guardar no dispositivo (localStorage).

## Testes sintéticos

```bash
npm test
```

Gera frames falsos (esteira + elipses) e valida detecção instantânea, cruzamento de linha e rejeição de ruído.

## Fluxo sugerido no teste real

1. Fixe o celular no tripé, esteira bem iluminada de cima.
2. Ative **Ver máscara** e ajuste limiar + ROI.
3. Desligue a máscara, confira bolinhas nos grãos e a linha.
4. Passe grãos conhecidos (ex. 50) e compare o total.

## Escopo

- Tudo no navegador (HTML/CSS/JS + servidor local Node).
- Sem backend e sem modelo ML.
- Grãos colados demais ou iluminação muito irregular ainda contam mal — ajuste fino ou separar o fluxo ajuda.
