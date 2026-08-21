# ManagerReplay

Sistema portátil de gravação de partidas esportivas (futebol, vôlei, etc.) que usa os celulares dos próprios jogadores como câmeras, sem depender de câmeras esportivas dedicadas ou de internet. O servidor roda num Raspberry Pi 3B, que cria a própria rede Wi-Fi (hotspot) e os celulares se conectam nela como câmeras — tudo pelo navegador, sem instalar nada.

Contexto completo do produto, decisões de arquitetura e riscos técnicos em [`ContextoProjeto.md`](ContextoProjeto.md).

## Telas

<table>
  <tr>
    <td align="center"><img src="imagem/Inicio.png" width="200" alt="Tela Início"><br>Início</td>
    <td align="center"><img src="imagem/Cameras.png" width="200" alt="Tela Câmeras"><br>Câmeras</td>
    <td align="center"><img src="imagem/Capture.png" width="200" alt="Tela de gravação"><br>Gravação</td>
  </tr>
  <tr>
    <td align="center"><img src="imagem/Gravando.png" width="200" alt="Tela Quem está gravando"><br>Quem está gravando</td>
    <td align="center"><img src="imagem/Files.png" width="200" alt="Tela Arquivos"><br>Arquivos</td>
    <td align="center"><img src="imagem/Monitor.png" width="200" alt="Tela Monitor"><br>Monitor</td>
  </tr>
</table>

## Como funciona

1. A Raspberry Pi liga e sobe sozinha — hotspot Wi-Fi aberto e o app já rodando, sem precisar de SSH nem tela.
2. Os celulares conectam nesse Wi-Fi e acessam `https://<ip-do-hotspot>:8443/` pelo navegador (dá pra "Adicionar à tela inicial" pra virar um ícone de app de verdade, com ícone próprio).
3. Na primeira vez, o celular baixa e instala o certificado de segurança direto pelo app (banner na tela inicial).
4. Quem vai gravar digita o nome e escolhe a câmera: **Câmera 1 é sempre a traseira**, **Câmera 2 é sempre a frontal** — o seletor de dispositivo só mostra as lentes daquele lado.
5. Antes de gravar, escolhe a qualidade (HD/FHD, 30/60fps) e aperta **● Iniciar gravação**. O vídeo é enviado em pedaços de 30s pro Pi (trocar de câmera no meio da gravação não reinicia a sessão — só troca a lente ao vivo).
6. Depois de 30s de gravação, o botão **⚡ Lance** libera — aperta pra marcar um momento importante (nome tipo "LanceEpico 003" + timestamp, com vibração e flash de confirmação).
7. **📹 Quem está gravando** mostra ao vivo quem está com a câmera ativa, em qual câmera, e se está enviando dados normalmente.
8. **📁 Arquivos** lista as gravações organizadas por dia, com download direto.
9. **📊 Monitor** mostra CPU/RAM/temperatura/armazenamento da Pi sob demanda (sem nada rodando em background).

## Stack

- **Backend**: Python (stdlib `http.server`, sem framework) — modo `webrtc` via `aiohttp`/`aiortc` existe no código mas não é usado pela UI atual (só `chunks` está exposto).
- **Frontend**: HTML/CSS/JS puro, servido direto pelo backend — sem build step, sem framework JS.
- **Rede**: HTTPS obrigatório (câmera do navegador exige contexto seguro), certificado gerado localmente com [mkcert](https://github.com/FiloSottile/mkcert). PWA instalável (manifest + ícones) pra virar um app de verdade na tela inicial.

## Estrutura do repositório

```
server/                  pacote Python do servidor (o nome da pasta importa — veja nota abaixo)
├── app.py               entrypoint CLI
├── chunks_receiver.py   servidor HTTPS (modo chunks, via stdlib http.server) — rotas da API
├── webrtc_receiver.py   servidor HTTPS (modo webrtc, via aiohttp/aiortc — não usado pela UI hoje)
├── storage.py           onde/como os vídeos são salvos (pastas por dia, nome por câmera+sessão+parte)
├── events.py            registro dos "lances" (events.jsonl)
├── sessions.py           quem está gravando agora (estado em memória, pra tela "Quem está gravando")
├── file_listing.py      listagem de diretório pro explorador de arquivos
├── monitor_status.py    leitura sob demanda de CPU/RAM/temperatura/disco da Pi
└── static/               HTML/CSS/JS servido pro navegador do celular
    ├── index.html         menu inicial + banner de instalação do certificado
    ├── cameras.html        nome do operador + escolha de câmera (1=traseira, 2=frontal)
    ├── capture.html         tela de gravação (vídeo, qualidade, lance, troca de câmera ao vivo)
    ├── gravando.html        quem está gravando agora, ao vivo
    ├── files.html           explorador de arquivos gravados
    └── monitor.html         saúde da Pi sob demanda
deploy/systemd/          unit files pro servidor subir sozinho no boot
tests/server/             testes automatizados (pytest)
docs/superpowers/         specs, planos e runbooks de decisões de design
```

> **Importante**: o pacote Python se chama `server` (é o que o código importa via `from server import ...`). Ao fazer deploy, a pasta no destino **precisa se chamar `server`** — renomear quebra o import.

## Rodando os testes

```bash
python3 -m venv .venv
.venv/bin/pip install -r server/requirements.txt -r server/requirements-dev.txt
.venv/bin/python -m pytest tests/server/ -v
```

## Deploy no Raspberry Pi

Layout esperado na Pi, tudo sob `~/managerreplay/`:

```
~/managerreplay/
├── server/        código + venv (.venv/)
├── data/
│   ├── recordings/       vídeos gravados, uma pasta por dia (YYYY-MM-DD/cameraN_<sessão>_parteN.webm)
│   └── events.jsonl      lances registrados
└── certs/         certificado HTTPS (leaf cert + key do mkcert)
```

1. **Sincronizar o código**:
   ```bash
   rsync -av --exclude .venv --exclude __pycache__ server/ rocha@<ip-da-pi>:~/managerreplay/server/
   ```
2. **Gerar o certificado HTTPS** (uma vez, ou quando o IP do hotspot mudar):
   ```bash
   mkcert -install
   mkdir -p ~/managerreplay/certs && cd ~/managerreplay/certs
   mkcert <ip-do-hotspot>   # ex: mkcert 10.42.0.1
   ```
3. **Subir o servidor** — via systemd (ver seção abaixo, recomendado) ou manualmente pra testar:
   ```bash
   cd ~/managerreplay/server
   .venv/bin/python app.py --mode=chunks --cameras=1 \
     --cert ~/managerreplay/certs/<ip>.pem --key ~/managerreplay/certs/<ip>-key.pem
   ```

`--storage-root` e `--events-file` já usam `~/managerreplay/data/...` por padrão — só precisam ser passados se quiser outro local.

## Hotspot Wi-Fi da Pi

Criado uma vez via `nmcli` (rede aberta, sem senha — evita um bug conhecido de kernel panic do chip Wi-Fi do Pi 3B em modo AP com WPA2, ver `ContextoProjeto.md` Risco 4):

```bash
sudo nmcli connection add type wifi ifname wlan0 con-name ManagerReplay-Hotspot autoconnect yes ssid ManagerReplay-Hotspot
sudo nmcli connection modify ManagerReplay-Hotspot 802-11-wireless.mode ap 802-11-wireless.band bg ipv4.method shared
sudo nmcli connection up ManagerReplay-Hotspot
```

`autoconnect yes` faz o hotspot subir sozinho a cada boot (testado com reboot real). Se a Pi já tiver um perfil de Wi-Fi doméstico salvo, remova-o (`nmcli connection delete <nome>`) — senão o `wlan0` pode preferir reconectar nele em vez de subir o hotspot.

## Autostart no boot (systemd) — jogo sem SSH

Pra usar num campo/quadra sem levar notebook: a Pi precisa subir o hotspot e o servidor sozinha ao ligar. O hotspot já sobe sozinho (seção acima). O servidor sobe via systemd:

```bash
sudo cp deploy/systemd/managerreplay-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now managerreplay-server
```

O arquivo `.service` já está pronto em [`deploy/systemd/`](deploy/systemd/) — ajuste o caminho do certificado dentro dele se o IP do hotspot for diferente de `10.42.0.1`. `Restart=always` garante que se ele cair, volta sozinho. Log fica no `journalctl -u managerreplay-server`.

**Desligando sem tela/teclado (puxando a energia direto)**: a tela de Monitor mede CPU/RAM/temperatura na hora (via `top`/`free`/`vcgencmd`), sob demanda, só quando alguém abre a tela e aperta "Atualizar" — não existe processo escrevendo continuamente no cartão SD, então não há nada pra corromper com uma queda de energia. As gravações de vídeo continuam no cartão SD normalmente; no pior caso, só o pedaço de ~30s que estava sendo gravado no exato momento de tirar a energia pode ficar incompleto — o resto da gravação (chunks anteriores, já com escrita concluída) fica intacto.

## Instalando o certificado nos celulares

Como o certificado é autoassinado (rede 100% offline, sem CA pública), cada celular precisa confiar no certificado raiz do mkcert uma vez. O app facilita isso: o menu inicial mostra um banner **"Primeira vez nesse celular?"** com um botão que baixa o `rootCA.pem` direto do Pi e o passo a passo de instalação (Android: Configurações → Segurança → Criptografia e credenciais → Instalar um certificado → Certificado de CA).

Esse link só funciona se o `rootCA.pem` do mkcert estiver copiado para `server/static/certs/rootCA.pem` na Pi (não vai para o Git — é específico de cada instalação):

```bash
mkdir -p ~/managerreplay/server/static/certs
cp "$(mkcert -CAROOT)/rootCA.pem" ~/managerreplay/server/static/certs/rootCA.pem
```

**Nunca copie `rootCA-key.pem` (a chave privada da CA) nem os arquivos `*-key.pem` de `~/managerreplay/certs/` pra dentro de `server/static/` — esses arquivos ficam expostos publicamente por HTTP, e a chave privada da CA compromete a segurança de qualquer aparelho que confiar no certificado.**

## Estado do projeto

O roadmap original (Fases 00–10) está em [`ContextoProjeto.md`](ContextoProjeto.md), seção 9. A validação de capacidade de hardware (Pi aguentando 2 câmeras simultâneas) foi pausada em favor de já estruturar o produto — ainda é uma pergunta em aberto se/quando o time decidir retomar. Fora do escopo por enquanto: SQLite (eventos ainda são JSON Lines), highlights automáticos (cortar 30s antes/depois de um lance), modo WebRTC na UI. Specs e planos de cada decisão de design ficam em [`docs/superpowers/`](docs/superpowers/).
