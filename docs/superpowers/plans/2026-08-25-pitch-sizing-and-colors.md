# Ajustes de tamanho e cor no campo de câmeras — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cap the pitch SVG's width on large screens and color-code its markers by side (blue for the left pair, red for the right pair, black-and-yellow "referee" for Geral).

**Architecture:** Pure CSS/JS tweaks to the pitch introduced in the previous feature — a `max-width` on `.pitch-wrap`, a `side` field added to each entry in `SLOTS`, and per-side CSS classes applied to each marker `<g>` at creation time. No HTML structure or interaction logic changes.

**Tech Stack:** Plain HTML/CSS/JS, same file as before (`server/static/cameras.html`).

---

### Task 1: Cap pitch width and add side-based marker colors

**Files:**
- Modify: `server/static/cameras.html`

- [ ] **Step 1: Add `max-width` to `.pitch-wrap`**

Find the `.pitch-wrap` rule (added in the previous feature) and add a max-width, centered:

```css
    .pitch-wrap {
      display: flex;
      justify-content: center;
      background: #14532d;
      border-radius: var(--radius-md);
      padding: 10px;
      box-shadow: var(--shadow-sm);
      max-width: 480px;
      margin: 0 auto;
    }
```

(Only the two new lines — `max-width: 480px;` and `margin: 0 auto;` — are added; the rest of the rule is unchanged.)

- [ ] **Step 2: Add side-color CSS rules, ordered before the busy/selected overrides**

Immediately after the existing `.pitch-marker .marker-label { ... }` rule and before `.pitch-marker.marker-selected .marker-dot { ... }`, insert:

```css
    .pitch-marker.marker-side-a .marker-dot { fill: #2563eb; }
    .pitch-marker.marker-side-b .marker-dot { fill: #dc2626; }
    .pitch-marker.marker-side-judge .marker-dot { fill: #111827; stroke: #facc15; }
```

This ordering matters: `.marker-busy`/`.marker-selected` rules have the same CSS specificity as these new side rules (three classes each), so whichever comes later in the file wins when a marker has both classes at once (e.g. a busy Lado A marker must show grey, not blue) — placing the side rules first and leaving the existing selected/busy rules after them preserves that.

- [ ] **Step 3: Add a `side` field to each `SLOTS` entry**

In the `SLOTS` array, add `side: "a" | "b" | "judge"` to each entry:

```javascript
    const SLOTS = [
      { id: 1, label: "Gol Esquerdo", abbr: "Gol E", x: 24, y: 90, side: "a" },
      { id: 2, label: "Gol Direito", abbr: "Gol D", x: 256, y: 90, side: "b" },
      { id: 3, label: "Arquibancada Esquerda", abbr: "Arq. E", x: 140, y: 20, side: "a" },
      { id: 4, label: "Arquibancada Direita", abbr: "Arq. D", x: 140, y: 160, side: "b" },
      { id: 5, label: "Geral", abbr: "Geral", x: 140, y: 90, side: "judge" },
    ];
```

- [ ] **Step 4: Apply the side class when building each marker**

In the `SLOTS.forEach` block that builds marker `<g>` elements, add `marker-side-${slot.side}` to the group's class list:

```javascript
    SLOTS.forEach((slot) => {
      const g = svgEl("g", { class: `pitch-marker marker-side-${slot.side}`, "data-camera-id": slot.id });
      g.appendChild(svgEl("circle", { class: "marker-hit", cx: slot.x, cy: slot.y, r: 16 }));
      g.appendChild(svgEl("circle", { class: "marker-dot", cx: slot.x, cy: slot.y, r: 10 }));
      g.appendChild(svgEl("text", { class: "marker-label", x: slot.x, y: slot.y + 22 })).textContent = slot.abbr;
      markersGroup.appendChild(g);
      cameraMarkers[slot.id] = { group: g, busy: false };
    });
```

(This is the same block as before — only the `class` value on the first line changes, from `"pitch-marker"` to the template string above. All later code that does `classList.add`/`classList.remove`/`classList.toggle` for `marker-busy`/`marker-selected` keeps working unchanged since those are separate class tokens on the same element.)

- [ ] **Step 5: Verify — JS syntax and consistency check**

```bash
python3 -c "
import re
content = open('server/static/cameras.html').read()
m = re.search(r'<script>(.*)</script>', content, re.S)
open('/tmp/cameras_check.js', 'w').write(m.group(1))
"
node --check /tmp/cameras_check.js && echo "JS syntax OK"
grep -c 'marker-side-a\|marker-side-b\|marker-side-judge' server/static/cameras.html
```
Expected: `JS syntax OK`, and the grep count should be 6 (3 CSS rules + 3 usages via the template string... actually the template string only appears once in JS, so expect the literal strings `marker-side-a`, `marker-side-b`, `marker-side-judge` each exactly once in CSS — confirm with `grep -n` that all three CSS color rules are present).

Then manually confirm each `SLOTS` entry has a `side` field matching Lado A (1, 3), Lado B (2, 4), judge (5) — matching the design: Gol Esquerdo/Arquibancada Esquerda = azul, Gol Direito/Arquibancada Direita = vermelho, Geral = preto/amarelo.

No live-browser verification available in this environment (same limitation as the rest of this file); rely on the static checks above plus visual inspection of the coordinates/colors against the design.

- [ ] **Step 6: Commit**

```bash
git add server/static/cameras.html
git commit -m "Trava largura máxima do campo e colore marcadores por lado"
```
