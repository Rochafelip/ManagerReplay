# Painel "quem está gravando agora"

Decidido em conversa direta com o usuário (aprovado sem brainstorm visual, segue o padrão visual já estabelecido em `monitor.html`).

## 1. Registro de sessões em memória (`server/sessions.py`)

Um dicionário em memória (chave = `camera_id`), protegido por `threading.Lock` (o `ThreadingHTTPServer` atende requisições em threads paralelas). Reseta se o processo do servidor reiniciar — não precisa de banco, é estado efêmero igual ao resto do app.

Cada sessão guarda: `name` (operador), `quality`, `started_at` (timestamp), `chunks_received`, `bytes_received`, `last_chunk_at` (timestamp, atualizado a cada chunk recebido).

Funções puras testáveis (recebem `now` como parâmetro pra não depender do relógio real nos testes):

- `start_session(registry, camera_id, name, quality, now)` — cria/substitui a entrada da câmera.
- `stop_session(registry, camera_id)` — remove a entrada (não erro se não existir).
- `record_chunk(registry, camera_id, size_bytes, now)` — incrementa `chunks_received`/`bytes_received` e atualiza `last_chunk_at`, só se a câmera tiver sessão ativa (chunk chegando sem sessão registrada — ex: sessão perdida por restart do servidor — é ignorado silenciosamente, não quebra o upload).
- `list_sessions(registry, now)` — devolve lista de dicts prontos pra JSON: `camera`, `name`, `quality`, `elapsed_seconds`, `chunks_received`, `bytes_received`, `seconds_since_last_chunk` (`None` se nenhum chunk chegou ainda).

## 2. Endpoints novos em `chunks_receiver.py`

- `POST /session-start?camera=N&name=...&quality=...` → 204. Chamado pelo client ao iniciar gravação.
- `POST /session-stop?camera=N` → 204. Chamado pelo client ao parar.
- `GET /recording-status` → 200, JSON com a lista de `list_sessions(...)`.
- `_handle_upload` (já existe) passa a chamar `record_chunk` depois de salvar o chunk em disco.

## 3. `client.js`

- `beginRecording()`: faz `POST /session-start` com `camera`, `name` (vem de `operatorName`, já existente) e `quality` antes de iniciar o `MediaRecorder`.
- `endRecording()`: faz `POST /session-stop` depois de finalizar o upload do último chunk.
- Se `operatorName` estiver vazio (URL sem `name`), ainda assim manda a sessão (com nome vazio) — não bloqueia gravar sem nome, só a tela não vai identificar quem é.

## 4. Página nova `gravando.html`

Mesmo padrão visual do `monitor.html`: poll em `/recording-status` a cada 3s, um card por sessão ativa.

Cada card mostra: nome do operador + câmera, tempo gravando (MM:SS, calculado a partir de `elapsed_seconds`), qualidade (ex: "HD · 30fps"), e indicador de buffer — verde "🟢 enviando" se `seconds_since_last_chunk` < 30s (ou ainda `None`, chunk ainda não chegou mas sessão é recente), vermelho "🔴 sem sinal há Xs" se ≥ 30s.

Sem sessões ativas: "Ninguém gravando agora."

Link novo no menu (`index.html`), ao lado dos existentes.

## Fora do escopo

- Persistência das sessões em disco/banco — é só estado de exibição em tempo real, não histórico.
- Timeout automático que remove sessões travadas do registro — ficam visíveis com "sem sinal" indefinidamente até `/session-stop` ou reinício do servidor; não é um problema prático (jogo dura pouco, servidor reinicia entre jogos).
