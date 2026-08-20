# Runbook — Spike 2 execução (1 e 2 câmeras)

Pré-requisitos:
- Código já sincronizado e venv pronta na Pi (Task 6 do plano).
- Certificado mkcert do Spike 1 disponível na Pi (ex: `~/spike1/192.168.4.1.pem` e `~/spike1/192.168.4.1-key.pem` — ajustar caminho conforme o Spike 1 real).
- 2 celulares Android, ambos na rede do hotspot do Pi.
- Hotspot do Pi em modo aberto: `nmcli device wifi hotspot ifname wlan0 ssid ManagerReplay-Test`.
- `monitor.sh`/`monitor2.sh` já presentes no home da Pi (conforme checkpoint do `ContextoProjeto.md`).

Deploy do código (rodar na máquina dev, com acesso à rede do Pi):
```bash
rsync -av --exclude .venv --exclude __pycache__ /home/rocha/Projetos/ManagerReplay/spikes/spike2 rocha@ManagerReplay.local:~/spike2/
```

Setup da venv na Pi (uma vez só, via SSH):
```bash
sudo apt install -y libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev libswscale-dev libswresample-dev libavfilter-dev
cd ~/spike2
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Diretório de resultados na Pi:
```bash
mkdir -p ~/highlightbox-spike2-results
```

## Padrão de execução de uma rodada

Repita este bloco para cada uma das 4 combinações da matriz (ajustando `MODE`, `CAMERAS` e `ROUND_NAME`):

```bash
# na Pi, via SSH
cd ~/spike2
MODE=chunks        # ou webrtc
CAMERAS=1          # ou 2
ROUND_NAME="1cam_chunks_smoke"   # nomear conforme a rodada (ver tabela abaixo)

: > ~/highlightbox-monitor.csv
./monitor.sh &
MONITOR_PID=$!

.venv/bin/python spike2_server.py \
  --mode=$MODE --cameras=$CAMERAS \
  --cert ~/spike1/192.168.4.1.pem --key ~/spike1/192.168.4.1-key.pem &
SERVER_PID=$!

# nos celulares: abrir https://192.168.4.1:8443/?mode=$MODE&camera=1
# (e camera=2 no segundo celular, se CAMERAS=2)
# aceitar o certificado/perfil confiável e permitir a câmera

# aguardar a duração da rodada (2-3min pro smoke test, 15-20min pra rodada completa),
# então encerrar:
kill $SERVER_PID
kill $MONITOR_PID

cp ~/highlightbox-monitor.csv ~/highlightbox-spike2-results/${ROUND_NAME}.csv
vcgencmd get_throttled >> ~/highlightbox-spike2-results/${ROUND_NAME}.csv
```

Depois de cada rodada, verificar os arquivos gravados:
```bash
find ~/highlightbox-spike2 -name "*.webm" -exec ffprobe -v error {} \;
```
Sem saída de erro do `ffprobe` = arquivo não corrompido.

## Ordem das rodadas

1. `1cam_chunks` — smoke (2-3min) → se ok, full (15-20min)
2. `1cam_webrtc` — smoke → full
3. `2cam_chunks` — smoke → full
4. `2cam_webrtc` — smoke → full

Se uma rodada falhar o critério de sucesso (crash, reboot, throttling, ou arquivo corrompido), documentar na tabela abaixo e seguir para a próxima combinação — só interromper a sequência se o Pi precisar de reboot manual pra se recuperar.

## Tabela de resultados

| Rodada | Passou? | CPU médio/pico | RAM | Temp | Throttling? | Observações |
|---|---|---|---|---|---|---|
| 1cam_chunks_full | | | | | | |
| 1cam_webrtc_full | | | | | | |
| 2cam_chunks_full | | | | | | |
| 2cam_webrtc_full | | | | | | |

Preencher esta tabela conforme cada rodada completa é executada. O resultado final desta tabela é o insumo de decisão para o transporte de vídeo da Fase 03.
