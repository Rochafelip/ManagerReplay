# Campo de futebol na escolha de câmera

## Problema

A escolha de câmera em `cameras.html` hoje é uma lista vertical de 4 cards genéricos ("Gol", "Lateral Esquerda", "Lateral Direita", "Geral"). Não transmite visualmente onde cada câmera fica no campo. Quer uma experiência mais intuitiva: um desenho de campo de futebol com marcadores nas posições reais, e escalar de 4 pra 5 câmeras simultâneas.

## Escopo

- 5 slots fixos (`camera_id` 1 a 5), com labels e posições novas.
- Lista vertical de cards é **substituída** pelo campo — não fica como alternativa.
- `--cameras` no CLI passa a aceitar até 5.
- Fora de escopo: mudança de storage/backend além do `choices` do argparse, autenticação, validação de hardware pra 5 câmeras simultâneas na Pi 3B (nunca foi testado nem pra 2 — ver `ContextoProjeto.md`; assumir 5 é um teto de UI, não uma promessa de performance).

## Slots, labels e posição no campo

| camera_id | label                  | posição no SVG              |
|-----------|------------------------|------------------------------|
| 1         | Gol Esquerdo           | centro da baliza esquerda    |
| 2         | Gol Direito             | centro da baliza direita     |
| 3         | Arquibancada Esquerda   | meio da linha lateral de cima |
| 4         | Arquibancada Direita    | meio da linha lateral de baixo |
| 5         | Geral                   | centro do campo (círculo central) |

(`camera_id` continua sendo o inteiro 1-5 usado internamente/storage, como hoje — só a UI muda.)

## `cameras.html`: campo SVG

- Um único `<svg viewBox="0 0 280 180">` desenhando um campo horizontal simplificado: retângulo verde, linha de meio-campo, círculo central, duas pequenas áreas de gol — traços brancos sobre fundo verde, sem grama/textura realista (é um diagrama, não uma foto).
- O SVG usa `width: 100%; height: auto;` dentro de um container `max-width` alinhado ao restante do layout do app (`.page`), então encolhe pra caber na largura do celular sem precisar girar o aparelho ou rolar horizontalmente — os 5 marcadores continuam grandes o bastante pra tocar mesmo menores (mínimo ~28px de área de toque efetiva, usando um círculo transparente maior por trás do ícone visível, se o marcador visual for menor que isso).
- Cada marcador é um `<circle>` (ou grupo `<g>`) posicionado nas coordenadas da tabela acima, com um rótulo curto ao lado/abaixo (label completo aparece no painel de detalhe, não precisa caber inteiro no SVG).
- Cor do marcador usa `var(--accent)` (roxo do tema) quando livre; muda pra um tom apagado (cinza, ex: `#94a3b8`) e perde interatividade (`pointer-events: none` ou handler que não faz nada) quando ocupado — mesma lógica de "slot-busy" que já existe hoje.
- **Interação:** tocar num marcador livre o destaca (contorno/anel de seleção) e revela, abaixo do SVG, um painel com o nome da posição + os dois botões de lente já existentes (**Câmera Traseira** / **Câmera Frontal**), exatamente como o card individual mostra hoje. Tocar em outro marcador troca a seleção (painel atualiza, sem precisar recarregar a página). Tocar num marcador ocupado não faz nada (ou, na melhor das hipóteses, mostra um texto "Em uso" no lugar do painel de lentes — decisão de implementação, sem gerar novo elemento de layout).
- O polling de `/recording-status` a cada 3s (já existente) continua igual — só muda o que é atualizado visualmente: os marcadores (cor + interatividade) em vez dos cards da lista. Mesmo comportamento fail-open se a consulta falhar (assume "nenhum slot ocupado conhecido").
- O fluxo de nome (`#name-input`, sugestão por modelo do aparelho, `localStorage`) não muda — o campo aparece exatamente onde a lista de cards aparecia hoje (`#camera-step`, visível só depois de preencher o nome).

## `app.py`

- `--cameras` muda de `choices=[1, 2, 3, 4]` pra `choices=[1, 2, 3, 4, 5]`.

## Backend (`chunks_receiver.py`, `sessions.py`)

Sem mudanças — `n_cameras` já é só metadado armazenado no handler (confirmado em código), sem validação ativa contra `camera_id`. `sessions_registry`/`start_session`/`stop_session`/`list_sessions`/`/recording-status` já são genéricos por `camera_id` inteiro, funcionam pra 5 sem alteração.

## Deploy

1. `rsync` de `server/` (inclui `cameras.html` alterado).
2. Editar `/etc/systemd/system/managerreplay-server.service` na Pi: trocar `--cameras=4` (ou o valor atual) por `--cameras=5`.
3. `sudo systemctl daemon-reload && sudo systemctl restart managerreplay-server`.

## Testes / verificação

Sem suite automatizada de UI (mesma limitação de sempre — sem framework de teste de UI no projeto). Verificação manual:
- Abrir `cameras.html`, digitar nome, ver o campo com 5 marcadores nas posições da tabela.
- Tocar num marcador livre — vê o painel com nome da posição + botões de lente aparecer.
- Tocar em outro marcador — painel atualiza pra nova posição, sem duplicar.
- Iniciar gravação num slot a partir de um celular; abrir `cameras.html` num segundo celular — o marcador correspondente deve ficar acinzentado/não-interativo dentro de ~3s.
- Parar a gravação; o marcador volta a ficar livre no próximo poll.
- Confirmar que os links de lente (`capture.html?mode=chunks&camera=${id}&facing=${facing}&name=${encoded}`) continuam funcionando exatamente como hoje.
