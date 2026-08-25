# Versão do sistema na tela Monitor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the app's version number (from a manually-bumped `VERSION` file) on the Monitor screen, so the operator can confirm a deploy actually landed on the Pi.

**Architecture:** A `VERSION` file at the repo root (already created, contains `1.0`) is read once at server startup — same pattern as `admin-password.txt` — and stored on `ChunksUploadHandler`. The `/monitor-status` handler adds it to the JSON response (same place `disk_used_mb`/`external_storage` already get added after `read_live_status()`). `monitor.html` renders a small card with the value.

**Tech Stack:** Python stdlib (`http.server`), `pytest`, plain HTML/JS (no framework) — matches existing project stack, no new dependencies.

---

### Task 1: `build_server`/`run` read and store the version file

**Files:**
- Modify: `server/chunks_receiver.py:30-48` (class attributes), `server/chunks_receiver.py:445-494` (`build_server`, `run`)
- Test: `tests/server/test_chunks_receiver.py`

- [ ] **Step 1: Write the failing test for `build_server` refusing to start without a version file**

Add to `tests/server/test_chunks_receiver.py`, near the top-level test functions (after the `_https_connection` helper, before the first `def test_...`):

```python
def test_build_server_refuses_to_start_without_version_file(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    admin_password_file = tmp_path / "admin-password.txt"
    admin_password_file.write_text(ADMIN_PASSWORD, encoding="utf-8")
    missing_version_file = tmp_path / "does-not-exist" / "VERSION"

    with pytest.raises(FileNotFoundError, match="version file not found"):
        chunks_receiver.build_server(
            storage_root=tmp_path / "storage",
            n_cameras=1,
            static_dir=tmp_path / "static",
            cert_path=cert_path,
            key_path=key_path,
            events_file=tmp_path / "events.jsonl",
            admin_password_file=admin_password_file,
            version_file=missing_version_file,
            host="127.0.0.1",
            port=0,
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/server/test_chunks_receiver.py::test_build_server_refuses_to_start_without_version_file -v`
Expected: FAIL with `TypeError: build_server() got an unexpected keyword argument 'version_file'`

- [ ] **Step 3: Add `app_version` class attribute and `version_file` handling to `build_server`/`run`**

In `server/chunks_receiver.py`, add the new class attribute next to the existing ones (around line 37, right after `admin_password: str = None`):

```python
class ChunksUploadHandler(SimpleHTTPRequestHandler):
    storage_root: Path = None
    default_storage_root: Path = None
    n_cameras: int = 1
    events_file: Path = None
    sessions_registry: dict = None
    sessions_lock: threading.Lock = None
    admin_password: str = None
    app_version: str = None
```

Update `build_server` (currently at line 445) to accept and validate `version_file`:

```python
def build_server(
    storage_root: Path,
    n_cameras: int,
    static_dir: Path,
    cert_path: Path,
    key_path: Path,
    events_file: Path,
    admin_password_file: Path,
    version_file: Path,
    host: str = "0.0.0.0",
    port: int = 8443,
) -> ThreadingHTTPServer:
    if not admin_password_file.is_file():
        raise FileNotFoundError(
            f"admin password file not found: {admin_password_file} "
            "(needed to gate deleting recordings -- create it with the password in plain text)"
        )
    if not version_file.is_file():
        raise FileNotFoundError(
            f"version file not found: {version_file} "
            "(needed to show the app version on the Monitor screen -- create it with the version number in plain text)"
        )

    ChunksUploadHandler.storage_root = storage_root
    ChunksUploadHandler.default_storage_root = storage_root
    ChunksUploadHandler.n_cameras = n_cameras
    ChunksUploadHandler.events_file = events_file
    ChunksUploadHandler.admin_password = admin_password_file.read_text(encoding="utf-8").strip()
    ChunksUploadHandler.app_version = version_file.read_text(encoding="utf-8").strip()
    ChunksUploadHandler.sessions_registry = {}
    ChunksUploadHandler.sessions_lock = threading.Lock()
    handler = partial(ChunksUploadHandler, directory=str(static_dir))

    server = ThreadingHTTPServer((host, port), handler)
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    server.socket = ssl_context.wrap_socket(server.socket, server_side=True)
    return server
```

Update `run` (currently at line 478) the same way:

```python
def run(
    storage_root: Path,
    n_cameras: int,
    static_dir: Path,
    cert_path: Path,
    key_path: Path,
    events_file: Path,
    admin_password_file: Path,
    version_file: Path,
    host: str = "0.0.0.0",
    port: int = 8443,
):
    storage_root.mkdir(parents=True, exist_ok=True)
    server = build_server(
        storage_root, n_cameras, static_dir, cert_path, key_path, events_file,
        admin_password_file, version_file, host, port,
    )
    print(f"[chunks] listening on https://{host}:{port}, storage={storage_root}")
```

- [ ] **Step 4: Update the shared test helper `_start_server` to pass a `version_file`**

In `tests/server/test_chunks_receiver.py`, update `_start_server` (currently lines 35-59) so every existing test keeps working:

```python
def _start_server(tmp_path, cert_path, key_path, storage_root=None):
    storage_root = storage_root or (tmp_path / "storage")
    static_dir = tmp_path / "static"
    static_dir.mkdir(exist_ok=True)
    events_file = tmp_path / "events.jsonl"
    admin_password_file = tmp_path / "admin-password.txt"
    if not admin_password_file.exists():
        admin_password_file.write_text(ADMIN_PASSWORD, encoding="utf-8")
    version_file = tmp_path / "VERSION"
    if not version_file.exists():
        version_file.write_text("1.0-test", encoding="utf-8")

    server = chunks_receiver.build_server(
        storage_root=storage_root,
        n_cameras=2,
        static_dir=static_dir,
        cert_path=cert_path,
        key_path=key_path,
        events_file=events_file,
        admin_password_file=admin_password_file,
        version_file=version_file,
        host="127.0.0.1",
        port=0,
    )
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    return server, thread, port
```

- [ ] **Step 5: Run the full test file to verify everything still passes**

Run: `.venv/bin/python -m pytest tests/server/test_chunks_receiver.py -v`
Expected: PASS (all tests, including the new `test_build_server_refuses_to_start_without_version_file`)

- [ ] **Step 6: Commit**

```bash
git add server/chunks_receiver.py tests/server/test_chunks_receiver.py
git commit -m "Faz build_server/run exigirem e carregarem o arquivo VERSION"
```

---

### Task 2: Expose `app_version` in `/monitor-status`

**Files:**
- Modify: `server/chunks_receiver.py:198-215` (`_handle_monitor_status`)
- Test: `tests/server/test_chunks_receiver.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/server/test_chunks_receiver.py`, right after `test_monitor_status_route_returns_live_reading_plus_disk_usage`:

```python
def test_monitor_status_route_returns_app_version(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    fake_status = {
        "timestamp": "2026-08-20 18:00:00",
        "cpu_pct": 8.2,
        "ram_used_mb": 164,
        "ram_total_mb": 955,
        "temp_c": 41.3,
        "arm_clock_mhz": 700,
        "core_clock_mhz": 275,
        "undervoltage_now": False,
        "freq_capped_now": False,
        "throttled_now": False,
        "undervoltage_ever": False,
    }

    version_file = tmp_path / "VERSION"
    version_file.write_text("2.3\n", encoding="utf-8")

    with patch("server.chunks_receiver.read_live_status", return_value=fake_status), \
         patch("server.chunks_receiver.detect_external_storage", return_value=[]):
        static_dir = tmp_path / "static"
        static_dir.mkdir(exist_ok=True)
        admin_password_file = tmp_path / "admin-password.txt"
        admin_password_file.write_text(ADMIN_PASSWORD, encoding="utf-8")
        server = chunks_receiver.build_server(
            storage_root=tmp_path / "storage",
            n_cameras=1,
            static_dir=static_dir,
            cert_path=cert_path,
            key_path=key_path,
            events_file=tmp_path / "events.jsonl",
            admin_password_file=admin_password_file,
            version_file=version_file,
            host="127.0.0.1",
            port=0,
        )
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.2)
        try:
            conn = _https_connection(port)
            conn.request("GET", "/monitor-status")
            response = conn.getresponse()
            body = json.loads(response.read())
        finally:
            server.shutdown()
            thread.join(timeout=2)

    assert response.status == 200
    assert body["app_version"] == "2.3"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/server/test_chunks_receiver.py::test_monitor_status_route_returns_app_version -v`
Expected: FAIL with `KeyError: 'app_version'`

- [ ] **Step 3: Add `app_version` to the response in `_handle_monitor_status`**

In `server/chunks_receiver.py`, update `_handle_monitor_status` (currently lines 198-215):

```python
    def _handle_monitor_status(self):
        try:
            status = read_live_status()
        except (OSError, ValueError) as err:
            self.send_response(503)
            self.end_headers()
            self.wfile.write(str(err).encode("utf-8"))
            return

        status.update(get_disk_usage(self.storage_root))
        status["external_storage"] = detect_external_storage()
        status["app_version"] = self.app_version

        body = json.dumps(status).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/server/test_chunks_receiver.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add server/chunks_receiver.py tests/server/test_chunks_receiver.py
git commit -m "Inclui app_version na resposta de /monitor-status"
```

---

### Task 3: `app.py` CLI argument for the version file

**Files:**
- Modify: `server/app.py`

- [ ] **Step 1: Add `--version-file` argument and wire it into `run_kwargs`**

In `server/app.py`, add the new argument next to `--admin-password-file` (currently line 19):

```python
    parser.add_argument("--admin-password-file", default="~/managerreplay/admin-password.txt")
    parser.add_argument("--version-file", default="~/managerreplay/VERSION")
```

Update `main()` so the `chunks` branch (currently lines 45-47) also resolves and passes it:

```python
    if args.mode == "chunks":
        from server import chunks_receiver as receiver
        run_kwargs["admin_password_file"] = Path(args.admin_password_file).expanduser()
        run_kwargs["version_file"] = Path(args.version_file).expanduser()
    else:
        from server import webrtc_receiver as receiver
```

- [ ] **Step 2: Verify manually that argument parsing doesn't crash**

Run: `.venv/bin/python -c "import sys; sys.argv = ['app.py', '--mode=chunks', '--cameras=1', '--cert=x', '--key=y']; sys.path.insert(0, '.'); from server.app import parse_args; a = parse_args(); print(a.version_file)"`
Expected output: `~/managerreplay/VERSION`

- [ ] **Step 3: Run the full server test suite to make sure nothing else broke**

Run: `.venv/bin/python -m pytest tests/server/ -v`
Expected: PASS (all tests)

- [ ] **Step 4: Commit**

```bash
git add server/app.py
git commit -m "Adiciona --version-file ao CLI do servidor"
```

---

### Task 4: Show the version on `monitor.html`

**Files:**
- Modify: `server/static/monitor.html:369-410` (the `render` function)

- [ ] **Step 1: Add a version card to the rendered markup**

In `server/static/monitor.html`, inside the `render(status, storageOptions)` function, add a new card as the first thing inside the returned template literal — right before the existing `<div class="grid">` (currently line 370):

```javascript
      contentEl.innerHTML = `
        <div class="card stat-card" style="margin-bottom: 10px;">
          <div class="label">Versão</div>
          <div class="value" style="font-size:1.1em;">v${escapeHtml(status.app_version)}</div>
        </div>

        <div class="grid">
          <div class="card stat-card">
            <div class="label">CPU</div>
            <div class="value ${cpuClass(status.cpu_pct)}">${status.cpu_pct.toFixed(1)}%</div>
          </div>
```

(Leave the rest of the function — everything from `<div class="card stat-card"><div class="label">Temperatura</div>` onward — exactly as it is today; only the new card and the opening of the existing `.grid` div change.)

- [ ] **Step 2: Manually verify in a browser**

Run the server locally (from repo root, with a test cert and files already in place from prior manual testing, or generate one with mkcert as documented in the README) and open `/monitor.html`. Confirm a "Versão" card shows `v1.0` at the top, above the CPU/Temperature grid, matching the repo's `VERSION` file content.

If no local HTTPS setup is readily available, at minimum verify by inspection that `status.app_version` is used consistently with the naming already established in Task 2 (`app_version`, not `version` or `appVersion`), and that `escapeHtml` is already defined earlier in the same file (it is, at line 256) so no new helper is needed.

- [ ] **Step 3: Commit**

```bash
git add server/static/monitor.html
git commit -m "Mostra a versão do app no topo da tela Monitor"
```

---

### Task 5: Document the VERSION file in the deploy flow

**Files:**
- Modify: `README.md` (the "Deploy no Raspberry Pi" section, currently around lines 74-104)

- [ ] **Step 1: Add a step for syncing `VERSION` and a reminder to bump it**

In `README.md`, insert a new step between step 1 ("Sincronizar o código") and step 2 ("Gerar o certificado HTTPS") of the "Deploy no Raspberry Pi" section:

```markdown
2. **Sincronizar a versão** (bump o número em `VERSION` antes de commitar qualquer mudança que valha marcar como nova versão; depois copie o arquivo pra Pi):
   ```bash
   scp VERSION rocha@<ip-da-pi>:~/managerreplay/VERSION
   ```
   A tela **Monitor** mostra esse número — depois de um deploy, confira lá se bate com o que você esperava, como forma de confirmar que o deploy realmente pegou.
```

Renumber the subsequent steps ("Gerar o certificado HTTPS" becomes step 3, "Subir o servidor" becomes step 4).

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "Documenta o deploy do arquivo VERSION no README"
```
