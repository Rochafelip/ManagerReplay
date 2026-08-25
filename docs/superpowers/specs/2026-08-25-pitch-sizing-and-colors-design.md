# Ajustes de tamanho e cor no campo de câmeras

## Problema

O campo de futebol introduzido em `cameras.html` (ver `2026-08-25-football-pitch-camera-picker-design.md`) estica 100% da largura do container em qualquer tela — em tablet/desktop (onde `.page` já permite até 640px) fica desproporcionalmente grande. Além disso todos os marcadores usam a mesma cor (roxo do tema), sem indicar visualmente o lado do campo.

## Tamanho máximo

`.pitch-wrap` ganha `max-width: 480px; margin: 0 auto;` — trava o campo num tamanho fixo e centralizado em telas largas, sem mexer no comportamento em celular (onde already cabe dentro da largura menor que 480px).

## Cores por lado

- **Lado A** — Gol Esquerdo (`camera_id` 1) e Arquibancada Esquerda (`camera_id` 3): azul `#2563eb`.
- **Lado B** — Gol Direito (`camera_id` 2) e Arquibancada Direita (`camera_id` 4): vermelho `#dc2626`.
- **Geral** (`camera_id` 5): paleta de juiz preto e amarelo — preenchimento `#111827`, borda `#facc15`.

Os estados já existentes (selecionado = anel amarelo, ocupado = cinza) continuam sobrepondo essas cores, sem mudança de comportamento — só a cor de base do marcador livre passa a variar por posição em vez de ser uniforme.

## Fora de escopo

Mudança de tamanho **mínimo** (não é o problema relatado — telas pequenas já funcionam bem hoje). Mudança de cor de qualquer outro elemento da UI fora do campo.

## Testes

Sem suite automatizada de UI (mesma limitação de sempre). Verificação: sintaxe JS válida (`node --check` no bloco `<script>` extraído) e inspeção estática confirmando que cada slot em `SLOTS` tem o campo `side` correto.
