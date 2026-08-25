# Swipe-to-delete em Lances — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the operator swipe-to-delete a lance card in `lances.html` (same gesture/password flow as `files.html`), removing both its `events.jsonl` entry and its physical clip file.

**Architecture:** A new `events.remove_event(events_file, nome)` rewrites `events.jsonl` without the matching line and returns the removed event (or `None`). A new `POST /delete-lance` handler in `chunks_receiver.py` reuses the existing `admin_password` check, calls `remove_event`, then best-effort deletes the clip file computed from the removed event's `camera`/`timestamp`. `lances.html` gets the same swipe-wrapper + delete-modal markup/CSS/JS already proven in `files.html`, adapted to call `/delete-lance?nome=...` instead of `/delete-file?path=...`. Along the way, `lances.html`'s stale `CAMERA_LABELS` map gets the same fix already applied to `cameras.html`/`gravando.html`.

**Tech Stack:** Python stdlib (`http.server`), `pytest`, plain HTML/JS — matches existing project stack.

---

### Task 1: `events.remove_event`

**Files:**
- Modify: `server/events.py`
- Test: `tests/server/test_events.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/server/test_events.py`:

```python
def test_remove_event_deletes_matching_event_and_returns_it(tmp_path: Path):
    events_file = tmp_path / "events.jsonl"
    record_event(events_file, camera_id="1")
    second = record_event(events_file, camera_id="2")

    removed = remove_event(events_file, "Lance Epico 001")

    assert removed["nome"] == "Lance Epico 001"
    remaining = list_events(events_file)
    assert [e["nome"] for e in remaining] == ["Lance Epico 002"]
    assert remaining[0] == second


def test_remove_event_returns_none_when_name_not_found(tmp_path: Path):
    events_file = tmp_path / "events.jsonl"
    record_event(events_file, camera_id="1")

    removed = remove_event(events_file, "Lance Epico 999")

    assert removed is None
    assert len(list_events(events_file)) == 1
```

Update the import line at the top of the file:

```python
from server.events import list_events, record_event, remove_event
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/server/test_events.py -v`
Expected: FAIL with `ImportError: cannot import name 'remove_event'`

- [ ] **Step 3: Implement `remove_event`**

In `server/events.py`, add after `record_event`:

```python
def remove_event(events_file: Path, nome: str) -> dict | None:
    events = list_events(events_file)
    removed = next((e for e in events if e["nome"] == nome), None)
    if removed is None:
        return None

    remaining = [e for e in events if e["nome"] != nome]
    with events_file.open("w", encoding="utf-8") as f:
        for event in remaining:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return removed
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/server/test_events.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add server/events.py tests/server/test_events.py
git commit -m "Adiciona events.remove_event pra apagar um lance por nome"
```

---

### Task 2: `POST /delete-lance` endpoint

**Files:**
- Modify: `server/chunks_receiver.py` (`do_POST` routing around line 234, new handler near `_handle_delete_file`)
- Test: `tests/server/test_chunks_receiver.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/server/test_chunks_receiver.py`, after `test_delete_file_returns_404_for_unknown_recording` (end of file):

```python
def test_delete_lance_rejects_wrong_password(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    server, thread, port = _start_server(tmp_path, cert_path, key_path)

    try:
        conn = _https_connection(port)
        conn.request("POST", "/events?camera=1")
        conn.getresponse().read()

        conn = _https_connection(port)
        conn.request(
            "POST", "/delete-lance?nome=Lance+Epico+001",
            body="password=wrong",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response = conn.getresponse()
        response.read()
        assert response.status == 403
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_delete_lance_returns_404_for_unknown_name(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    server, thread, port = _start_server(tmp_path, cert_path, key_path)

    try:
        conn = _https_connection(port)
        conn.request(
            "POST", "/delete-lance?nome=Nao+Existe",
            body=f"password={ADMIN_PASSWORD}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response = conn.getresponse()
        response.read()
        assert response.status == 404
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_delete_lance_removes_event_and_clip(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    storage_root = tmp_path / "storage"
    server, thread, port = _start_server(tmp_path, cert_path, key_path, storage_root)

    try:
        conn = _https_connection(port)
        conn.request("POST", "/events?camera=2")
        event = json.loads(conn.getresponse().read())

        conn = _https_connection(port)
        conn.request(
            "POST", f"/lance-clip?camera=2&nome={event['nome'].replace(' ', '+')}",
            body=b"clip-bytes",
        )
        conn.getresponse().read()

        clip_matches = list(storage_root.glob("*/lances/lance_camera2_LanceEpico001.webm"))
        assert len(clip_matches) == 1

        conn = _https_connection(port)
        conn.request(
            "POST", f"/delete-lance?nome={event['nome'].replace(' ', '+')}",
            body=f"password={ADMIN_PASSWORD}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response = conn.getresponse()
        response.read()
        assert response.status == 204

        conn = _https_connection(port)
        conn.request("GET", "/events-list")
        remaining = json.loads(conn.getresponse().read())
        assert remaining == []
        assert not clip_matches[0].exists()
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_delete_lance_succeeds_when_clip_was_never_uploaded(tmp_path: Path, self_signed_cert):
    cert_path, key_path = self_signed_cert
    server, thread, port = _start_server(tmp_path, cert_path, key_path)

    try:
        conn = _https_connection(port)
        conn.request("POST", "/events?camera=1")
        event = json.loads(conn.getresponse().read())

        conn = _https_connection(port)
        conn.request(
            "POST", f"/delete-lance?nome={event['nome'].replace(' ', '+')}",
            body=f"password={ADMIN_PASSWORD}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response = conn.getresponse()
        response.read()
        assert response.status == 204
    finally:
        server.shutdown()
        thread.join(timeout=2)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/server/test_chunks_receiver.py -k delete_lance -v`
Expected: FAIL — `/delete-lance` currently 404s (unrouted), so the wrong-password/unknown-name tests get a 404 instead of 403/404-as-expected mismatch on the first one, and the removal tests fail their assertions.

- [ ] **Step 3: Add the route and handler**

In `server/chunks_receiver.py`, add the route inside `do_POST` (currently around line 234, right after the `/delete-file` branch):

```python
        elif self.path.startswith("/delete-file"):
            self._handle_delete_file()
        elif self.path.startswith("/delete-lance"):
            self._handle_delete_lance()
        else:
```

Add the import for `remove_event` at the top of the file, next to the existing `events` import:

```python
from server.events import list_events, record_event, remove_event
```

Add the handler right after `_handle_delete_file` (before `_handle_session_start`):

```python
    def _handle_delete_lance(self):
        query = parse_qs(urlparse(self.path).query)
        nome = unquote(query.get("nome", [""])[0])

        length = int(self.headers.get("Content-Length", 0))
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        password = form.get("password", [""])[0]

        if not nome or not self.admin_password or not hmac.compare_digest(password, self.admin_password):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"senha incorreta")
            return

        removed = remove_event(self.events_file, nome)
        if removed is None:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"nao encontrado")
            return

        clip_path = (
            self.storage_root
            / removed["timestamp"][:10]
            / "lances"
            / f"lance_camera{removed['camera']}_{sanitize_lance_name(nome)}.webm"
        )
        if clip_path.exists():
            clip_path.unlink()

        self.send_response(204)
        self.end_headers()
```

Add `sanitize_lance_name` to the existing `server.storage` import at the top of the file:

```python
from server.storage import build_day_dir, find_session_parts, sanitize_lance_name, save_chunk, save_lance_clip
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/server/test_chunks_receiver.py -v`
Expected: PASS (all tests, including the 4 new `delete_lance` ones)

- [ ] **Step 5: Commit**

```bash
git add server/chunks_receiver.py tests/server/test_chunks_receiver.py
git commit -m "Adiciona endpoint POST /delete-lance protegido por senha admin"
```

---

### Task 3: Swipe-to-delete UI in `lances.html`, plus the stale label fix

**Files:**
- Modify: `server/static/lances.html`

- [ ] **Step 1: Fix the stale `CAMERA_LABELS` map**

Replace:

```javascript
    // Labels de posição dos slots de câmera — mesmo mapeamento de cameras.html.
    const CAMERA_LABELS = { 1: "Gol", 2: "Lateral Esquerda", 3: "Lateral Direita", 4: "Geral" };
```

with:

```javascript
    // Labels de posição dos slots de câmera — mesmo mapeamento de cameras.html.
    const CAMERA_LABELS = { 1: "Gol A", 2: "Gol B", 3: "Arquibancada A", 4: "Arquibancada B", 5: "Geral" };
```

- [ ] **Step 2: Add swipe/modal CSS**

In the `<style>` block, right after `.lance-action { ... }` and before `#empty { ... }`, add (copied from `files.html`'s equivalent rules, renamed to `lance-*`/reusing the same `#delete-*` modal ids so both pages could theoretically share a stylesheet later, but for now duplicated inline like every other page in this project):

```css
    .lance-swipe { position: relative; margin-bottom: 9px; overflow: hidden; border-radius: var(--radius-md); }
    .lance-delete-bg {
      position: absolute;
      inset: 0;
      display: flex;
      justify-content: flex-end;
      align-items: stretch;
      background: var(--danger);
      border-radius: var(--radius-md);
    }
    .lance-delete-btn {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 3px;
      width: 84px;
      background: none;
      border: none;
      color: #fff;
      font-size: 0.7rem;
      font-weight: 700;
      cursor: pointer;
    }
    .lance-swipe .card.lance-card { position: relative; touch-action: pan-y; transition: transform 0.12s ease; margin-bottom: 0; }
    .lance-swipe.swiping .card.lance-card { transition: none; }
    .lance-swipe.exiting { max-height: 0; margin-bottom: 0; opacity: 0; transition: max-height 0.2s ease, opacity 0.2s ease, margin-bottom 0.2s ease; }

    #delete-modal-overlay {
      position: fixed;
      inset: 0;
      background: rgba(15, 23, 42, 0.55);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
      z-index: 1000;
    }
    #delete-modal-overlay[hidden] { display: none; }
    #delete-modal {
      background: var(--card-bg);
      padding: 18px;
      max-width: 380px;
      width: 100%;
      border-radius: var(--radius-md);
      box-shadow: var(--shadow-lg);
    }
    #delete-modal h2 { font-size: 1rem; margin: 0 0 6px; }
    #delete-modal p { font-size: 0.85rem; color: var(--text-secondary); margin: 0 0 14px; overflow-wrap: break-word; }
    #delete-password {
      display: block;
      width: 100%;
      padding: 12px 14px;
      font-size: 1rem;
      background: var(--bg);
      border: 1px solid var(--border-strong);
      color: var(--text);
      border-radius: var(--radius-sm);
      margin-bottom: 8px;
    }
    #delete-error { color: var(--danger); font-size: 0.8rem; font-weight: 700; min-height: 1.2em; margin-bottom: 8px; }
    #delete-modal-actions { display: flex; gap: 8px; }
    #delete-modal-actions button {
      flex: 1;
      padding: 11px;
      border-radius: var(--radius-sm);
      font-weight: 700;
      font-size: 0.85rem;
      cursor: pointer;
      border: none;
    }
    #delete-cancel { background: var(--bg); color: var(--text); }
    #delete-confirm { background: var(--danger); color: #fff; }
```

- [ ] **Step 3: Add the delete-modal markup**

Right after `<div id="content"></div>` and before the closing `</div>` of `.page`, add:

```html
    <div id="content"></div>

  </div>

  <div id="delete-modal-overlay" hidden>
    <div id="delete-modal">
      <h2>Excluir</h2>
      <p id="delete-modal-target"></p>
      <input id="delete-password" type="password" placeholder="Senha admin" autocomplete="off" />
      <div id="delete-error"></div>
      <div id="delete-modal-actions">
        <button id="delete-cancel" type="button">Cancelar</button>
        <button id="delete-confirm" type="button">Excluir</button>
      </div>
    </div>
  </div>
```

(This replaces the existing `<div id="content"></div>\n\n  </div>` block — same two lines, with the modal markup inserted between the `.page` close and the `</body>`.)

- [ ] **Step 4: Wrap each card in a swipe wrapper with a delete button**

Replace `renderCard`:

```javascript
    function renderCard(event) {
      const url = clipUrl(event);
      return `
        <div class="card lance-card">
          <div class="lance-top">
            <div>
              <div class="lance-name">${escapeHtml(event.nome)}</div>
              <div class="lance-meta">${ICON_CAMERA} ${cameraLabel(event.camera)} · ${ICON_CLOCK} ${formatDate(event.timestamp)}</div>
            </div>
            <a class="lance-action" href="${url}" download>${ICON_DOWNLOAD} Baixar</a>
          </div>
        </div>
      `;
    }
```

with:

```javascript
    const ICON_TRASH = '<svg class="icon" viewBox="0 0 24 24"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>';

    function renderCard(event) {
      const url = clipUrl(event);
      const wrapper = document.createElement("div");
      wrapper.className = "lance-swipe";
      wrapper.dataset.nome = event.nome;
      wrapper.innerHTML = `
        <div class="lance-delete-bg">
          <button class="lance-delete-btn" type="button">${ICON_TRASH}Excluir</button>
        </div>
        <div class="card lance-card">
          <div class="lance-top">
            <div>
              <div class="lance-name">${escapeHtml(event.nome)}</div>
              <div class="lance-meta">${ICON_CAMERA} ${cameraLabel(event.camera)} · ${ICON_CLOCK} ${formatDate(event.timestamp)}</div>
            </div>
            <a class="lance-action" href="${url}" download>${ICON_DOWNLOAD} Baixar</a>
          </div>
        </div>
      `;
      return wrapper;
    }
```

- [ ] **Step 5: Change `render` to append DOM nodes instead of joining HTML strings**

`renderCard` now returns a DOM element instead of an HTML string, so `render` can no longer use `.map(renderCard).join("")`. Replace:

```javascript
    function render(events) {
      if (events.length === 0) {
        contentEl.innerHTML = '<div id="empty">Nenhum lance registrado ainda.</div>';
        return;
      }
      contentEl.innerHTML = events.slice().reverse().map(renderCard).join("");
    }
```

with:

```javascript
    function render(events) {
      if (events.length === 0) {
        contentEl.innerHTML = '<div id="empty">Nenhum lance registrado ainda.</div>';
        return;
      }
      contentEl.innerHTML = "";
      events.slice().reverse().forEach((event) => contentEl.appendChild(renderCard(event)));
    }
```

- [ ] **Step 6: Add the swipe gesture and delete-modal logic**

At the end of the `<script>` block, right before `load();` and the `setInterval(load, 5000);` line, insert (and keep `load();`/`setInterval` calls where they are, after this new code — order doesn't matter here since these only attach listeners and define functions, but keep `load()` as the last executable statement for readability, matching the original file's structure):

Replace:

```javascript
    load();
    setInterval(load, 5000);
```

with:

```javascript
    // --- Swipe-to-delete -------------------------------------------------
    const REVEAL_PX = 84;
    const SWIPE_THRESHOLD_PX = 40;

    let activeSwipe = null; // { wrapper, front, startX, currentX, moved }

    function closeSwipe(wrapper) {
      if (!wrapper) return;
      wrapper.classList.remove("swiping", "open");
      wrapper.querySelector(".lance-card").style.transform = "";
    }

    function closeAllSwipesExcept(except) {
      contentEl.querySelectorAll(".lance-swipe").forEach((el) => {
        if (el !== except) closeSwipe(el);
      });
    }

    contentEl.addEventListener("touchstart", (event) => {
      const wrapper = event.target.closest(".lance-swipe");
      if (!wrapper) return;
      const front = wrapper.querySelector(".lance-card");
      closeAllSwipesExcept(wrapper);
      activeSwipe = { wrapper, front, startX: event.touches[0].clientX, currentX: 0, moved: false };
      wrapper.classList.add("swiping");
    });

    contentEl.addEventListener("touchmove", (event) => {
      if (!activeSwipe) return;
      const dx = event.touches[0].clientX - activeSwipe.startX;
      const alreadyOpen = activeSwipe.wrapper.classList.contains("open");
      const base = alreadyOpen ? -REVEAL_PX : 0;
      const next = Math.max(-REVEAL_PX, Math.min(0, base + dx));
      if (Math.abs(dx) > 8) activeSwipe.moved = true;
      activeSwipe.currentX = next;
      activeSwipe.front.style.transform = `translateX(${next}px)`;
    }, { passive: true });

    contentEl.addEventListener("touchend", () => {
      if (!activeSwipe) return;
      const { wrapper, front, currentX } = activeSwipe;
      wrapper.classList.remove("swiping");
      const shouldOpen = currentX <= -SWIPE_THRESHOLD_PX;
      front.style.transform = shouldOpen ? `translateX(-${REVEAL_PX}px)` : "";
      wrapper.classList.toggle("open", shouldOpen);
      activeSwipe = null;
    });

    contentEl.addEventListener("click", (event) => {
      const wrapper = event.target.closest(".lance-swipe");
      if (wrapper && wrapper.classList.contains("open") && !event.target.closest(".lance-delete-btn")) {
        event.preventDefault();
      }
    });

    // --- Delete modal ------------------------------------------------------
    const deleteOverlay = document.getElementById("delete-modal-overlay");
    const deleteTargetLabel = document.getElementById("delete-modal-target");
    const deletePasswordInput = document.getElementById("delete-password");
    const deleteErrorEl = document.getElementById("delete-error");
    const deleteConfirmBtn = document.getElementById("delete-confirm");

    let pendingDeleteWrapper = null;

    function openDeleteModal(wrapper) {
      pendingDeleteWrapper = wrapper;
      const name = wrapper.querySelector(".lance-name").textContent;
      deleteTargetLabel.textContent = `Apagar "${name}"? Essa ação não pode ser desfeita.`;
      deletePasswordInput.value = "";
      deleteErrorEl.textContent = "";
      deleteOverlay.hidden = false;
      deletePasswordInput.focus();
    }

    function closeDeleteModal() {
      deleteOverlay.hidden = true;
      pendingDeleteWrapper = null;
    }

    contentEl.addEventListener("click", (event) => {
      const btn = event.target.closest(".lance-delete-btn");
      if (!btn) return;
      const wrapper = btn.closest(".lance-swipe");
      openDeleteModal(wrapper);
    });

    document.getElementById("delete-cancel").addEventListener("click", closeDeleteModal);

    deleteConfirmBtn.addEventListener("click", async () => {
      if (!pendingDeleteWrapper) return;
      const wrapper = pendingDeleteWrapper;
      deleteErrorEl.textContent = "";
      try {
        const response = await fetch(`/delete-lance?nome=${encodeURIComponent(wrapper.dataset.nome)}`, {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: `password=${encodeURIComponent(deletePasswordInput.value)}`,
        });
        if (response.status === 403) {
          deleteErrorEl.textContent = "Senha incorreta.";
          return;
        }
        if (!response.ok) {
          deleteErrorEl.textContent = "Não deu pra apagar (erro no servidor).";
          return;
        }
        closeDeleteModal();
        wrapper.classList.add("exiting");
        wrapper.addEventListener("transitionend", () => wrapper.remove(), { once: true });
      } catch (err) {
        deleteErrorEl.textContent = "Falha de conexão — tenta de novo.";
      }
    });

    load();
    setInterval(load, 5000);
```

- [ ] **Step 7: Verify**

```bash
python3 -c "
import re
content = open('server/static/lances.html').read()
m = re.search(r'<script>(.*)</script>', content, re.S)
open('/tmp/lances_check.js', 'w').write(m.group(1))
"
node --check /tmp/lances_check.js && echo "JS syntax OK"
```
Expected: `JS syntax OK`

No live-browser verification available in this environment (same limitation as every other static page in this project). Static check: confirm `wrapper.dataset.nome` is set in `renderCard` (Step 4) and read in the fetch call (Step 6) — the identifier flowing end-to-end without a typo.

- [ ] **Step 8: Commit**

```bash
git add server/static/lances.html
git commit -m "Adiciona swipe-to-delete em Lances, protegido por senha admin"
```

---

### Task 4: Bump `VERSION`

**Files:**
- Modify: `VERSION`

- [ ] **Step 1: Bump the version number**

Change `VERSION` from `1.1` to `1.2`.

- [ ] **Step 2: Commit**

```bash
git add VERSION
git commit -m "Bump VERSION para 1.2"
```
