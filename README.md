# Esteira — contagem de grãos (protótipo)

Aplicação web simples para contar grãos em esteira **preta** com grãos **claros**, sem IA.

## Como funciona

1. Abre a câmera do dispositivo no navegador.
2. Converte cada frame para brilho e aplica um **limiar** (esteira escura some; grãos claros ficam).
3. Encontra **blobs** (grupos de pixels claros) por área.
4. Rastreia o centro de cada grão entre frames.
5. Soma **1** quando o centro **cruza a linha virtual** na direção da esteira.

## Como rodar (local)

Câmera no navegador exige origem segura: `localhost` ou HTTPS.

```bash
# na pasta do projeto
python -m http.server 8080
```

Abra: http://localhost:8080

No celular da mesma rede Wi‑Fi, use o IP do PC (ex.: `http://192.168.x.x:8080`).  
Alguns navegadores mobile só liberam câmera em **HTTPS** — no host definitivo isso resolve.

## Calibração

| Controle        | Uso |
|-----------------|-----|
| Limiar          | Suba até a esteira sumir; grãos devem sobrar na máscara |
| Área min/max    | Filtra pó (min) e pedaços grandes / reflexos (max) |
| Linha           | Cruza o fluxo dos grãos |
| Direção         | Sentido real da esteira (evita contagem errada) |
| Ver máscara     | Confere se só os grãos estão brancos |

## Escopo do protótipo

- Tudo no navegador (HTML/CSS/JS).
- Sem backend e sem modelo de machine learning.
- Bom para demo; grãos colados ou iluminação instável exigem ajuste fino ou morfogia depois.
