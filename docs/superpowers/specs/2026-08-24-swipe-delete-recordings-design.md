# Swipe-to-delete com senha admin

## Problema

`files.html` não tem nenhuma forma de apagar gravações — só listar e baixar. Precisa de um jeito de deletar (arquivos individuais ou pastas de dia inteiro), protegido por senha, pra evitar que qualquer pessoa com acesso ao Wi-Fi da hotspot apague gravações por engano ou de propósito.

## Senha admin

Um arquivo de texto simples no Pi, fora do repo: `~/managerreplay/admin-password.txt`, permissão `600` (só o dono lê). Lido uma vez na subida do servidor (`chunks_receiver.build_server`), guardado em memória no handler. Sem hash — não é um sistema com contas de usuário, é uma senha local única pra travar uma ação destrutiva; texto puro com permissão de arquivo restrita é proporcional ao risco de um projeto de time de várzea. Comparação feita com `hmac.compare_digest` pra evitar timing attack.

O caminho do arquivo é configurável via `--admin-password-file` (novo argumento em `app.py`, default `~/managerreplay/admin-password.txt`). Se o arquivo não existir na subida, o servidor recusa iniciar (erro claro, em vez de deletar sem senha nenhuma por engano).

## Endpoint `POST /delete-file`

Corpo `application/x-www-form-urlencoded` ou JSON com `path` (mesmo formato de path relativo usado em `/files-list`) e `password`.

Fluxo no servidor:
1. Senha errada → `403`, corpo `{"error": "senha incorreta"}`.
2. `path` resolvido contra `storage_root`; se escapar da raiz (mesma checagem de `file_listing.list_directory`) → `400`.
3. Se o alvo é diretório → `shutil.rmtree`.
4. Se o alvo é uma gravação "virtual" mesclada (nome no formato `cameraN_SESSION.webm`, sem existir de verdade — ver `file_listing._group_recording_parts`) → usa `storage.find_session_parts(day_dir, camera_id, session_id)` pra achar e apagar todos os `_parteN.webm` daquela sessão.
5. Senão (arquivo solto que existe de verdade) → apaga o arquivo direto.
6. Sucesso → `200 {"ok": true}`. Alvo inexistente → `404`.

## `files.html`: gesto de swipe

Cada `.entry` (arquivo ou pasta) ganha:
- Um wrapper que permite swipe horizontal via touch (`touchstart`/`touchmove`/`touchend`, sem biblioteca externa — o projeto não usa nenhuma até agora).
- Puxar pra esquerda além de um threshold (~60px) revela um botão vermelho "Excluir" atrás do card; soltar antes do threshold volta pro lugar (snap-back).
- Tocar em "Excluir" abre um modal simples (mesmo padrão visual do modal de certificado em `index.html`) pedindo a senha admin, com campo `type="password"`.
- Confirmar → `POST /delete-file`. Sucesso: remove o card da lista com uma transição rápida. Senha errada: mostra erro inline no modal, mantém aberto pra tentar de novo. Outro erro: mostra o erro e fecha o modal.
- Como é touch-only (swipe), desktop/mouse não tem como disparar o delete por engano — aceitável pra esse app, que é usado majoritariamente em celular.

## Escopo

Funciona tanto em arquivos de gravação quanto em pastas de dia inteiro (mesmo endpoint, mesmo gesto) — apagar uma pasta remove todas as gravações daquele dia de uma vez.

Fora de escopo: desfazer/lixeira (delete é permanente), rate-limiting de tentativas de senha (risco baixo — rede local isolada, sem internet).

## Testes

- `tests/server/test_chunks_receiver.py`: cobre `/delete-file` com senha certa/errada, deleção de arquivo solto, de gravação mesclada (múltiplas partes), de pasta inteira, e tentativa de escapar da storage_root (`../`).
- Sem teste automatizado pro gesto de swipe (é interação de touch em HTML/JS puro, sem framework de teste de UI no projeto) — verificação manual num celular.

## Deploy

Além do rsync dos arquivos alterados, precisa criar o arquivo de senha no Pi antes do primeiro restart com essa mudança:
```bash
echo -n "SUA_SENHA_AQUI" > ~/managerreplay/admin-password.txt
chmod 600 ~/managerreplay/admin-password.txt
```
