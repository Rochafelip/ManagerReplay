# Redesenho da UI: tela de câmera e explorador de arquivos

Decidido em sessão de brainstorm visual (navegador). Três decisões:

## 1. Navegação geral: mantém páginas separadas

Sem abas fixas nem painel único — mantém o fluxo atual (`index.html` menu → `cameras.html` → `capture.html`, `/files/` separado), só melhora a aparência de cada tela.

## 2. Tela de câmera (`capture.html`): controles sobre o vídeo

- Indicador de gravação (● gravando · MM:SS) sobreposto no canto superior esquerdo do vídeo.
- Seletor de câmera e botão de Lance flutuam sobre a parte inferior do vídeo (estilo câmera nativa/stories): seletor à esquerda (mostra label curto, ex: "📷 Traseira ▾"), botão de Lance em pílula à direita.
- Abaixo do vídeo, um link discreto "⚙ detalhes técnicos ▾" que expande (accordion) pra mostrar o que hoje fica sempre visível: status de upload (chunks/bytes), caminho de armazenamento na Pi. Fechado por padrão.
- Feedback do lance registrado aparece como toast/mensagem temporária, não permanente.

## 3. Explorador de arquivos (`/files/`): lista customizada

Troca a listagem crua do `http.server`/`aiohttp` por uma página HTML própria:

- Nome do arquivo/pasta grande e em negrito; tamanho + data numa linha menor abaixo (arquivos) ou "pasta" (diretórios).
- Pastas com ícone 📁 e seta `›` pra entrar; arquivos com botão de baixar ⬇ explícito.
- Breadcrumb no topo mostrando o caminho atual, clicável pra voltar a níveis anteriores.
- Precisa de uma rota JSON auxiliar (`/files-list?path=...`) que devolve os itens do diretório (nome, é-pasta, tamanho, mtime) — a página estática consome essa rota via `fetch`; o download em si continua usando a rota `/files/...` já existente (serve o arquivo bruto).

## Fora do escopo

- Abas de navegação / painel único (rejeitados nesta rodada).
- Preview de vídeo inline no explorador de arquivos.
- Paginação/busca na listagem de arquivos (poucos arquivos por enquanto).
