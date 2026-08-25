# Versão do sistema na tela Monitor

## Problema

Não existe hoje nenhum jeito de saber, olhando o app rodando na Pi, se um deploy recente realmente pegou (rsync rodou, serviço reiniciou, celular não está com página em cache). Precisa de um número de versão visível que o operador possa comparar com o que ele esperava ter deployado.

## Arquivo `VERSION`

Um arquivo de texto simples na raiz do repo, `VERSION`, contendo só o número (ex: `1.0`), sem quebra de linha extra. Commitado no git — faz parte do histórico do projeto, igual qualquer outro arquivo versionado.

Começa em `1.0`. Bump manual: sempre que o desenvolvedor achar que vale marcar uma mudança como nova versão, edita esse arquivo antes de commitar (sem regra automática de quando incrementar — critério do desenvolvedor).

Sem validação de formato — qualquer texto simples serve (não precisa ser `X.Y` estrito). O objetivo é comparação visual por uma pessoa, não parsing por máquina.

## Leitura no servidor

`app.py` ganha um novo argumento `--version-file`, default `VERSION` relativo à raiz do repo (mesmo diretório de onde `app.py` já espera ser executado — `~/managerreplay/server/../VERSION` na Pi, ou seja, o rsync do passo de deploy precisa incluir esse arquivo).

Lido uma vez na subida do servidor (mesmo padrão do `admin_password_file` em `chunks_receiver.build_server`): se o arquivo não existir, o servidor recusa iniciar com um erro claro. O conteúdo (trimmed) fica guardado em memória.

## Endpoint `/monitor-status`

`monitor_status.read_live_status()` ganha mais uma chave no dict retornado: `"app_version"`, com o valor lido do `VERSION`. Não precisa de leitura de disco a cada request — o valor já está em memória desde a subida do servidor, então é passado como parâmetro pra `read_live_status()` (ou composto no handler depois de chamar a função, seguindo o padrão que for mais simples de encaixar no código atual).

## `monitor.html`: exibição

Novo card pequeno no topo do grid existente (antes ou junto do card de CPU/Temperatura), mostrando `Versão: v{app_version}` — texto simples, sem cor de status (não é uma métrica de saúde, não tem estado ok/warn/bad).

## Fora de escopo

- Comparação automática com uma versão "esperada" ou "mais recente" — não existe um servidor central de referência, a comparação é visual/manual pelo operador.
- Changelog ou histórico de versões dentro do app — só o número atual.
- Versionamento semântico estrito ou automação de bump (git hooks, CI) — puramente manual.

## Deploy

O rsync do código (`rsync -av --exclude .venv --exclude __pycache__ server/ rocha@<ip-da-pi>:~/managerreplay/server/`) não inclui o `VERSION`, que fica na raiz do repo, fora de `server/`. Precisa de um passo adicional:
```bash
scp VERSION rocha@<ip-da-pi>:~/managerreplay/VERSION
```
Isso será documentado no README como um lembrete no fluxo de deploy: bump do `VERSION` antes de commitar, e sincronizar esse arquivo junto no deploy.

## Testes

- `tests/server/test_monitor_status.py` (ou onde os testes de monitor já estiverem): cobre que `read_live_status`/o handler inclui `app_version` lido do arquivo informado.
- `tests/server/test_chunks_receiver.py` ou `test_app.py`: cobre que o servidor recusa subir se `--version-file` apontar pra um caminho inexistente (mesmo padrão do teste já existente pro `admin_password_file`).
- Sem teste automatizado pra exibição no `monitor.html` (sem framework de teste de UI no projeto) — verificação manual.
