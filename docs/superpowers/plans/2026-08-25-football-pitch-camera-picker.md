# Campo de futebol na escolha de câmera — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the vertical list of 4 camera-slot cards in `cameras.html` with an SVG football pitch showing 5 tappable position markers (Gol Esquerdo, Gol Direito, Arquibancada Esquerda, Arquibancada Direita, Geral), keeping the existing busy-slot polling and lens-choice flow.

**Architecture:** `cameras.html` keeps its existing name-input → camera-step flow untouched. The list of `.camera-slot` cards is replaced by an inline SVG pitch diagram with 5 marker groups positioned by fixed coordinates, plus a single detail panel below the SVG that shows the selected slot's name and the two lens-choice links (reusing the exact same link-building logic that exists today). `gravando.html`'s duplicate label map is updated to match. `app.py`'s `--cameras` argparse choice grows to include 5.

**Tech Stack:** Plain HTML/CSS/JS (no framework, no SVG library) — matches existing project stack.

---

### Task 1: Update camera slot labels in `gravando.html`

**Files:**
- Modify: `server/static/gravando.html:94-100`

- [ ] **Step 1: Replace the `CAMERA_LABELS` map**

In `server/static/gravando.html`, replace:

```javascript
    // Labels de posição dos slots de câmera — mesmo mapeamento de cameras.html.
    const CAMERA_LABELS = {
      1: "Gol",
      2: "Lateral Esquerda",
      3: "Lateral Direita",
      4: "Geral",
    };
```

with:

```javascript
    // Labels de posição dos slots de câmera — mesmo mapeamento de cameras.html.
    const CAMERA_LABELS = {
      1: "Gol Esquerdo",
      2: "Gol Direito",
      3: "Arquibancada Esquerda",
      4: "Arquibancada Direita",
      5: "Geral",
    };
```

- [ ] **Step 2: Manually verify**

Open `server/static/gravando.html` in a text viewer and confirm the map now has exactly 5 entries matching the table in the spec (`docs/superpowers/specs/2026-08-25-football-pitch-camera-picker-design.md`). No automated test exists for this file (no UI test framework in the project, same as every other static page).

- [ ] **Step 3: Commit**

```bash
git add server/static/gravando.html
git commit -m "Atualiza labels de posição de câmera pras 5 posições do campo"
```

---

### Task 2: `--cameras` accepts up to 5

**Files:**
- Modify: `server/app.py:14`

- [ ] **Step 1: Widen the argparse choices**

In `server/app.py`, replace:

```python
    parser.add_argument("--cameras", type=int, choices=[1, 2, 3, 4], required=True)
```

with:

```python
    parser.add_argument("--cameras", type=int, choices=[1, 2, 3, 4, 5], required=True)
```

- [ ] **Step 2: Verify manually**

Run: `.venv/bin/python -c "import sys; sys.argv = ['app.py', '--mode=chunks', '--cameras=5', '--cert=x', '--key=y']; sys.path.insert(0, '.'); from server.app import parse_args; a = parse_args(); print(a.cameras)"`
Expected output: `5`

- [ ] **Step 3: Run the full test suite to confirm nothing else depends on the old choice set**

Run: `.venv/bin/python -m pytest tests/server/ -v`
Expected: PASS (all tests — none of them exercise `app.py`'s argparse today, this just guards against an unrelated regression)

- [ ] **Step 4: Commit**

```bash
git add server/app.py
git commit -m "Permite até 5 câmeras simultâneas no CLI do servidor"
```

---

### Task 3: Replace the camera-slot list with the SVG pitch in `cameras.html`

**Files:**
- Modify: `server/static/cameras.html` (CSS block `server/static/cameras.html:14-94`, body/script `server/static/cameras.html:96-253`)

This is one atomic UI change — the existing `.camera-slot` cards, their CSS, and the JS that builds/polls them are removed together and replaced with the pitch SVG, its CSS, and the JS that renders/polls markers. No automated test exists for this file (no UI test framework in the project); verification is manual, at the end of this task.

- [ ] **Step 1: Replace the camera-slot CSS with pitch + marker + detail-panel CSS**

In `server/static/cameras.html`, replace the block from `.camera-slot {` through the closing of `.camera-slot.slot-busy .lens-buttons { display: none; }` (currently lines 52-93) with:

```css
    .pitch-wrap {
      display: flex;
      justify-content: center;
      background: #14532d;
      border-radius: var(--radius-md);
      padding: 10px;
      box-shadow: var(--shadow-sm);
    }
    #pitch-svg { width: 100%; height: auto; display: block; touch-action: manipulation; }
    .pitch-field { fill: #2f9e44; stroke: #ffffff; stroke-width: 1.5; }
    .pitch-line { stroke: #ffffff; stroke-width: 1.5; fill: none; }

    .pitch-marker { cursor: pointer; }
    .pitch-marker .marker-hit { fill: transparent; }
    .pitch-marker .marker-dot { fill: var(--accent); stroke: #ffffff; stroke-width: 1.5; transition: fill 0.15s ease, stroke-width 0.15s ease; }
    .pitch-marker .marker-label { fill: #ffffff; font-size: 9px; font-weight: 700; text-anchor: middle; pointer-events: none; }
    .pitch-marker.marker-selected .marker-dot { stroke-width: 3; stroke: #fde047; }
    .pitch-marker.marker-busy { cursor: default; }
    .pitch-marker.marker-busy .marker-dot { fill: #64748b; }
    .pitch-marker.marker-busy .marker-label { fill: #cbd5e1; }

    #slot-detail {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 14px 16px;
      margin-top: 12px;
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      box-shadow: var(--shadow-sm);
    }
    #slot-detail[hidden] { display: none; }
    .camera-link-icon {
      flex: 0 0 auto;
      width: 42px;
      height: 42px;
      border-radius: 11px;
      background: var(--accent-soft);
      color: var(--accent);
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .camera-slot-body { min-width: 0; flex: 1; }
    .camera-link-title { font-size: 1rem; font-weight: 800; margin-bottom: 8px; }
    .camera-slot-busy-label { font-size: 0.85rem; font-weight: 700; color: var(--text-muted); }
    .lens-buttons { display: flex; gap: 8px; }
    a.lens-btn {
      flex: 1;
      text-align: center;
      padding: 9px 10px;
      background: var(--accent-soft);
      color: var(--accent);
      text-decoration: none;
      font-size: 0.8rem;
      font-weight: 700;
      border-radius: var(--radius-sm);
      transition: transform 0.12s ease;
    }
    a.lens-btn:active { transform: scale(0.97); }
```

- [ ] **Step 2: Replace the camera-step markup**

In `server/static/cameras.html`, replace the `#camera-step` div (currently lines 120-126):

```html
    <div id="camera-step">
      <label>
        <svg class="icon" viewBox="0 0 24 24"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg>
        Qual câmera você vai usar?
      </label>
      <div id="camera-links"></div>
    </div>
```

with:

```html
    <div id="camera-step">
      <label>
        <svg class="icon" viewBox="0 0 24 24"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg>
        Qual câmera você vai usar?
      </label>
      <div class="pitch-wrap">
        <svg id="pitch-svg" viewBox="0 0 280 180" xmlns="http://www.w3.org/2000/svg">
          <rect class="pitch-field" x="10" y="10" width="260" height="160" rx="6" />
          <line class="pitch-line" x1="140" y1="10" x2="140" y2="170" />
          <circle class="pitch-line" cx="140" cy="90" r="28" />
          <rect class="pitch-line" x="10" y="55" width="28" height="70" />
          <rect class="pitch-line" x="242" y="55" width="28" height="70" />
          <g id="pitch-markers"></g>
        </svg>
      </div>
      <div id="slot-detail" hidden>
        <span class="camera-link-icon">
          <svg class="icon" viewBox="0 0 24 24"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg>
        </span>
        <span class="camera-slot-body">
          <span class="camera-link-title" id="slot-detail-title"></span>
          <span class="camera-slot-busy-label" id="slot-detail-busy" hidden>Em uso</span>
          <span class="lens-buttons" id="slot-detail-lenses">
            <a class="lens-btn" data-facing="environment" href="#">Câmera Traseira</a>
            <a class="lens-btn" data-facing="user" href="#">Câmera Frontal</a>
          </span>
        </span>
      </div>
    </div>
```

- [ ] **Step 3: Replace the SLOTS array, marker rendering, and interaction script**

In `server/static/cameras.html`, replace everything from `const STORAGE_KEY = "managerreplay_operator_name";` through the end of `updateLinks` (currently lines 131-177) with:

```javascript
    const STORAGE_KEY = "managerreplay_operator_name";
    const SLOTS = [
      { id: 1, label: "Gol Esquerdo", abbr: "Gol E", x: 24, y: 90 },
      { id: 2, label: "Gol Direito", abbr: "Gol D", x: 256, y: 90 },
      { id: 3, label: "Arquibancada Esquerda", abbr: "Arq. E", x: 140, y: 20 },
      { id: 4, label: "Arquibancada Direita", abbr: "Arq. D", x: 140, y: 160 },
      { id: 5, label: "Geral", abbr: "Geral", x: 140, y: 90 },
    ];
    const POLL_INTERVAL_MS = 3000;
    const SVG_NS = "http://www.w3.org/2000/svg";

    const nameInput = document.getElementById("name-input");
    const cameraStep = document.getElementById("camera-step");
    const markersGroup = document.getElementById("pitch-markers");
    const slotDetail = document.getElementById("slot-detail");
    const slotDetailTitle = document.getElementById("slot-detail-title");
    const slotDetailBusy = document.getElementById("slot-detail-busy");
    const slotDetailLenses = document.getElementById("slot-detail-lenses");

    function svgEl(tag, attrs) {
      const el = document.createElementNS(SVG_NS, tag);
      Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, value));
      return el;
    }

    const cameraMarkers = {};
    SLOTS.forEach((slot) => {
      const g = svgEl("g", { class: "pitch-marker", "data-camera-id": slot.id });
      g.appendChild(svgEl("circle", { class: "marker-hit", cx: slot.x, cy: slot.y, r: 16 }));
      g.appendChild(svgEl("circle", { class: "marker-dot", cx: slot.x, cy: slot.y, r: 10 }));
      g.appendChild(svgEl("text", { class: "marker-label", x: slot.x, y: slot.y + 22 })).textContent = slot.abbr;
      markersGroup.appendChild(g);
      cameraMarkers[slot.id] = { group: g, busy: false };
    });

    let selectedCameraId = null;

    function selectSlot(cameraId) {
      const slot = SLOTS.find((s) => s.id === cameraId);
      const marker = cameraMarkers[cameraId];
      if (!slot || !marker || marker.busy) return;

      if (selectedCameraId !== null && cameraMarkers[selectedCameraId]) {
        cameraMarkers[selectedCameraId].group.classList.remove("marker-selected");
      }
      selectedCameraId = cameraId;
      marker.group.classList.add("marker-selected");

      slotDetailTitle.textContent = slot.label;
      slotDetailBusy.hidden = true;
      slotDetailLenses.hidden = false;
      const encodedName = encodeURIComponent(nameInput.value.trim());
      slotDetailLenses.querySelectorAll("a.lens-btn").forEach((btn) => {
        btn.href = `capture.html?mode=chunks&camera=${cameraId}&facing=${btn.dataset.facing}&name=${encodedName}`;
      });
      slotDetail.hidden = false;
    }

    markersGroup.addEventListener("click", (event) => {
      const g = event.target.closest(".pitch-marker");
      if (!g) return;
      selectSlot(Number(g.dataset.cameraId));
    });

    function updateLinks(name) {
      if (selectedCameraId === null) return;
      selectSlot(selectedCameraId);
    }
```

(`updateLinks` is kept as a thin wrapper so the rest of the file — which calls `updateLinks(name)` on every keystroke — keeps working without further changes: it just re-runs `selectSlot` to refresh the `name=` query param on the currently selected slot's lens links, and does nothing if nothing is selected yet.)

- [ ] **Step 4: Update the busy-slot polling to toggle marker state instead of card state**

In `server/static/cameras.html`, replace `refreshBusySlots` (currently inside the block that starts with `async function refreshBusySlots()`):

```javascript
    async function refreshBusySlots() {
      let busyCameraIds = [];
      try {
        const res = await fetch("/recording-status");
        const sessions = await res.json();
        busyCameraIds = sessions.map((s) => s.camera);
      } catch (err) {
        // Falha de rede no poll: assume "nenhum slot ocupado conhecido" em
        // vez de travar a escolha — o backend continua sendo a fonte da
        // verdade por camera_id de qualquer forma.
        busyCameraIds = [];
      }
      SLOTS.forEach((slot) => {
        const marker = cameraMarkers[slot.id];
        const busy = busyCameraIds.includes(slot.id);
        marker.busy = busy;
        marker.group.classList.toggle("marker-busy", busy);
        if (busy && selectedCameraId === slot.id) {
          marker.group.classList.remove("marker-selected");
          selectedCameraId = null;
          slotDetail.hidden = true;
        }
      });
    }
```

- [ ] **Step 5: Verify the rest of the file still fits (no further edits needed)**

The remaining code (`startPolling`, `stopPolling`, `onNameChange`, `nameInput.addEventListener`, `guessDeviceModel`, the `savedName`/`guessed` bootstrap at the bottom) references `cameraStep`, `updateLinks(name)`, `startPolling()`, `stopPolling()` — all of which still exist with the same names after Steps 3-4, so no change needed there. Read through `server/static/cameras.html` once after applying Steps 1-4 to confirm no leftover reference to the removed `cameraLinksEl`, `cameraSlots`, or `.camera-slot` — those were only used inside the code just replaced.

- [ ] **Step 6: Manual verification**

Serve the app locally (see README's "Rodando os testes" / local dev instructions — or open `server/static/cameras.html` directly with the rest of `server/static/` reachable) and in a browser:
1. Open `cameras.html`, type a name — the pitch SVG appears with 5 markers positioned as: two at the left/right edges (Gol Esquerdo/Direito), two at top/bottom center (Arquibancada Esquerda/Direita), one dead center (Geral).
2. Tap a free marker — it gets a yellow selection ring, and the panel below shows its full label plus "Câmera Traseira"/"Câmera Frontal" buttons with working `href`s.
3. Tap a different marker — the panel updates to the new slot, old marker loses its ring.
4. With no local multi-device setup, simulate a busy slot by starting a recording from `capture.html?mode=chunks&camera=1&facing=environment&name=Teste` in one tab, then reload `cameras.html` in another — marker 1 should render grey and unresponsive to taps within ~3s.

If no local HTTPS/dev setup is readily available in this environment, at minimum verify by static inspection: every `id`/`class` referenced in the Step 3-4 JavaScript exists in the Step 2 HTML, and `SLOTS` ids (1-5) match `gravando.html`'s `CAMERA_LABELS` keys from Task 1.

- [ ] **Step 7: Commit**

```bash
git add server/static/cameras.html
git commit -m "Substitui lista de câmeras por campo de futebol com 5 posições"
```

---

### Task 4: Document the 5-camera deploy step

**Files:**
- Modify: `README.md` (wherever `--cameras` is mentioned, e.g. the "Deploy no Raspberry Pi" example command)

- [ ] **Step 1: Update the example `app.py` invocation to mention the new max**

In `README.md`, find the line showing the manual server-start example (`--cameras=1` in the "Subir o servidor" step). Leave the example value as-is (it's illustrative, not prescriptive) but add a short note right after the code block:

```markdown
`--cameras` aceita de 1 a 5 — cada número corresponde a uma posição fixa no campo mostrado em `cameras.html` (1=Gol Esquerdo, 2=Gol Direito, 3=Arquibancada Esquerda, 4=Arquibancada Direita, 5=Geral).
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "Documenta as 5 posições de câmera no README"
```
