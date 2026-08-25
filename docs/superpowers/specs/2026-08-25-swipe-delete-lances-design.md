# Swipe-to-delete em Lances

## Problema

`lances.html` só lista e permite baixar clipes — sem forma de apagar um lance indesejado (gravado por engano, nome errado etc). `files.html` já resolveu esse problema pra gravações inteiras (ver `2026-08-24-swipe-delete-recordings-design.md`); Lances precisa do mesmo tratamento, mas apaga um **evento** (linha em `events.jsonl`) além do arquivo de clipe, não só um arquivo solto.

## Backend: `events.remove_event`

Nova função em `server/events.py`:

```python
def remove_event(events_file: Path, nome: str) -> dict | None:
```

Lê todas as linhas de `events_file`, filtra fora a que tem `"nome" == nome`, reescreve o arquivo com o restante. Retorna o dict do evento removido (mesmo formato de `record_event`/`list_events` — `nome`/`timestamp`/`camera`), ou `None` se nenhum evento com esse nome existia (arquivo inalterado). O handler usa o `camera`/`timestamp` retornados pra montar o caminho do clipe físico a apagar (ver endpoint abaixo). `nome` é único por construção (`_next_name` numera sequencialmente, "Lance Epico 001", "002"...), então nunca precisa desambiguar duplicatas.

## Endpoint `POST /delete-lance`

Corpo `application/x-www-form-urlencoded` com `password`; `nome` vem na query string (`?nome=<nome>`), mesmo padrão de `path` em `/delete-file`.

Fluxo no servidor (`chunks_receiver._handle_delete_lance`):
1. Senha errada → `403`, mesmo formato de erro de `/delete-file`.
2. `removed = remove_event(self.events_file, nome)` — se `removed` for `None` (evento não existe) → `404`.
3. Best-effort: tenta apagar o clipe físico associado — `self.storage_root / removed["timestamp"][:10] / "lances" / f"lance_camera{removed['camera']}_{sanitize_lance_name(nome)}.webm"`. Se o arquivo não existir, ignora (não é erro — o evento pode ter sido registrado sem o upload do clipe ter completado).
4. Sucesso → `204`.

Reaproveita `self.admin_password` e o mesmo `hmac.compare_digest`, já carregado no handler — sem mudança em `build_server`/`run`.

## `lances.html`: gesto de swipe

Mesmo padrão de `files.html` (`_MERGED_RECORDING_PATTERN`/swipe não se aplica aqui — cada card já é um evento único, sem conceito de "partes"):
- Cada `.card.lance-card` vira um wrapper de swipe (`touchstart`/`touchmove`/`touchend`), revela botão "Excluir" ao arrastar ~60px pra esquerda.
- Tocar em "Excluir" abre modal pedindo senha admin (mesmo componente visual de `files.html`).
- Confirmar → `POST /delete-lance?nome=<nome do evento>`. Sucesso: remove o card da lista. Senha errada: erro inline no modal. Outro erro: mostra erro, fecha modal.
- Como o clique em "Baixar" (`<a class="lance-action" href=... download>`) já é um link separado do card inteiro (não é um card clicável como um todo), o swipe não precisa suprimir nenhum clique de navegação — só precisa não interferir no link de download quando não há swipe ativo.

## Correção: `CAMERA_LABELS` desatualizado em `lances.html`

Linha 82 (`const CAMERA_LABELS = { 1: "Gol", 2: "Lateral Esquerda", 3: "Lateral Direita", 4: "Geral" };`) ficou pra trás nas duas renomeações anteriores (campo de futebol com 5 posições, depois rename pra Gol A/B). Atualiza pro mesmo mapa de `cameras.html`/`gravando.html`:
```js
const CAMERA_LABELS = { 1: "Gol A", 2: "Gol B", 3: "Arquibancada A", 4: "Arquibancada B", 5: "Geral" };
```

## Fora de escopo

Desfazer/lixeira (delete é permanente, mesma decisão de `files.html`). Rate-limiting de senha (mesma justificativa: rede local isolada).

## Testes

- `tests/server/test_events.py`: cobre `remove_event` — remove o evento certo por nome, retorna `None`/falsy quando nome não existe, preserva os outros eventos na ordem.
- `tests/server/test_chunks_receiver.py`: cobre `/delete-lance` com senha certa/errada, evento inexistente (`404`), remoção bem-sucedida (evento some de `/events-list` E clipe físico é apagado se existia), e o caso do evento sem clipe físico (não deve dar erro).
- Sem teste automatizado pro gesto de swipe em si (mesma limitação de sempre, sem framework de UI no projeto) — verificação manual.
