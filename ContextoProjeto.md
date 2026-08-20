# Contexto do Projeto — HighlightBox

> Documento de contexto para uso com assistentes de IA de desenvolvimento (ex: Claude Code, Cursor, etc). Cole este arquivo inteiro como contexto inicial ao começar a trabalhar no código do projeto.

## 1. O que é o projeto

HighlightBox é um sistema portátil de gravação de partidas esportivas (futebol, vôlei, etc.) que usa os celulares dos próprios jogadores como câmeras, sem depender de câmeras esportivas dedicadas ou de internet. Qualquer jogador com Android ou iPhone conecta o celular numa rede Wi-Fi local e vira temporariamente uma câmera do jogo.

O servidor central roda num **Raspberry Pi 3 Model B** (hardware já em posse do time, 1GB RAM, quad-core ARM Cortex-A53 1.2GHz, Wi-Fi 2.4GHz apenas, sem USB 3.0). Ele é responsável por: criar a rede Wi-Fi local, hospedar a aplicação web, gerar QR Codes para conectar câmeras, receber e gravar os streams de vídeo, registrar eventos/momentos do jogo, e gerar highlights.

**Não há inteligência artificial no MVP.** Os highlights são criados manualmente pelo administrador apertando botões (ex: "⚽ GOL") durante a partida.

## 2. Filosofia do MVP

- Deve funcionar **100% offline** — internet é opcional, não faz parte da v1.
- Não otimizar prematuramente para hardware melhor: o hardware disponível é um Pi 3B, e o objetivo inicial é descobrir quantas câmeras esse hardware específico aguenta de forma confiável, não assumir escala.
- O jogador (câmera) não deve precisar entender nada de rede/IP/configuração — fluxo alvo: conectar no Wi-Fi → escanear QR Code → permitir câmera → pronto.
- Não transcodificar vídeo no Raspberry sempre que possível (o celular já manda H.264 codificado; o Pi só grava/enfileira, evitando trabalho pesado de CPU).
- SQLite guarda só metadados (jogos, câmeras, eventos, highlights) — vídeo nunca vai para dentro do banco, fica no filesystem/armazenamento externo.

## 3. Decisão de plataforma: MVP no Raspberry Pi, produto final possivelmente em app Android

Avaliamos duas arquiteturas de "hub" (quem hospeda a rede Wi-Fi + servidor): Raspberry Pi 3B (plano original) vs. um celular Android atuando como hotspot + servidor.

**Decisão**: começar o MVP no Raspberry Pi 3B, porque é o hardware já disponível, evita competir com as políticas agressivas de economia de bateria/background do Android enquanto ainda estamos validando se o conceito central funciona, e a lógica de negócio (Kotlin/Ktor) é majoritariamente reaproveitável depois caso o produto final migre para um app Android.

**Para referência futura**, os motivos que tornam um app Android mais viável como *produto* comercial (não como MVP técnico) são: zero custo de hardware/BOM, sem necessidade de homologação ANATEL (custo estimado de R$10.000–R$25.000+ para um aparelho físico com Wi-Fi + bateria no Brasil), e resolve organicamente a entrega dos vídeos aos jogadores depois do jogo (o celular-hub pode usar seus próprios dados móveis como backhaul para subir highlights à nuvem, algo que o Pi isolado sem internet não faz nativamente). Importante: **iPhone nunca pode ser o hub** — a Apple não expõe API para criar hotspot programável nem para manter um servidor de rede persistente em segundo plano; iPhone só pode ser câmera-cliente, em qualquer uma das duas arquiteturas.

## 4. Riscos técnicos identificados (validar cedo, antes de investir em funcionalidades)

### Risco 1 — HTTPS / `getUserMedia()` em contexto seguro
Navegadores (Chrome e Safari) só liberam acesso à câmera (`getUserMedia()`) em contexto seguro — não existe mais exceção para `http://` em IP privado (`192.168.4.1`) nem para hostname `.local` via mDNS. É necessário HTTPS com certificado confiável. Como a rede é totalmente offline (sem CA pública tipo Let's Encrypt), o caminho é gerar uma CA local com **mkcert** e instalar o certificado raiz como perfil confiável em cada iPhone (Safari é notoriamente rígido com certificados autoassinados). Isso conflita com a promessa de "zero configuração" para o jogador — é o maior risco de UX/técnico do projeto.

**Status**: em validação — kit de teste (`Spike 1`) já foi entregue com servidor Python (HTTP + HTTPS via mkcert) e página de diagnóstico de câmera.

### Risco 2 — Capacidade do Pi 3B como receptor de vídeo
Não há relato documentado de um Pi 3B atuando como receptor/SFU de múltiplos streams WebRTC 1080p simultâneos — a maioria dos projetos usa o Pi como emissor de uma única câmera, não como servidor recebendo várias. É uma incógnita real, não só um parâmetro de escala.

**Alternativa a considerar** se WebRTC completo (que exige implementar/embutir um SFU) se provar inviável no Pi 3B: usar `MediaRecorder API` no navegador com upload de vídeo em chunks (5–10s) via HTTP `POST`/`fetch` comum, em vez de WebRTC. Isso elimina ICE/DTLS-SRTP/SFU inteiramente — o Pi só recebe e grava blobs — trocando preview ao vivo por alguns segundos de latência. Muito mais amigável ao hardware do Pi 3B.

**Status**: a validar (`Spike 2` — Pi recebendo 1 stream real por 15–20 min, medindo CPU/RAM/temperatura/energia).

### Risco 3 — Banda de Wi-Fi do Pi 3B
O rádio Wi-Fi do Pi 3B é 2.4GHz, 802.11n apenas (BCM43438) — throughput real de TCP tipicamente 20–30 Mbps, compartilhado entre todas as câmeras conectadas. Um stream H.264 1080p30 de boa qualidade consome ~4–8 Mbps. É plausível que 2 câmeras já saturem o rádio antes mesmo de chegar a CPU como limite.

### Risco 4 — Bug conhecido no chip Wi-Fi do Pi 3B/3B+ em modo Access Point
Existe um bug documentado e sem correção no kernel oficial do Raspberry Pi (`raspberrypi/linux#5380`, `#7247`): o chip BCM43438 pode causar **kernel panic** ao rodar em modo Access Point via NetworkManager com senha WPA2 ativa, principalmente quando um cliente tenta conectar. Rede aberta (sem senha) tende a ser mais estável nesse chip. Recomendação: testar hotspot sem senha primeiro, só depois ativar WPA2; se travar, usar o método clássico `hostapd` + `dnsmasq` como alternativa.

### Risco 5 — Comportamento do celular-câmera em segundo plano
Navegadores móveis (especialmente Safari) suspendem streams de câmera/WebRTC quando a aba vai para segundo plano ou a tela bloqueia. Isso é esperado e vira uma limitação documentada do MVP, não um bug a "corrigir" agora (endereçar bloqueio de tela fica para V3 do roadmap).

## 5. Stack técnica planejada

- **Backend**: Kotlin + Ktor (JVM) rodando como serviço no Raspberry Pi OS. Escolhido por já haver experiência prévia com Java/Kotlin e por ter overhead menor que Spring Boot num Pi 3B com recursos limitados.
- **Banco de dados**: SQLite — só metadados (`users`, `games`, `cameras`, `camera_sessions`, `events`, `highlights`, `settings`). Vídeo nunca entra no banco.
- **Frontend**: HTML/CSS/JS simples inicialmente (pode evoluir pra framework depois). Roda no navegador do celular do jogador e do administrador — sem apps nativos no MVP.
- **Transmissão de vídeo**: WebRTC como plano principal (celular já manda H.264 codificado, evita transcodificação no Pi); `MediaRecorder` + upload em chunks como plano B mais simples de implementar no hardware do Pi 3B (ver Risco 2).
- **Rede**: Pi conectado à internet de casa via **cabo Ethernet** (`eth0`); Wi-Fi embutido (`wlan0`) em modo Access Point via `nmcli device wifi hotspot`, broadcasting a rede local que os celulares-câmera usam (rede isolada, sem depender de internet para o funcionamento central).
- **Armazenamento**: separar sistema (microSD, Raspberry Pi OS + app) de vídeo (idealmente storage USB — pendrive no primeiro teste, SSD USB depois). USB 2.0 no Pi 3B — sem USB 3.0.

### Estrutura de arquivos sugerida

```
/opt/highlightbox/
├── app/
├── data/
│   └── highlightbox.db
├── recordings/
│   └── games/
│       └── {game-id}/
│           ├── camera-{camera-id}/
│           │   ├── segments/
│           │   └── metadata/
│           └── highlights/
├── config/
└── logs/
```

### Esquema do banco (conceitual)

```
users(id, username, password_hash, role, created_at)
games(id, name, sport, status, started_at, ended_at, created_at)
cameras(id, game_id, name, device_name, platform, position, status, created_at)
camera_sessions(id, camera_id, connected_at, disconnected_at)
events(id, game_id, type, timestamp, created_at)
highlights(id, event_id, start_time, end_time, status, created_at)
```

### API conceitual

```
POST   /api/auth/login
POST   /api/games
GET    /api/games/current
POST   /api/games/{id}/start
POST   /api/games/{id}/stop
POST   /api/games/{id}/cameras/token
GET    /api/games/{id}/cameras
DELETE /api/cameras/{id}
POST   /api/games/{id}/events
GET    /api/games/{id}/events
GET    /api/games/{id}/highlights
GET    /api/highlights/{id}
```

A API de vídeo/WebRTC deve ser tratada separada da API administrativa (componentes diferentes, possivelmente até processos/linguagens diferentes — ver Risco 2).

## 6. Perfis de usuário

- **Administrador**: cria/inicia/encerra partida, adiciona/remove câmeras, gera QR Code, registra eventos, gerencia highlights e armazenamento.
- **Câmera**: um celular conectado via QR Code com token temporário (identifica a partida, uso único/controlado, sem privilégio administrativo). Só conecta, transmite, informa status.
- **Espectador**: fora do MVP ou simplificado — acesso a highlights depois do jogo.

## 7. Segmentação de gravação e highlights

Gravação em segmentos de ~10s. Um highlight é o evento + 30s antes + 30s depois (registrado como `event { game_id, timestamp }` primeiro; o highlight é montado depois, para reduzir carga em tempo real no Pi 3B).

**Requisito técnico a não esquecer**: os segmentos de gravação devem estar alinhados a keyframes (estilo HLS, cada segmento começando num I-frame), senão remontar um highlight que cruza limites de segmento exige recodificar em vez de só concatenar arquivos.

Tipos de evento (futebol): `GOAL, CARD, SAVE, PLAY, OTHER`. Vôlei: `POINT, BLOCK, ATTACK, RALLY, OTHER`. Arquitetura deve permitir adicionar esportes novos.

## 8. Explicitamente fora do escopo do MVP

IA, reconhecimento de jogadores/bola, detecção automática de eventos, cloud, login pela internet, transmissão para YouTube, processamento remoto, edição avançada, apps nativos iOS/Android, pagamento, assinatura.

## 9. Ordem de desenvolvimento

```
Fase 00 (adicionada após os spikes de risco)
  Spike 1: validar getUserMedia()/HTTPS local (mkcert) no iPhone
  Spike 2: Pi 3B recebendo e gravando 1 stream de vídeo real por 15-20min,
           medindo CPU/RAM/temperatura/energia

Fase 01: Wi-Fi Access Point + servidor web
Fase 02: página web + acesso à câmera (Android/iPhone)
Fase 03: WebRTC celular → Raspberry
Fase 04: gravação em storage USB
Fase 05: SQLite (jogos, câmeras, eventos)
Fase 06: admin + QR Code + gerenciamento de câmeras
Fase 07: botão MOMENTO + registro de evento
Fase 08: highlight (30s antes + momento + 30s depois)
Fase 09: testes com 2 celulares
Fase 10: testes com 3+ celulares
```

Critério de sucesso do MVP: Raspberry cria Wi-Fi → Android + iPhone conectam → QR Code identifica câmeras → câmeras transmitem → Raspberry grava → Admin aperta botão → evento é registrado → highlight é gerado → Admin reproduz. Tudo sem internet e sem IA.

## 10. Estado atual do hardware / setup (checkpoint)

- Raspberry Pi 3 Model B, **Raspberry Pi OS Lite 64-bit** (Debian 13 "Trixie", kernel 6.18).
- Hostname: `ManagerReplay` (acessível via `ManagerReplay.local`), usuário `rocha`.
- SSH configurado e funcionando (`ssh rocha@ManagerReplay.local`).
- Conectividade: Ethernet (`eth0`) para internet de casa; Wi-Fi (`wlan0`) para modo Access Point via `nmcli device wifi hotspot` (testar primeiro sem senha por causa do Risco 4 acima, depois com WPA2).
- `gpu_mem=16` configurado em `/boot/firmware/config.txt` para liberar RAM (headless, sem saída de vídeo local).
- Bluetooth desativado (`sudo systemctl disable --now bluetooth`).
- Script de monitoramento (`monitor.sh` / `monitor2.sh`) rodando em CPU/RAM/temperatura/clock/energia (detecta subvoltagem via `vcgencmd get_throttled`), logando em CSV (`~/highlightbox-monitor.csv`) para revisão pós-teste.
- Baseline observado (idle, pós fresh install): ~6% CPU, ~175MB RAM usada de ~905MB disponível, 38°C, sem subvoltagem.

## 11. Próximos passos imediatos

1. Validar Spike 1 (câmera via HTTPS local) com iPhone real.
2. Validar hotspot Wi-Fi do Pi (sem senha primeiro, depois com WPA2 — atenção ao Risco 4).
3. Validar Spike 2 (Pi recebendo vídeo real de 1 câmera por 15-20min, monitorando com o script).
4. Só depois desses três resultados, prosseguir para Fase 01 em diante do plano de desenvolvimento.