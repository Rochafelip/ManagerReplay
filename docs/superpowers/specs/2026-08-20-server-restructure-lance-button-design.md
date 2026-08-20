# Reestruturação do projeto + botão de lance

## Contexto

O `spikes/spike2/` nasceu como código descartável só pra validar se o Pi 3B aguenta gravar 2 câmeras simultâneas (ainda em validação, não concluída). O usuário decidiu pausar essa validação e usar esse código já funcional (recepção HTTPS, hotspot, captura de câmera, chunks e WebRTC) como base real do produto ManagerReplay, abandonando o nome "spike" e adicionando a primeira feature de produto: um botão de "lance" (evento) com nome e timestamp, adiantando a Fase 07 do roadmap.

## Decisões

- **Stack**: continua em Python (não migra pra Kotlin/Ktor como o `ContextoProjeto.md` original previa) — reaproveita o pipeline já testado neste hardware.
- **Transporte de vídeo**: mantém os dois modos (`chunks` e `webrtc`) como estavam, nenhuma decisão final ainda entre eles.
- **Registro de lances**: log simples em JSON Lines (`~/managerreplay-data/events.jsonl`), não SQLite ainda — migração pra SQLite fica pra uma iteração futura, mas o formato do registro (`nome`, `timestamp`, `camera`) já é compatível com a futura tabela `events`.

## Reestruturação de pastas

- `spikes/spike2/` → `server/` (pacote Python `server`, não mais `spikes.spike2`).
- `spikes/spike2/spike2_server.py` → `server/app.py`.
- `spikes/spike2/storage.py`, `chunks_receiver.py`, `webrtc_receiver.py`, `static/` mantêm nome e função, só mudam de pacote.
- Novo `server/events.py`: funções puras pra registrar e listar lances (testável sem rede).
- `tests/spikes/spike2/` → `tests/server/`.
- `spikes/` (pasta vazia depois da migração) é removida.

## Botão de lance

- Em `capture.html`, um botão "⚡ Lance" abaixo do seletor de câmera.
- Ao tocar, `POST /events` com `{camera_id}` — servidor gera o nome (`LanceEpico 001`, `002`, ...; contador incremental persistido no próprio arquivo, calculado pela contagem de linhas existentes) e o timestamp (UTC ISO 8601, gerado no servidor pra evitar depender do relógio do celular).
- Resposta mostra o nome do lance registrado na tela por alguns segundos (feedback visual de confirmação).
- Cada linha do `events.jsonl`: `{"nome": "LanceEpico 001", "timestamp": "2026-08-20T18:32:10Z", "camera": "1"}`.

## Fora do escopo desta iteração

- SQLite, tabela `events` real.
- Associação a uma "partida"/`game` (ainda não existe conceito de jogo iniciado/encerrado).
- Geração de highlight (30s antes/depois do lance) — só o registro do evento.
- Autenticação/perfil de administrador.
