# ManagerReplay

Sistema portátil de gravação de partidas esportivas (futebol, vôlei, etc.) que usa os celulares dos próprios jogadores como câmeras, sem depender de câmeras esportivas dedicadas ou de internet. O servidor roda num Raspberry Pi 3B, que cria a própria rede Wi-Fi (hotspot) e os celulares se conectam nela como câmeras.

Contexto completo do produto, decisões de arquitetura e riscos técnicos em [`ContextoProjeto.md`](ContextoProjeto.md).

## Como funciona

1. O Raspberry Pi cria um hotspot Wi-Fi aberto.
2. Os celulares conectam nesse Wi-Fi e acessam a página do app pelo navegador (sem instalar nada — dá pra "Adicionar à tela inicial" pra virar um ícone de app).
3. Cada celular grava vídeo da câmera (frontal ou traseira, HD/FHD, 30/60fps) e envia em pedaços de 30s pro Pi.
4. O operador aperta o botão **⚡ Lance** pra marcar um momento importante da partida (nome + timestamp).
5. Os vídeos gravados ficam disponíveis pra download na tela **📁 Arquivos** do app.

## Stack

- **Backend**: Python (stdlib `http.server` + `aiohttp`/`aiortc` para o modo WebRTC), sem framework.
- **Frontend**: HTML/CSS/JS puro, servido direto pelo backend — sem build step.
- **Rede**: HTTPS obrigatório (câmera do navegador exige contexto seguro), certificado gerado localmente com [mkcert](https://github.com/FiloSottile/mkcert).

## Estrutura do repositório

```
server/                  pacote Python do servidor (o nome da pasta importa — veja nota abaixo)
├── app.py               entrypoint CLI
├── chunks_receiver.py   servidor HTTPS (modo chunks, via stdlib http.server)
├── webrtc_receiver.py   servidor HTTPS (modo webrtc, via aiohttp/aiortc)
├── storage.py           onde/como os vídeos são salvos em disco
├── events.py            registro dos "lances" (events.jsonl)
├── file_listing.py      listagem de diretório pro explorador de arquivos
└── static/               HTML/CSS/JS servido pro navegador do celular
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
│   ├── recordings/       vídeos gravados (recordings/camera-N/...)
│   └── events.jsonl      lances registrados
├── certs/         certificado HTTPS (leaf cert + key do mkcert)
└── monitor/        script de monitoramento de CPU/RAM/temperatura da Pi
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
3. **Subir o servidor**:
   ```bash
   cd ~/managerreplay/server
   nohup .venv/bin/python app.py --mode=chunks --cameras=1 \
     --cert ~/managerreplay/certs/<ip>.pem --key ~/managerreplay/certs/<ip>-key.pem \
     > ~/managerreplay/monitor/server.log 2>&1 &
   ```

`--storage-root` e `--events-file` já usam `~/managerreplay/data/...` por padrão — só precisam ser passados se quiser outro local.

## Autostart no boot (systemd) — jogo sem SSH

Pra usar num campo/quadra sem levar notebook: a Pi precisa subir o hotspot, o servidor e o monitor sozinha ao ligar. O hotspot Wi-Fi já sobe sozinho por conta do NetworkManager (`nmcli connection modify <ssid> autoconnect yes`, feito uma vez na configuração inicial). Servidor e monitor sobem via systemd:

```bash
sudo cp deploy/systemd/managerreplay-server.service deploy/systemd/managerreplay-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now managerreplay-server managerreplay-monitor
```

Os arquivos `.service` já estão prontos em [`deploy/systemd/`](deploy/systemd/) — ajuste o caminho do certificado dentro de `managerreplay-server.service` se o IP do hotspot for diferente de `10.42.0.1`. `Restart=always` garante que se algum dos dois cair, ele volta sozinho.

**Desligando sem tela/teclado (puxando a energia direto)**: o `monitor.csv` é escrito no `/dev/shm` (RAM, tmpfs) por padrão — não fica no cartão SD, então puxar a energia nunca corrompe esse arquivo. As gravações de vídeo continuam no cartão SD normalmente; no pior caso, só o pedaço de ~30s que estava sendo gravado no exato momento de tirar a energia pode ficar incompleto — o resto da gravação (chunks anteriores, já com escrita concluída) fica intacto.

## Instalando o certificado nos celulares

Como o certificado é autoassinado (rede 100% offline, sem CA pública), cada celular precisa confiar no certificado raiz do mkcert uma vez. O app facilita isso: o menu inicial tem um link **"📜 Instalar certificado"** que baixa o `rootCA.pem` direto do Pi — depois é só instalar como certificado de CA confiável nas configurações do Android (ou perfil confiável no iPhone).

Esse link só funciona se o `rootCA.pem` do mkcert estiver copiado para `server/static/certs/rootCA.pem` na Pi (não vai para o Git — é específico de cada instalação):

```bash
mkdir -p ~/managerreplay/server/static/certs
cp "$(mkcert -CAROOT)/rootCA.pem" ~/managerreplay/server/static/certs/rootCA.pem
```

**Nunca copie `rootCA-key.pem` (a chave privada da CA) nem os arquivos `*-key.pem` de `~/managerreplay/certs/` pra dentro de `server/static/` — esses arquivos ficam expostos publicamente por HTTP, e a chave privada da CA compromete a segurança de qualquer aparelho que confiar no certificado.**

## Estado do projeto

O roadmap original (Fases 00–10) está em [`ContextoProjeto.md`](ContextoProjeto.md), seção 9. A validação de capacidade de hardware (Pi aguentando 2 câmeras simultâneas) foi pausada em favor de já estruturar o produto — ainda é uma pergunta em aberto se/quando o time decidir retomar. Specs e planos de cada decisão de design ficam em [`docs/superpowers/`](docs/superpowers/).
