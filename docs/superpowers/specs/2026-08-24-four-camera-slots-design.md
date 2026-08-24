# 4 câmeras simultâneas com slots de posição e trava de ocupação

## Problema

O app hoje só suporta 2 câmeras simultâneas, fixadas por lente: "Câmera traseira" (`camera=1`, lente traseira travada) e "Câmera frontal" (`camera=2`, lente frontal travada). Precisa escalar pra 4 pessoas gravando ao mesmo tempo, com nomes de slot melhores que "Câmera 1/2", e impedir que duas pessoas escolham o mesmo slot sem saber que já está em uso.

## Escopo

- 4 slots fixos (`camera_id` 1 a 4), com labels de posição em vez de números.
- Lente (frontal/traseira) deixa de ser fixada por slot — vira escolha livre dentro da tela de gravação (`capture.html`), usando o seletor `#camera-device` que já existe.
- `cameras.html` passa a mostrar os slots já ocupados como desabilitados, consultando o estado de sessões ativas em tempo real.
- Não inclui: mudança de storage/backend, autenticação, ou suporte a mais de 4 slots (fora de escopo — o hardware da Pi 3B nunca foi validado nem pra 2 simultâneas, então 4 é o teto assumido pra este trabalho).

## Slots e labels

Mapeamento fixo `camera_id → label`, usado só na UI (o `camera_id` continua sendo o inteiro 1-4 usado internamente/storage, como hoje):

| camera_id | label              |
|-----------|--------------------|
| 1         | Gol                |
| 2         | Lateral Esquerda    |
| 3         | Lateral Direita     |
| 4         | Geral               |

## `cameras.html`

- Os dois links `<a class="camera-link" id="camera-N-link">` fixos (traseira/frontal) são substituídos por 4, gerados em JS a partir de um array `SLOTS = [{id:1,label:"Gol"}, {id:2,label:"Lateral Esquerda"}, {id:3,label:"Lateral Direita"}, {id:4,label:"Geral"}]`.
- O `href` de cada link aponta pra `capture.html?mode=chunks&camera=${id}&name=${encoded}` — **sem** o parâmetro `facing` (removido; a escolha de lente passa a ser só dentro do `capture.html`).
- Ao exibir a etapa de escolha de câmera (`#camera-step` visível), a página faz `fetch("/recording-status")` (endpoint já existente, usado em `gravando.html`) e cruza os `camera` das sessões ativas retornadas com os 4 slots: qualquer slot cujo `camera_id` apareça na lista fica com o link desabilitado (`pointer-events: none`, classe `.slot-busy`, texto trocado pra "Em uso", sem mostrar nome de quem está usando).
- Enquanto essa etapa estiver visível, repete essa consulta a cada 3s (`setInterval`), pra refletir alguém que começou a gravar depois que a página carregou. Para o polling quando a etapa não está mais visível (troca de nome, navegação pra outra página) — sem instância de timer vazando.
- Se a consulta a `/recording-status` falhar (rede instável), trata como "nenhum slot ocupado conhecido" (fail-open: melhor deixar escolher um slot que por acaso já está ocupado — o próprio backend segue funcionando com sessões por `camera_id`, não quebra — do que travar a tela inteira por causa da falha do polling).

## `client.js`

- `friendlyDeviceLabel`: hoje deriva o rótulo ("Frontal"/"Traseira") da variável global `facing` (fixa, vinda da URL). Passa a inferir por dispositivo, usando `matchesFacing(device.label, "user")` vs `matchesFacing(device.label, "environment")` pra decidir o prefixo de cada opção individualmente (com fallback "Câmera N" quando não dá pra inferir por nenhum dos dois).
- `populateDeviceSelect`: remove o filtro `matching = videoDevices.filter(d => matchesFacing(d.label, facing))` — lista **todos** os `videoinput` disponíveis, não só os do lado inicial.
- O primeiro `getUserMedia` continua pedindo `facing=environment` (traseira) como padrão inicial quando a URL não especifica — só a trava de "só posso trocar dentro do mesmo lado" é removida. Trocar de lente depois de iniciado continua usando o `switchCamera` já existente, sem mudança de comportamento aí.

## `app.py`

- `--cameras` passa de `choices=[1, 2]` pra `choices=[1, 2, 3, 4]`.

## Backend (`chunks_receiver.py`, `sessions.py`)

Sem mudanças. `n_cameras` já é só metadado armazenado no handler, sem validação ativa contra `camera_id`; o registro de sessões (`sessions_registry`, `start_session`/`stop_session`/`list_sessions`) já é genérico por `camera_id` inteiro, funciona pra 4 sem alteração. `/recording-status` já expõe esse registro.

## Deploy

Depois de implementado e testado localmente, no Pi:
1. `rsync` dos arquivos alterados (`cameras.html`, `client.js`, `app.py`... `app.py` só se o `--cameras` mudar de fato o processo, o que muda é o valor passado no systemd unit, não o arquivo em si precisa mudar — mas o `choices` do argparse precisa refletir o novo valor permitido).
2. Editar `/etc/systemd/system/managerreplay-server.service`: trocar `--cameras=1` por `--cameras=4`.
3. `sudo systemctl daemon-reload && sudo systemctl restart managerreplay-server`.

## Testes / verificação

Sem suite automatizada de UI. Verificação manual:
- Abrir `cameras.html`, digitar nome, ver os 4 slots com os labels de posição.
- Iniciar gravação num slot a partir de um celular; abrir `cameras.html` num segundo celular — o slot em uso deve aparecer desabilitado/"Em uso" dentro de ~3s.
- Parar a gravação no primeiro celular; o segundo celular deve ver o slot liberado no próximo poll.
- Dentro de `capture.html`, confirmar que o seletor de lente mostra tanto câmeras frontais quanto traseiras, independente de qual slot foi escolhido.
