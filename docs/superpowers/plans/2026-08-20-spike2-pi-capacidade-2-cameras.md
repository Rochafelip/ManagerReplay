# Spike 2 — Capacidade de captura de vídeo do Pi 3B (1 e 2 câmeras) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a disposable Python test harness that lets the Raspberry Pi 3B receive and record video from 1 or 2 Android phones over its own open hotspot, using either MediaRecorder+HTTP-chunks or WebRTC, so we can run the 4-round test matrix from the design doc and decide the video transport for Fase 03.

**Architecture:** A single CLI entrypoint (`spike2_server.py`) dispatches to one of two receiver modules — `chunks_receiver.py` (stdlib `http.server`, threaded, HTTPS via mkcert) or `webrtc_receiver.py` (`aiohttp` + `aiortc`, HTTPS via mkcert) — both writing recorded video under a shared `storage.py` path-building module. A static HTML/JS client served by whichever receiver is active captures 720p video from `getUserMedia` and sends it via the mode-appropriate path. Physical test execution (smoke test + 15-20min full run per combination) is a manual runbook using the Pi's existing `monitor.sh`.

**Tech Stack:** Python 3 (stdlib `http.server`, `aiohttp`, `aiortc`), pytest, vanilla HTML/JS (`getUserMedia`, `MediaRecorder`, `RTCPeerConnection`), mkcert-generated TLS cert/key (reused from Spike 1).

---

## Scope note

This plan implements the spike 2 test harness — the code and the manual runbook — per `docs/superpowers/specs/2026-08-20-spike2-pi-capacidade-2-cameras-design.md`. It does **not** implement production code (Fase 03+), does not touch SQLite, and does not implement a real SFU.

## File Structure

- `spikes/spike2/storage.py` — pure functions for building per-camera storage paths and writing chunk files. Fully unit-testable, no network/hardware dependency.
- `spikes/spike2/chunks_receiver.py` — HTTPS `http.server`-based receiver for MediaRecorder+chunks mode. Also serves the static client.
- `spikes/spike2/webrtc_receiver.py` — HTTPS `aiohttp`+`aiortc`-based receiver for WebRTC mode. Also serves the static client.
- `spikes/spike2/spike2_server.py` — CLI entrypoint, parses `--mode`, `--cameras`, `--cert`, `--key`, dispatches to the right receiver.
- `spikes/spike2/static/index.html` — client page (video preview + status).
- `spikes/spike2/static/client.js` — client capture logic for both modes, selected by URL query params.
- `spikes/spike2/requirements.txt` — `aiohttp`, `aiortc`.
- `spikes/spike2/requirements-dev.txt` — `pytest`.
- `tests/spikes/spike2/test_storage.py` — unit tests for `storage.py`.
- `tests/spikes/spike2/test_chunks_receiver.py` — integration test spinning up the real chunks HTTPS server on an ephemeral port and posting fake chunk bytes to it.
- `docs/superpowers/runbooks/2026-08-20-spike2-execution.md` — manual runbook for running the 4-round test matrix on the physical Pi, plus the results table template.

---

### Task 1: Storage module (path building + chunk writing)

**Files:**
- Create: `spikes/spike2/storage.py`
- Create: `spikes/spike2/__init__.py` (empty)
- Test: `tests/spikes/spike2/test_storage.py`
- Create: `tests/spikes/spike2/__init__.py` (empty)
- Create: `tests/spikes/__init__.py` (empty)
- Create: `tests/__init__.py` (empty)

- [ ] **Step 1: Write the failing tests**

```python
# tests/spikes/spike2/test_storage.py
from pathlib import Path

from spikes.spike2.storage import build_camera_dir, save_chunk


def test_build_camera_dir_creates_nested_path(tmp_path: Path):
    result = build_camera_dir(tmp_path, mode="chunks", n_cameras=2, camera_id=1)

    assert result == tmp_path / "chunks" / "2" / "camera-1"
    assert result.is_dir()


def test_build_camera_dir_is_idempotent(tmp_path: Path):
    first = build_camera_dir(tmp_path, mode="webrtc", n_cameras=1, camera_id=1)
    second = build_camera_dir(tmp_path, mode="webrtc", n_cameras=1, camera_id=1)

    assert first == second
    assert first.is_dir()


def test_save_chunk_writes_file_with_zero_padded_sequence(tmp_path: Path):
    path = save_chunk(tmp_path, sequence_number=3, data=b"fake-video-bytes")

    assert path == tmp_path / "chunk-0003.webm"
    assert path.read_bytes() == b"fake-video-bytes"


def test_save_chunk_handles_sequence_above_9999(tmp_path: Path):
    path = save_chunk(tmp_path, sequence_number=12345, data=b"x")

    assert path == tmp_path / "chunk-12345.webm"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/rocha/Projetos/ManagerReplay && python3 -m pytest tests/spikes/spike2/test_storage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spikes'` (or `spikes.spike2.storage`)

- [ ] **Step 3: Write minimal implementation**

```python
# spikes/spike2/storage.py
from pathlib import Path


def build_camera_dir(storage_root: Path, mode: str, n_cameras: int, camera_id: int) -> Path:
    camera_dir = storage_root / mode / str(n_cameras) / f"camera-{camera_id}"
    camera_dir.mkdir(parents=True, exist_ok=True)
    return camera_dir


def save_chunk(camera_dir: Path, sequence_number: int, data: bytes) -> Path:
    chunk_path = camera_dir / f"chunk-{sequence_number:04d}.webm"
    chunk_path.write_bytes(data)
    return chunk_path
```

```python
# spikes/spike2/__init__.py
```

```python
# tests/spikes/spike2/__init__.py
```

```python
# tests/spikes/__init__.py
```

```python
# tests/__init__.py
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/rocha/Projetos/ManagerReplay && python3 -m pytest tests/spikes/spike2/test_storage.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add spikes/spike2/storage.py spikes/spike2/__init__.py tests/spikes/spike2/test_storage.py tests/spikes/spike2/__init__.py tests/spikes/__init__.py tests/__init__.py
git commit -m "feat(spike2): add storage path/chunk-writing module"
```

---

### Task 2: Chunks receiver (HTTPS, MediaRecorder+chunks mode)

**Files:**
- Create: `spikes/spike2/chunks_receiver.py`
- Test: `tests/spikes/spike2/test_chunks_receiver.py`

- [ ] **Step 1: Write the failing test**

This test spins up the real HTTPS server on an ephemeral port with a self-signed cert generated on the fly (so the test doesn't depend on mkcert being installed), posts a fake chunk, and checks it landed on disk.

```python
# tests/spikes/spike2/test_chunks_receiver.py
import http.client
import ssl
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from spikes.spike2 import chunks_receiver


@pytest.fixture
def self_signed_cert(tmp_path: Path):
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", str(key_path), "-out", str(cert_path),
            "-days", "1", "-nodes", "-subj", "/CN=localhost",
        ],
        check=True,
        capture_output=True,
    )
    return cert_path, key_path


def test_chunks_receiver_writes_posted_chunk_to_disk(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    storage_root = tmp_path / "storage"
    static_dir = tmp_path / "static"
    static_dir.mkdir()

    server = chunks_receiver.build_server(
        storage_root=storage_root,
        n_cameras=2,
        static_dir=static_dir,
        cert_path=cert_path,
        key_path=key_path,
        host="127.0.0.1",
        port=0,
    )
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)

    try:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        conn = http.client.HTTPSConnection("127.0.0.1", port, context=ssl_context)
        conn.request("POST", "/upload?camera=1&seq=3", body=b"fake-video-bytes")
        response = conn.getresponse()
        assert response.status == 204
    finally:
        server.shutdown()
        thread.join(timeout=2)

    written = storage_root / "chunks" / "2" / "camera-1" / "chunk-0003.webm"
    assert written.read_bytes() == b"fake-video-bytes"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/rocha/Projetos/ManagerReplay && python3 -m pytest tests/spikes/spike2/test_chunks_receiver.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spikes.spike2.chunks_receiver'` (or `AttributeError: module has no attribute 'build_server'`)

- [ ] **Step 3: Write minimal implementation**

```python
# spikes/spike2/chunks_receiver.py
import ssl
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from spikes.spike2.storage import build_camera_dir, save_chunk


class ChunksUploadHandler(SimpleHTTPRequestHandler):
    storage_root: Path = None
    n_cameras: int = 1

    def do_POST(self):
        if not self.path.startswith("/upload"):
            self.send_response(404)
            self.end_headers()
            return

        query = parse_qs(urlparse(self.path).query)
        try:
            camera_id = int(query["camera"][0])
            sequence_number = int(query["seq"][0])
        except (KeyError, ValueError, IndexError):
            self.send_response(400)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length)

        camera_dir = build_camera_dir(self.storage_root, "chunks", self.n_cameras, camera_id)
        save_chunk(camera_dir, sequence_number, data)

        self.send_response(204)
        self.end_headers()

    def log_message(self, format, *args):
        pass


def build_server(
    storage_root: Path,
    n_cameras: int,
    static_dir: Path,
    cert_path: Path,
    key_path: Path,
    host: str = "0.0.0.0",
    port: int = 8443,
) -> ThreadingHTTPServer:
    ChunksUploadHandler.storage_root = storage_root
    ChunksUploadHandler.n_cameras = n_cameras
    handler = partial(ChunksUploadHandler, directory=str(static_dir))

    server = ThreadingHTTPServer((host, port), handler)
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    server.socket = ssl_context.wrap_socket(server.socket, server_side=True)
    return server


def run(
    storage_root: Path,
    n_cameras: int,
    static_dir: Path,
    cert_path: Path,
    key_path: Path,
    host: str = "0.0.0.0",
    port: int = 8443,
):
    storage_root.mkdir(parents=True, exist_ok=True)
    server = build_server(storage_root, n_cameras, static_dir, cert_path, key_path, host, port)
    print(f"[chunks] listening on https://{host}:{port}, storage={storage_root}")
    server.serve_forever()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/rocha/Projetos/ManagerReplay && python3 -m pytest tests/spikes/spike2/test_chunks_receiver.py -v`
Expected: 1 passed

Note: this test needs `openssl` on PATH (already standard on Raspberry Pi OS and most dev machines) — it does not require mkcert.

- [ ] **Step 5: Commit**

```bash
git add spikes/spike2/chunks_receiver.py tests/spikes/spike2/test_chunks_receiver.py
git commit -m "feat(spike2): add HTTPS chunks receiver for MediaRecorder mode"
```

---

### Task 3: WebRTC receiver (aiortc/aiohttp)

There is no real camera or browser in CI/dev, so `aiortc`'s track handling cannot be meaningfully unit-tested without a live peer. This module is verified manually against a real phone in Task 7's runbook. Keep it thin and reuse `storage.py`, which is already tested.

**Files:**
- Create: `spikes/spike2/webrtc_receiver.py`

- [ ] **Step 1: Write the implementation**

```python
# spikes/spike2/webrtc_receiver.py
import ssl
from pathlib import Path

from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRecorder

from spikes.spike2.storage import build_camera_dir

_active_connections: set[RTCPeerConnection] = set()


async def _handle_offer(request: web.Request) -> web.Response:
    camera_id = int(request.match_info["camera_id"])
    n_cameras: int = request.app["n_cameras"]
    storage_root: Path = request.app["storage_root"]

    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    _active_connections.add(pc)

    camera_dir = build_camera_dir(storage_root, "webrtc", n_cameras, camera_id)
    recorder = MediaRecorder(str(camera_dir / "recording.webm"))

    @pc.on("track")
    def on_track(track):
        if track.kind == "video":
            recorder.addTrack(track)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        if pc.connectionState in ("failed", "closed"):
            await recorder.stop()
            await pc.close()
            _active_connections.discard(pc)

    await pc.setRemoteDescription(offer)
    await recorder.start()

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.json_response({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type})


async def _on_shutdown(app: web.Application):
    for pc in list(_active_connections):
        await pc.close()
    _active_connections.clear()


def run(
    storage_root: Path,
    n_cameras: int,
    static_dir: Path,
    cert_path: Path,
    key_path: Path,
    host: str = "0.0.0.0",
    port: int = 8443,
):
    storage_root.mkdir(parents=True, exist_ok=True)

    app = web.Application()
    app["storage_root"] = storage_root
    app["n_cameras"] = n_cameras
    app.router.add_post("/offer/{camera_id}", _handle_offer)
    app.router.add_static("/", path=str(static_dir), name="static")
    app.on_shutdown.append(_on_shutdown)

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))

    print(f"[webrtc] listening on https://{host}:{port}, storage={storage_root}")
    web.run_app(app, host=host, port=port, ssl_context=ssl_context)
```

- [ ] **Step 2: Sanity-check the module imports cleanly**

Run: `cd /home/rocha/Projetos/ManagerReplay && python3 -c "from spikes.spike2 import webrtc_receiver"`
Expected: no output, exit code 0 (only proves imports resolve — `aiortc`/`aiohttp` must already be installed per Task 6)

- [ ] **Step 3: Commit**

```bash
git add spikes/spike2/webrtc_receiver.py
git commit -m "feat(spike2): add HTTPS WebRTC receiver using aiortc"
```

---

### Task 4: CLI entrypoint

**Files:**
- Create: `spikes/spike2/spike2_server.py`

- [ ] **Step 1: Write the implementation**

```python
# spikes/spike2/spike2_server.py
import argparse
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="HighlightBox Spike 2 test server")
    parser.add_argument("--mode", choices=["chunks", "webrtc"], required=True)
    parser.add_argument("--cameras", type=int, choices=[1, 2], required=True)
    parser.add_argument("--cert", required=True, help="Path to mkcert-generated cert file")
    parser.add_argument("--key", required=True, help="Path to mkcert-generated key file")
    parser.add_argument("--storage-root", default="~/highlightbox-spike2")
    parser.add_argument("--static-dir", default=str(Path(__file__).parent / "static"))
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8443)
    return parser.parse_args()


def main():
    args = parse_args()
    storage_root = Path(args.storage_root).expanduser()
    static_dir = Path(args.static_dir).expanduser()
    cert_path = Path(args.cert).expanduser()
    key_path = Path(args.key).expanduser()

    if args.mode == "chunks":
        from spikes.spike2 import chunks_receiver as receiver
    else:
        from spikes.spike2 import webrtc_receiver as receiver

    receiver.run(
        storage_root=storage_root,
        n_cameras=args.cameras,
        static_dir=static_dir,
        cert_path=cert_path,
        key_path=key_path,
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the CLI parses arguments correctly**

Run: `cd /home/rocha/Projetos/ManagerReplay && python3 spikes/spike2/spike2_server.py --help`
Expected: argparse help text listing `--mode`, `--cameras`, `--cert`, `--key`, `--storage-root`, `--static-dir`, `--host`, `--port`, exit code 0

- [ ] **Step 3: Commit**

```bash
git add spikes/spike2/spike2_server.py
git commit -m "feat(spike2): add CLI entrypoint dispatching chunks/webrtc modes"
```

---

### Task 5: Client (HTML + JS)

**Files:**
- Create: `spikes/spike2/static/index.html`
- Create: `spikes/spike2/static/client.js`

- [ ] **Step 1: Write the client page**

```html
<!-- spikes/spike2/static/index.html -->
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>HighlightBox Spike 2</title>
</head>
<body>
  <h1>Spike 2 — câmera de teste</h1>
  <p>Modo: <span id="mode-label"></span> · Câmera: <span id="camera-label"></span></p>
  <p id="status">iniciando...</p>
  <video id="preview" autoplay playsinline muted style="width: 100%; max-width: 480px;"></video>
  <script src="client.js"></script>
</body>
</html>
```

- [ ] **Step 2: Write the client capture logic**

```javascript
// spikes/spike2/static/client.js
const params = new URLSearchParams(window.location.search);
const mode = params.get("mode") || "chunks";
const cameraId = params.get("camera") || "1";

const statusEl = document.getElementById("status");
document.getElementById("mode-label").textContent = mode;
document.getElementById("camera-label").textContent = cameraId;

const constraints = {
  video: { width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 30 } },
  audio: false,
};

async function startChunksMode(stream) {
  const recorder = new MediaRecorder(stream, { mimeType: "video/webm;codecs=vp8" });
  let sequence = 0;

  recorder.ondataavailable = async (event) => {
    if (event.data.size === 0) return;
    const seq = sequence++;
    await fetch(`/upload?camera=${cameraId}&seq=${seq}`, {
      method: "POST",
      body: event.data,
    });
    statusEl.textContent = `chunks: enviado chunk ${seq} (${event.data.size} bytes)`;
  };

  recorder.start(7000);
}

async function startWebrtcMode(stream) {
  const pc = new RTCPeerConnection();
  stream.getTracks().forEach((track) => pc.addTrack(track, stream));

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);

  const response = await fetch(`/offer/${cameraId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sdp: pc.localDescription.sdp, type: pc.localDescription.type }),
  });
  const answer = await response.json();
  await pc.setRemoteDescription(answer);

  pc.onconnectionstatechange = () => {
    statusEl.textContent = `webrtc: ${pc.connectionState}`;
  };
}

async function start() {
  const stream = await navigator.mediaDevices.getUserMedia(constraints);
  document.getElementById("preview").srcObject = stream;

  if (mode === "chunks") {
    await startChunksMode(stream);
  } else {
    await startWebrtcMode(stream);
  }
}

start().catch((err) => {
  statusEl.textContent = `erro: ${err.message}`;
  console.error(err);
});
```

- [ ] **Step 3: Commit**

```bash
git add spikes/spike2/static/index.html spikes/spike2/static/client.js
git commit -m "feat(spike2): add browser client for chunks and webrtc capture"
```

---

### Task 6: Dependencies and deploy-to-Pi instructions

**Files:**
- Create: `spikes/spike2/requirements.txt`
- Create: `spikes/spike2/requirements-dev.txt`

- [ ] **Step 1: Write dependency files**

```
# spikes/spike2/requirements.txt
aiohttp==3.10.11
aiortc==1.9.0
```

```
# spikes/spike2/requirements-dev.txt
pytest==8.3.3
```

- [ ] **Step 2: Run the full local test suite**

Run: `cd /home/rocha/Projetos/ManagerReplay && python3 -m venv .venv && .venv/bin/pip install -r spikes/spike2/requirements.txt -r spikes/spike2/requirements-dev.txt && .venv/bin/python -m pytest tests/spikes/spike2/ -v`
Expected: all tests pass (4 from `test_storage.py`, 1 from `test_chunks_receiver.py`)

Note: `aiortc` pulls in `av` (PyAV), which compiles native code against ffmpeg. On the dev machine this is usually a quick binary wheel install; on the Raspberry Pi 3B (ARM) it may need `ffmpeg` dev headers installed first (`sudo apt install -y libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev libswscale-dev libswresample-dev libavfilter-dev`) and can take several minutes to compile — expect this only once, when setting up the Pi's venv in Step 3 below.

- [ ] **Step 3: Commit**

```bash
git add spikes/spike2/requirements.txt spikes/spike2/requirements-dev.txt
git commit -m "chore(spike2): pin aiohttp/aiortc/pytest dependencies"
```

- [ ] **Step 4: Deploy the code to the Pi**

Run from the dev machine:
```bash
rsync -av --exclude .venv --exclude __pycache__ /home/rocha/Projetos/ManagerReplay/spikes/spike2 rocha@ManagerReplay.local:~/spike2/
```
Expected: file list synced, exit code 0

- [ ] **Step 5: Set up the venv on the Pi (one-time)**

Run over SSH (`ssh rocha@ManagerReplay.local`):
```bash
sudo apt install -y libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev libswscale-dev libswresample-dev libavfilter-dev
cd ~/spike2
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```
Expected: `aiortc` and `aiohttp` install successfully (this step can take several minutes on first run due to `av` compiling from source)

---

### Task 7: Execution runbook and results table

The physical test matrix (smoke test + full 15-20min run × 4 combinations) is executed by hand against real phones and the real Pi — it is not automatable. This task produces the runbook document the operator follows, and the results table template to fill in during/after testing.

**Files:**
- Create: `docs/superpowers/runbooks/2026-08-20-spike2-execution.md`

- [ ] **Step 1: Write the runbook**

```markdown
# Runbook — Spike 2 execução (1 e 2 câmeras)

Pré-requisitos:
- Código já sincronizado e venv pronta na Pi (Task 6 do plano).
- Certificado mkcert do Spike 1 disponível na Pi (ex: `~/spike1/192.168.4.1.pem` e `~/spike1/192.168.4.1-key.pem` — ajustar caminho conforme o Spike 1 real).
- 2 celulares Android, ambos na rede do hotspot do Pi.
- Hotspot do Pi em modo aberto: `nmcli device wifi hotspot ifname wlan0 ssid HighlightBox-Test`.
- `monitor.sh`/`monitor2.sh` já presentes no home da Pi (conforme checkpoint do `ContextoProjeto.md`).

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
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/runbooks/2026-08-20-spike2-execution.md
git commit -m "docs(spike2): add manual execution runbook and results table"
```

---

## Out of scope (matches design doc)

- 1080p testing, WPA2 hotspot testing, SQLite/production storage layout, real SFU implementation, iPhone testing, numeric pass/fail thresholds for CPU/RAM/temperature — all deferred per the design doc's "Fora do escopo" section.
