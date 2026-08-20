# Tela "quem vai gravar" + remoção do Modo WebRTC (UI)

Decidido em sessão de brainstorm visual (navegador). Duas decisões:

## 1. Remove o Modo WebRTC da UI, por enquanto

- `cameras.html` deixa de listar "Modo chunks" / "Modo WebRTC" como duas seções — só existe um fluxo, o modo chunks (já é o único usado na prática).
- `client.js` perde a função `startWebrtcMode` e o branch condicional em `start()`, já que nenhum link da UI gera mais `mode=webrtc`. Fica só o caminho chunks.
- Fora do escopo: o backend Python (`server/webrtc_receiver.py`, `--mode webrtc` em `app.py`) não é tocado — é infraestrutura de spike separada da tela, não exposta a quem grava. Pode voltar a ser ligado à UI depois, se o modo WebRTC for retomado.

## 2. Nova `cameras.html`: passo único, nome primeiro

Fluxo escolhido (opção C do brainstorm) — substitui a tela atual de "escolher câmera":

1. A tela abre com um único campo: "Qual é o seu nome?". Enquanto vazio, os botões de câmera ficam ocultos/desabilitados.
2. Ao preencher o nome, aparecem dois botões: "📹 Câmera 1" e "📹 Câmera 2".
3. Clicar num botão navega pra `capture.html?mode=chunks&camera=N&name=<nome-codificado>`.
4. O nome é salvo em `localStorage` (`managerreplay_operator_name`) e pré-preenchido da próxima vez que a tela abrir no mesmo celular — sem persistência no servidor/SQLite, é só conveniência local.

Em `capture.html`, o nome de quem está gravando aparece como um selo discreto perto do indicador de gravação (ex: abaixo do "● gravando", "🎥 Carlos"). Sem mudança de backend: se `name` não vier na URL, o selo simplesmente não aparece.

## 3. Paleta: azul → verde esportivo

O azul (`#2563eb` / `#1d4ed8`) usado como cor de ação primária em `index.html`, `cameras.html` e `files.html` vira verde (`#16a34a` ativo / `#15803d` pressed). Mantém o vermelho do selo "gravando" (semântico) e o âmbar do botão "Lance" (contraste/urgência) como estão.

## Fora do escopo

- Qualquer mudança no backend (`server/*.py`), exceto nenhuma — só front-end estático.
- Reativar o Modo WebRTC na UI.
- Lista/agenda de operadores cadastrados — é só um campo de nome livre, sem cadastro prévio.
