# Spike 2 — Capacidade de captura de vídeo do Raspberry Pi 3B (1 e 2 câmeras)

## Contexto

O Raspberry Pi 3B (1GB RAM, quad-core ARM Cortex-A53 1.2GHz, Wi-Fi 2.4GHz 802.11n) é o hub central do HighlightBox/ManagerReplay: ele cria a rede Wi-Fi local (hotspot), recebe os streams de vídeo dos celulares-câmera e grava em disco. O caso de uso mínimo viável do produto exige pelo menos 2 câmeras simultâneas. Não existe relato documentado de um Pi 3B recebendo múltiplos streams WebRTC 1080p simultâneos (Risco 2 do contexto do projeto), e o rádio Wi-Fi 2.4GHz pode saturar antes mesmo da CPU virar o gargalo (Risco 3).

Este spike responde uma pergunta binária por combinação testada: **o Pi 3B aguenta gravar N câmeras simultâneas, usando o método de transporte X, sem travar?** Não é a arquitetura de produção — é código descartável, focado em medir capacidade real de hardware antes de investir nas fases seguintes do roadmap (Fase 03 em diante).

## Objetivo e critério de sucesso

Para cada rodada de teste, o critério de aprovação é:

- O Pi não trava nem reinicia durante o teste inteiro.
- `vcgencmd get_throttled` não acusa flag de subvoltagem/throttling em nenhum momento do teste.
- Os arquivos de vídeo gravados por cada câmera abrem e tocam sem corrupção ao final.

CPU, RAM e temperatura são registrados via o script `monitor.sh`/`monitor2.sh` já existente (log em CSV) como dado de referência para a decisão de arquitetura — não são critério de corte nesta rodada, já que ainda não há baseline empírico para definir limiares numéricos.

## Matriz de testes e ordem de execução

Quatro rodadas, sempre nessa ordem (baseline de 1 câmera antes de escalar para 2):

1. 1 câmera, MediaRecorder + chunks HTTP
2. 1 câmera, WebRTC
3. 2 câmeras, MediaRecorder + chunks HTTP
4. 2 câmeras, WebRTC

Cada rodada segue duas etapas:

1. **Smoke test** (~2-3 minutos): valida que a câmera conecta, transmite e o servidor grava, sem gastar tempo se algo estiver quebrado de forma óbvia.
2. **Rodada completa** (15-20 minutos), só executada se o smoke test passar, replicando a duração já usada no Spike 2 original de 1 câmera do roadmap.

Se uma rodada falhar o critério de sucesso, o resultado é documentado e o teste segue para a próxima combinação da matriz — o objetivo é mapear as 4 combinações, não parar no primeiro fracasso. Exceção: se o Pi travar de um jeito que exija reboot manual, a próxima rodada só começa depois de recuperar o Pi.

## Arquitetura técnica

- **Servidor único em Python** (`spike2_server.py`), descartável, com modo selecionado por flag de linha de comando: `--mode=chunks|webrtc --cameras=1|2`.
  - **Modo `chunks`**: endpoint HTTP que recebe blobs de vídeo via `POST` a cada 5-10s (cliente grava com a `MediaRecorder API`), gravando sequencialmente em disco por câmera.
  - **Modo `webrtc`**: usa a biblioteca `aiortc` (WebRTC em Python) para receber o track de vídeo de cada câmera e gravar em disco. Cada câmera é uma conexão peer-to-peer direta com o servidor — sem SFU real, o que é suficiente para medir capacidade bruta de recepção/gravação com até 2 câmeras.
- **Cliente**: página HTML simples servida pelo próprio `spike2_server.py`, com toggle de modo, usando `getUserMedia` limitado a 720p (para não confundir o teste do pipeline de captura com saturação de banda em 1080p — ver seção "Fora do escopo"). Roda no navegador dos 2 celulares Android usados no teste.
- **Armazenamento**: grava em `~/highlightbox-spike2/{modo}/{n-cameras}/camera-{id}/`, isolado da estrutura de produção (`/opt/highlightbox/`) e do SQLite — este spike não usa banco de dados.
- **Monitoramento**: o servidor dispara/acompanha o `monitor.sh` já existente no início de cada rodada e marca o CSV com um identificador da rodada (ex: `2cam_webrtc_full`), para permitir cruzar os logs com a matriz de resultados depois.

## Rede

O hotspot do Pi roda **apenas em modo aberto (sem senha)** via `nmcli device wifi hotspot` durante este spike. A validação de WPA2 (Risco 4 — bug de kernel panic documentado no chip BCM43438 em modo AP com WPA2) fica para uma rodada de validação separada, fora do escopo deste spike.

## Dispositivos de teste

2 celulares Android (evita misturar, neste teste, o risco de capacidade do Pi com o risco de HTTPS/certificado do Safari em iPhone, que já foi tratado separadamente no Spike 1).

## Saída esperada

Uma tabela comparativa em Markdown com as 4 rodadas, contendo: combinação testada, passou/falhou, CPU médio/pico, RAM, temperatura, ocorrência de throttling (sim/não), e observações livres. Essa tabela vira a base de decisão para escolher o transporte de vídeo (WebRTC vs MediaRecorder+chunks) a ser usado na Fase 03 do roadmap.

## Fora do escopo deste spike

- Teste em resolução 1080p (fica para uma rodada seguinte, se 720p passar em todas as 4 combinações).
- Hotspot com WPA2.
- Uso do SQLite ou da estrutura de diretórios de produção.
- Implementação de SFU real para WebRTC (o teste usa conexões peer-to-peer diretas, uma por câmera).
- Testes com iPhone.
- Definição de limiares numéricos de CPU/RAM/temperatura como critério de corte (fica para depois de ter dado empírico desta primeira rodada).
