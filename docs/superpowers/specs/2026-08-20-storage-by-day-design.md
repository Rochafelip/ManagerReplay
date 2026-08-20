# Armazenamento por dia (em vez de por câmera)

Decidido em conversa direta com o usuário (mudança grande, aprovada sem brainstorm visual).

## 1. Estrutura de pastas: dia, não câmera

Hoje: `storage_root/camera-{N}/{session_id}_parte{P}.webm`.

Depois: `storage_root/{YYYY-MM-DD}/camera{N}_{session_id}_parte{P}.webm`.

- A data da pasta vem dos 10 primeiros caracteres do `session_id` (que já é um timestamp ISO gerado no client, ex: `2026-08-20T18-32-10-123Z` → pasta `2026-08-20`), não da hora em que o chunk chega no servidor — assim uma sessão que atravessa a meia-noite continua inteira na mesma pasta.
- Dentro da pasta do dia, os arquivos das duas câmeras ficam misturados; o nome do arquivo (`camera1_...` / `camera2_...`) diz de qual câmera é.

`server/storage.py`: `build_camera_dir(storage_root, camera_id)` vira `build_day_dir(storage_root, session_id)`. `save_chunk` passa a receber `camera_id` também, pra montar o nome do arquivo com o prefixo `camera{N}_`.

`server/chunks_receiver.py`: `_handle_upload` chama `build_day_dir` em vez de `build_camera_dir`, e passa `camera_id` pro `save_chunk`.

## 2. Exibição amigável em `files.html`

Pastas cujo nome bate com `YYYY-MM-DD` aparecem na listagem como "📅 Replay do dia DD/MM/AAAA" em vez do nome cru da pasta. Outras entradas (arquivos, pastas com outro nome — inclusive as pastas antigas `camera-1`/`camera-2`) continuam exibidas como hoje.

## Fora do escopo

- Migração das gravações já existentes em `camera-1`/`camera-2` — ficam como estão, sem script de migração (dado de spike/teste).
- Mudança em `client.js` — o `session_id` já é gerado no formato certo, nada muda do lado do celular.
