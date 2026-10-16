# PhDF — Project Handoff & Roadmap

> Status: **Phase 5.7 done (v0.5.7)** — GitHub repo not created yet. Ask the owner before starting each new phase.
> Last updated: 2026-10-15
> Original requirements: `notes.md`

---

## 1. Vision

PhDF is a **lightweight, reader-first, cross-platform PDF app** for heavy readers (research, study) that:
- remembers exactly where you were in every PDF,
- lives next to your Markdown notes (built-in MD reader/editor + Obsidian bridge),
- turns anything into text (OCR) and gets text out fast (send to Obsidian, 1-click export to `.md`),
- offers reading aids (focus / "ADHD mode"),
- has a terminal-based AI side panel (Claude Code / Codex).

**Non-goals (for now):** full PDF authoring, form design, digital signatures, heavy page editing.

---

## 2. Requirements (from `notes.md`, normalized)

| # | Requirement | Priority |
|---|---|---|
| R1 | Lightweight: small install, fast startup, low RAM | Must |
| R2 | Remember position (page, zoom, scroll) per PDF across sessions | Must |
| R3 | Markdown reader + editor, openable side-by-side with a PDF | Must |
| R4 | Annotations: highlight, underline, sticky notes, free text, ink | Must |
| R5 | Easy navigation: outline/TOC, thumbnails, search, go-to-page, back/forward | Must |
| R6 | OCR for scanned PDFs (selectable/searchable text) | Should |
| R7 | Obsidian integration: send selection/quote to the vault/note | Must |
| R8 | 1-click export PDF → `.md` (text + highlights/notes) | Should |
| R9 | MD-first secondary mode with reading aids ("ADHD mode") | Should |
| R10 | AI sidebar: Claude Code / Codex through an embedded terminal | Could |
| R11 | Link peek: clicking a link opens a small preview first → *expand*, *open here*, or *close* | Must |

---

## 3. Final Decisions & Rationale (Decision Log)

| # | Decision | Why | Alternatives considered |
|---|---|---|---|
| D1 | **Python backend + pywebview frontend** (option "B") | Owner prefers Python. pywebview uses the OS's built-in webview (WebView2 / WebKit / GTK WebKit), so no bundled Chromium → stays light (~40–60 MB install). Web UI makes CodeMirror, xterm.js, popups, overlays and side panels easy. | **A) PySide6/Qt** — fully native Python, but CodeMirror/xterm would need QtWebEngine (+~150 MB Chromium) or a primitive Qt editor. **C) Tauri + PDF.js** — lightest, but no Python and loses MuPDF strengths. |
| D2 | **PDF engine: PyMuPDF (MuPDF)**, behind an abstraction layer | Fast native C rendering, best fidelity on complex/scanned PDFs, rich text extraction (blocks/lines/fonts/positions), built-in Tesseract OCR hooks, full annotation read/write, `pymupdf4llm` for high-quality Markdown export. Most of our key features (OCR, export, notes) are exactly MuPDF's strengths. | **PDF.js** — free text layer, but slower on big files, weak extraction, limited annotation writing, no OCR. **PDFium** (`pypdfium2`, BSD/Apache) — kept as the **fallback engine** if licensing ever requires it. |
| D3 | **Engine abstraction (`PdfEngine` interface)** | MuPDF is AGPL. If PhDF is ever sold closed-source, we can swap to PDFium (or buy an Artifex license) without rewriting the app. "Worst case we swap the engine." | Direct MuPDF calls everywhere (faster to write, locks us in). |
| D4 | **License: AGPL-3.0, open source on GitHub** | Required by MuPDF anyway; free to use. Selling is still allowed under AGPL (source stays open). | MIT/Apache — only possible with a non-AGPL engine. |
| D5 | **CLA (Contributor License Agreement) for outside contributors** | Keeps the owner's right to relicense later (e.g. dual-license or closed-source commercial edition). Without it, every contributor must agree to a license change. | No CLA (simpler, but blocks future relicensing). |
| D6 | **Markdown editor: CodeMirror 6** | Obsidian itself uses CodeMirror 6 → same feel (live preview, wikilinks, callouts). Lightweight, extensible. | textarea + preview (too basic), Milkdown/TipTap (WYSIWYG, Obsidian syntax painful), Monaco (too heavy). |
| D7 | **AI integration: terminal-based** (xterm.js + PTY) | Reuses the user's installed `claude` / `codex` CLIs and their own auth; PhDF stores no API keys; zero vendor lock-in. | Direct API integration (needs key management, more code). |
| D8 | **Platforms: Windows + macOS + Linux** | Every chosen component is cross-platform. Windows is the primary dev platform; GitHub Actions builds all three from Phase 0. macOS/Linux marked "experimental" until end of Phase 1. | Windows-only (simpler, but harder to add later). |
| D9 | **OCR: Tesseract engine built into MuPDF** (see D19) | Works on all three OSes, supports many languages incl. Turkish. | Windows.Media.Ocr (Windows-only); a system Tesseract install. |
| D10 | **State store: SQLite** in the per-user app-data dir | Built into Python, zero setup, reliable. Stores positions, recent files, settings, annotation index. | JSON files (fragile under concurrency/growth). |
| D11 | **Document identity = content hash**, not path | Position memory survives renames and moves. | Path-based keys (break on move). |
| D12 | **Annotations written into the PDF** (standard annotations) + index in SQLite | Other PDF readers can see them; index enables fast search/list. | Sidecar-only (invisible to other apps). |
| D13 | **Release model: phased, incremental packages** | Ship each phase as a versioned release; new phases can be added along the way. | Big-bang release. |
| D14 | **Frontend framework: Svelte 5 + TypeScript (Vite)** | PhDF has many interactive, stateful parts (tabs, sidebar, annotation list, MD editor, terminal, link peek, reading modes, settings). Svelte's reactivity keeps that manageable while adding only ~5–10 KB (compiled to plain JS). CodeMirror 6 and xterm.js integrate directly. | **Vanilla TS** — smallest, but manual DOM/state syncing gets messy as UI grows. **React** — bigger runtime and steeper learning curve. |
| D15 | **macOS-inspired UI** (owner preference) | Translucent unified toolbar with centered title/subtitle, SF/Segoe UI Variable font stack, system blue accent, segmented controls, inset grouped lists, thin overlay scrollbars, light/dark from OS. Tokens live in `frontend/src/app.css`. No engine name shown in the UI. | Windows/Fluent look; plain default styling. |
| D16 | **Annotations are saved with Ctrl+S** (owner) | Classic PDF-app behaviour: edits live in memory, the tab shows a dot and the title “— Edited”; closing asks Save / Don’t Save / Cancel; closing a window with unsaved changes asks too (pywebview `confirm_close`). Saving is incremental (appends to the file). | Autosave into the file; never touching the PDF. |
| D17 | **Integrated note = `<pdf name>.md` next to the PDF** (owner) | One note per PDF, opened inside the same tab beside the PDF. An existing .md can be linked instead (stored in `md_links`). Notes autosave (debounced), and reload when changed on disk. Obsidian vault support comes in the next phase. | A central notes folder. |
| D18 | **Pin format** `⎘ phdf · p.12 · §2.1 · #k7q2` + `> “quote”` (owner) | Distinctive, readable in any editor, one line to parse. The id is the PDF annotation's `/NM`, so a pin finds its exact highlight; page (+ quote) are the fallback. Links are two-way: pin → PDF highlight, highlight → pin. | Obsidian callout + hidden comment; fenced ```phdf block. |
| D19 | **OCR needs no Tesseract install** | PyMuPDF ships MuPDF's Tesseract engine; only `*.traineddata` files are needed. PhDF downloads them on first use (tessdata_fast, ~4 MB each) into its data folder; a system Tesseract's files are reused if present. Recognized words are written as invisible text into the page (an unsaved change, Ctrl+S), so the PDF becomes searchable everywhere. | Installing Tesseract (needs admin; the winget attempt was cancelled at the UAC prompt). |
| D20 | **Obsidian v1 = copies, not sync** (owner) | “Send to Obsidian” appends pin + quote to `<vault>/<folder>/<book title>.md`; integrated notes stay next to the PDF, and “Copy Note to Obsidian” writes a copy (asks before replacing). Two-way sync between the integrated note and its vault copy is a later phase. | Moving integrated notes into the vault. |
| D21 | **Parking lot lives next to the document** (owner) | Parked thoughts belong to the book being read and should be seen with its note, not in Obsidian: `<name>.parking.md` beside `<name>.pdf` / `<name>.md`, shown as a Parking tab in the note panel. | One list in the Obsidian vault (Phase 4 behaviour). |

### Open source → selling later: how it works
- AGPL itself costs nothing.
- Selling under AGPL is allowed (e.g. paid installers, support, hosted features) as long as source remains available.
- For a **closed-source** commercial edition: either swap the engine to PDFium (D3) or buy a commercial MuPDF license from Artifex (price on request, not public).
- The CLA (D5) ensures the owner can relicense their own code.

---

## 4. Architecture

```
┌──────────────────────── pywebview window ────────────────────────┐
│  Frontend (HTML/CSS/TypeScript, bundled with Vite)               │
│  ┌──────────┐ ┌───────────────────────┐ ┌──────────────────────┐ │
│  │ Sidebar  │ │ PDF view              │ │ Side panel           │ │
│  │ TOC,     │ │ page images +         │ │ • MD editor (CM6)    │ │
│  │ thumbs,  │ │ text layer +          │ │ • Annotations list   │ │
│  │ search   │ │ annotation layer      │ │ • Terminal (xterm.js)│ │
│  └──────────┘ └───────────────────────┘ └──────────────────────┘ │
└──────────────────────────────▲───────────────────────────────────┘
                               │ pywebview JS↔Python bridge
┌──────────────────────────────┴───────────────────────────────────┐
│  Python backend                                                  │
│  • PdfEngine interface → MuPdfEngine (default) / PdfiumEngine    │
│  • Render service (page → PNG/WebP at zoom, LRU cache)           │
│  • Text service (words + bboxes for selectable text layer)       │
│  • Annotation service (write to PDF + SQLite index)              │
│  • OCR service (Tesseract, background thread, per-page cache)    │
│  • Export service (pymupdf4llm → .md + notes)                    │
│  • Session store (SQLite, content-hash keys)                     │
│  • Obsidian bridge (vault write / obsidian:// URI / REST API)    │
│  • PTY service (pywinpty on Windows, ptyprocess on Unix)         │
└──────────────────────────────────────────────────────────────────┘
```

**Rendering approach:** PyMuPDF renders pages to images; the frontend overlays an invisible, positioned **text layer** (from word bounding boxes) for selection/copy/search highlights, plus an **annotation layer**. Pages are virtualized (only visible ± a few are rendered), with an LRU cache and resolution re-render on zoom.

### Proposed repo layout
```
projectPDF/                # repo root
  backend/phdf/
    app.py                 # pywebview entry point (`uv run phdf`)
    api.py                 # methods exposed to JS as window.pywebview.api.*
    paths.py               # per-OS data dir, bundled frontend location
    docid.py               # content-hash document identity (D11)
    engine/                # PdfEngine interface (base.py) + MuPDF impl (mupdf.py)
    db/store.py            # SQLite: settings, documents/positions, append-only migrations
    services/render_server.py  # local HTTP server streaming page PNGs to <img> tags
                           # engine: annotations (add/update/delete, /NM ids), incremental save
                           # api.py: Core (shared docs/store/render) + Api (one per window)
    services/              # annots, ocr, export, obsidian, pty — added per phase
  frontend/
    src/App.svelte         # shell: toolbar, tabs, sidebar, shortcuts, session restore
    src/lib/api.ts         # typed wrapper for the Python API + page image URLs
    src/lib/tab.svelte.ts  # per-tab state: position, history, search, text/link caches
    src/lib/viewer/        # Viewer (virtualized scroll, zoom/fit) + PageView (image, text, links)
    src/lib/workspace.svelte.ts  # panes (max 3) and their tabs: move / split / prune
    src/lib/dnd.svelte.ts  # pointer-based tab drag & drop + drop-target hit testing
    src/lib/annot/         # SelectionMenu, AnnotEditor, AnnotationsPanel, Popover, colours
    src/lib/md/            # MdEditor (CodeMirror 6, pins as cards) + markdown-it preview
    src/lib/md.svelte.ts   # MdDoc: load / autosave / reload-on-change for a .md file
    src/lib/pin.ts         # pin format: parse, format, block, section label
    src/lib/*.svelte       # PaneView, Sidebar, OutlineNode, TabBar, Welcome, LinkPeek, Icon
  tests/                   # pytest (engine, store, docid)
  .github/workflows/ci.yml # lint/test/package matrix: windows, macos, linux
  phdf.spec                # PyInstaller spec
  pyproject.toml, LICENSE (AGPL-3.0), CLA.md, README.md
```

### Tooling
- Python 3.12+, `uv` for env/deps, `ruff` (lint/format), `pytest`
- Frontend: Svelte 5 + TypeScript + Vite (D14)
- Packaging: PyInstaller (one build per OS via GitHub Actions)

---

## 5. Feature Design Notes

### R2 — Session memory
- Key: SHA-256 of (first 1 MB + file size) → robust to rename/move.
- Store: page, scroll offset, zoom, view mode, last opened, open panels.
- Optional: restore all open tabs at startup.

### R11 — Link peek
- **Internal links** (same PDF): floating mini-render of the target. Buttons: `Go there` · `Open as split` · `✕`.
- **External URLs**: small secondary pywebview window with top bar: `Maximize` · `Open in browser` · `✕`.
- Back/forward history so jumps never lose your place.

### R7 — Obsidian bridge (by effort)
1. **Direct vault write**: configure vault path → append to inbox note / daily note / chosen note.
2. **`obsidian://` URI**: no plugin needed.
3. **Local REST API plugin**: target the *currently open* note.
4. (Later) `phdf://open?file=…&page=…` deep links back from Obsidian.
- Quote template (configurable): `> text` + `— [[Book Title]], p. 12`.

### R8 — Export to Markdown
- `pymupdf4llm` for body text (headings, lists, tables) + appended highlights/notes with page refs.
- Optional later: external tools (`marker`, `docling`) if installed.

### R9 — MD mode & reading aids
- Focus line / reading ruler, dim non-current paragraphs, bionic-style bolding toggle.
- Adjustable line width/spacing, dyslexia-friendly font, reading timer, progress bar.
- Ruler/dim overlays also usable in PDF mode.

### R10 — AI terminal
- Embedded terminal running `claude` / `codex` in a chosen working dir (vault or PhDF workspace).
- "Send to AI": puts selection + page ref + file path into the prompt (or a temp context file).

---

## 6. Roadmap (each phase = a versioned release)

### Phase 0 — Foundations → `v0.0.x`
- [x] Local git repo, AGPL-3.0 `LICENSE`, `CLA.md`, README
- [ ] Create the GitHub repo and push (needs `gh` CLI or web UI) — CI has never run yet
- [x] Python project (`uv`, `ruff`, `pytest`), frontend (Vite + Svelte 5 + TS)
- [x] pywebview window + JS↔Python bridge (verified end-to-end in a real window)
- [x] `PdfEngine` interface + `MuPdfEngine` (info, page size, render, outline)
- [x] SQLite schema + settings + document positions/recents
- [x] GitHub Actions workflow + PyInstaller spec (Windows build verified locally: 70 MB folder, ~31 MB zipped)

### Phase 0.1 — Polish → `v0.0.2`
- [x] Remove engine name ("mupdf") from the UI
- [x] macOS-style UI: translucent toolbar, centered title + "Page X of Y", segmented page
      controls, welcome screen with app icon and "Recents" card, Ctrl/Cmd+O shortcut, Home button
- [x] `.gitignore` hardened (`.env*`, venvs, OS files) + `.env.example` + `.env` loader
      (`backend/phdf/env.py`, real env vars win, ignored in packaged builds)
- [ ] (Later) frameless window with Mac-style traffic-light buttons — needs custom drag/resize
      handling per OS, so deferred

### Phase 1 — Core Reader (MVP) → `v0.1`
- [x] Open PDF, continuous virtualized rendering (only pages near the viewport load), zoom
      (buttons, Ctrl±, Ctrl+wheel) & fit modes (width / page / actual size)
- [x] Selectable text layer (copy works, line breaks preserved), in-document search with
      highlights and n/N stepping
- [x] Outline/TOC tree, page thumbnails, go-to-page (click "Page X of Y" or Ctrl+G), back/forward
- [x] **Session memory (R2)**: page + offset within page + zoom + fit per document; open tabs,
      active tab and sidebar restored at startup
- [x] **Link peek (R11)**: internal links → small card with a clip of the target (Enlarge /
      Go to Page / close); web links → small floating window right away, card offers Enlarge
      (maximize) / Open in Browser / Copy Link / close
- [x] Tabs (Ctrl+T/W/Tab), recents on the new-tab page, dark pages toggle (inverted rendering)
- [ ] macOS/Linux promoted from experimental to supported — needs CI runs first
- Not yet: "open link target as split view", rotated-text support in the text layer,
  multi-threaded rendering, password-protected PDFs (open fails with an error toast)

### Phase 1.1 — Tabs & Split View → `v0.1.1`
- [x] Drag tabs to reorder (insertion marker in the tab bar)
- [x] Side-by-side panes (max 3): drag a tab onto the left/right 30% of a pane to split; onto
      the middle or another tab bar to move it; empty panes close; dividers are resizable
- [x] Drag a tab outside the window → it opens in a new window
- [x] Multi-window backend: one `Api` per window over a shared `Core`; documents are
      reference-counted across windows; each window has its own session (`session.<windowId>`);
      closing one of several windows discards its tabs, the last window's session is restored
- Not yet: dragging a tab *between* two existing windows; "open link target as split"
  (now trivial with panes — see Phase 1 leftovers)

### Phase 2 — Notes & Markdown → `v0.2.0`
- [x] Select text → floating menu: highlight (5 colours), underline, strikethrough, Note in MD, copy
- [x] Sticky note and free-text tools (click on the page); click any annotation to recolour,
      comment, delete or jump to its note
- [x] Save with Ctrl+S (D16): “— Edited” + tab dot, Save/Don’t Save/Cancel on close, window
      close guard; incremental save; doc ids aliased after a save so open tabs keep working
- [x] Annotations panel sliding in from the right of the PDF: grouped by page, search, filter by
      marks/notes and colour, click to jump, delete; shows which ones have a note pin
- [x] Integrated .md in the same tab (D17), resizable; “Link an existing .md” (import)
- [x] Pins (D18): “Note in MD” adds a highlight + pin + quote and puts the cursor under it;
      pin → PDF (“Go to PDF ↗” or Ctrl+click) and highlight → pin, both ways
- [x] Standalone Markdown tabs (open .md with Ctrl+O, “New Note…”); CodeMirror 6 with heading
      styles, Edit/Preview (markdown-it, HTML escaped); pins in a standalone note open its PDF
- [x] Editor is lazy-loaded: initial JS ~107 KB, the editor chunk loads on first note
- Not yet: undo/redo for annotations, ink/freehand (Phase 3), live-preview editing like Obsidian

### Phase 2.1 — Fixes from manual testing → `v0.2.x`
- [x] “Don't Save” then reopen showed the discarded highlight (cached page image): page
      revisions are bumped when a document is reopened
- [x] Window close asks with the app's own Save / Don't Save / Cancel sheet (per unsaved PDF)
      instead of a system message box (`closing` event held by the backend)
- [x] Narrowing a pane (divider / sidebar) no longer re-fits the page: the zoom stays and the
      page is cropped on the side that moved; only a window resize re-fits

### Phase 3 — Obsidian & Text Power → `v0.3.0`
- [x] **Obsidian bridge v1** (D20): Settings → vault + folder; selection menu “Send to Obsidian”
      (highlight + pin + quote into the book's vault note, toast with “Open” via `obsidian://`);
      More → “Copy Note to Obsidian”
- [x] **OCR** (R6, D19): “This page has no text” bar → Recognize Text / All N Pages, progress +
      Stop; More → Recognize Text; Settings → languages (download on demand)
- [x] **1-click export to .md** (R8): More → “Export as Markdown…” / “Export to Obsidian Vault”;
      pymupdf4llm text (headings, lists, tables) + an Annotations section with pins
- [x] **Ink** annotations: draw tool (pen), live stroke, recolour/delete like other annotations
- [x] More (⋯) menu and Settings sheet; one toast system with an optional action button
- Not yet: two-way sync of integrated note ↔ vault copy (later phase), ink colour/width picker,
  OCR of a selected area only

### Phase 3.1 — Big documents & link peek → `v0.3.1`
Measured with a 218 MB / 655-page scanned-photo textbook (working sets of PhDF + WebView2):
open → first page 2.8 s → **0.9 s**; scrolling 76 pages peaked 1318 MB → **948 MB**; after
closing it 1029 MB → **545 MB** (= empty app).
- [x] No full “pages without text” scan on open (it took 1.9 s and held the doc lock); text is
      checked per viewed page, the full scan runs only for “All Pages Without Text”
- [x] Only pages around the viewport are mounted (was one component per page); live range
      narrowed to ½ viewport above / 1½ below; one shared canvas for text measuring
- [x] Page images: photo-heavy pages (>50 % image area) are served as JPEG (7.3 MB PNG → 1 MB),
      text pages stay PNG; `Cache-Control: no-store` + a 64 MB LRU in the render server instead of
      the browser cache; a closed document's images are dropped
- [x] MuPDF store emptied every 4 renders and when no document is open (PyMuPDF can't read
      its size); WebView2 `MemoryUsageTargetLevel` Low→Normal after closing a document
- [x] Link peek: real page view (zoom −/+ / Ctrl+wheel / Ctrl±), drag to pan, “T” toggles
      text selection (Ctrl+C), in both the small card and the enlarged sheet
- Remaining baseline: WebView2 itself is ~400 MB working set (Chromium processes)

### Phase 4 — Read Mode, Focus & Parking Lot → `v0.4.0`
Scope chosen by the owner (an "ADHD-friendly" set, each part optional):
- [x] **Read** pull-down (toolbar, top left) — each item on its own: reading ruler (band follows
      the pointer, S/M/L), zen mode (hide toolbar/tabs/sidebar; Ctrl+. or Esc), full screen
      (F11), page tint (cream / blue / green / gray, multiply blend)
- [x] **Focus** pull-down: small pomodoro (15/25/45/50 min, break, chime, clock in the toolbar)
      and time left for the chapter (top-level outline entry) and the whole document, from a
      learned reading pace (EMA of 8 s–15 min page turns)
- [x] **Parking lot** (lightbulb button, Ctrl+Shift+Space): park a stray thought with Enter and
      go straight back; saved as a Markdown task list with book + page + time; tick items off
      (storage changed in 4.1, see D21)
- [x] Markdown editor typography (“Aa”): System, Inter, Literata, Atkinson Hyperlegible,
      JetBrains Mono (bundled, OFL, loaded on first use) + size, line spacing, letter spacing,
      text width; shared by editor and preview, remembered
- [x] “Export as Markdown” is now only the converted text (notes stay in the .md note)
- [x] Delete / Backspace removes the selected annotation
- Not wanted (owner): reflow reading view, bionic reading, text-to-speech, reading prompts

### Phase 4.1 — Owner feedback → `v0.4.1`
- [x] **Parking lot per document, not in Obsidian (D21)**: `<name>.parking.md` next to the PDF
      (beside its integrated `<name>.md`); the note panel has **Note | Parking** tabs with an
      open-items badge; “Show All” in the parking popover opens that tab. Standalone notes get
      their own list next to them; with nothing open → PhDF's data folder.
- [x] **Narrow windows: toolbar items overlap** (e.g. the title runs over the annotation tool
      buttons). Fixed: grid `auto | minmax(0,1fr) | auto` so the title truncates instead of
      overlapping; container queries collapse Read/Focus labels (≤1280), annotation tools
      (≤1020) and zoom + dark pages (≤860) into the ⋯ menu, search to an icon (≤720), back /
      forward (≤600). The note panel header shrinks the same way. Verified at 1400–650 px.
- [x] **Focus pace must ignore fast scrolling**: only count time on a page as reading when the
      reader actually dwelt there. Detect skimming/scrolling (scroll velocity, pages passed per
      second, page visible < N s, window not focused / idle) and exclude those intervals; count
      dwell time per page while it is the main visible page and the user is active.
      Done: dwell seconds tick only with focus + input in the last 90 s; moving > 1.2 pages within
      1.5 s (incl. a single jump) is skimming and wipes the dwell; a sample needs a ±1 page turn
      and 8 s–10 min of dwell. Verified: a 12-page fling adds 0 samples, a real read adds 1.

### Phase 5 — AI terminal → `v0.5.0`
- [x] **Embedded terminal** (xterm.js + PTY: pywinpty on Windows, ptyprocess elsewhere) running
      the user's shell (PowerShell on Windows, `$SHELL` elsewhere) **in the active PDF's folder**.
      No AI is auto-started: the user types `claude` / `codex` (both installed: Claude Code 2.1,
      codex-cli 0.161). PhDF stores no API keys.
- [x] **Modular, MATLAB-style docking**: default docked in the right column **above the note**
      (Note | Parking), with a draggable splitter; drag its header (or a button) to dock it at the
      **bottom** of the window instead, and back. Works like a drawer: drag down to any size,
      down to a thin header strip; click the header to collapse/expand. Dock place and sizes are
      remembered. Moving/collapsing never restarts the shell (one persistent xterm per window,
      re-parented between docks).
- [x] **Ask AI** in the selection menu: presets (Explain, Summarize, Translate to Turkish) paste
      the quote + book title + page + PDF path into the terminal **and send it**; “My own
      question…” pastes the same context **without** pressing Enter. Uses bracketed paste so
      multi-line text doesn't submit early. **Guard:** if no `claude`/`codex` process runs in the
      shell (psutil, child processes), nothing is pasted — a toast offers *Claude* / *Codex*,
      starts it, waits until it runs, then sends. (Pasting into plain PowerShell would execute
      the quote as commands.)
- [x] **How to use PhDF** sheet (“?” button in the toolbar and on the welcome page): one card
      per feature + shortcut table
- Implementation: `services/terminal.py` (session + reader thread, long-poll `term_read`),
  `lib/ai/terminal.svelte.ts` (singleton xterm re-parented between docks, layout persisted as
  `terminal.layout`), `lib/ai/AiPanel.svelte`; app shortcuts are ignored while the terminal has
  focus (except Ctrl+` to toggle). Verified with a real PowerShell and a fake `claude.exe` echo.

### Phase 5.1 — Terminal guide & whole-document AI → `v0.5.1`
- [x] **How to** in the terminal header: pick Windows / macOS / Linux (auto-detected) and Claude
      Code / Codex (✓ when installed, found via PATH / `~/.local/bin`); 5 steps — install, restart
      the terminal, check (`--version`), start & sign in, use — each command with *Type in
      terminal* (typed, not run: the user presses Enter) and *Copy*, plus what it does in plain
      words ("this is your computer's own command line…"). Commands verified against the official
      docs on 2026-10-15: Claude `irm https://claude.ai/install.ps1 | iex` /
      `curl -fsSL https://claude.ai/install.sh | bash`; Codex
      `powershell -ExecutionPolicy ByPass -c "irm https://chatgpt.com/codex/install.ps1 | iex"` /
      `curl -fsSL https://chatgpt.com/codex/install.sh | sh`. Re-check them when updating.
- [x] **✦ AI in the toolbar** for the whole text: summarize the document / this chapter, explain
      this page, key ideas & terms, study questions, own question. The page range is converted to
      Markdown (`ai_context`, cached in `<data>/ai/<doc>-p<a>-<b>-r<rev>.md`, includes unsaved OCR)
      and the AI is told to read that file. (Done ahead of Phase 6's "AI reads the whole PDF".)
- [x] Park button moved next to Read / Focus

### Phase 5.2 — Polish before Phase 6 → `v0.5.2`
- [x] **Undo / redo** of annotation changes (Ctrl+Z, Ctrl+Y / Ctrl+Shift+Z): add, edit, delete;
      a deleted annotation comes back with **its old /NM id** (`add_annotation(annot_id=…)`), so
      note pins keep working. Session-only history, 200 steps per tab.
- [x] **Pen colour & width** bar while drawing (6 colours, 4 widths, remembered as `ink`); ink
      annotations now expose `strokes` + `width`
- [x] **Open Beside** in the link preview: the same document opens at the link target in a pane
      beside (a second tab on the same doc; the backend reference is released with the last tab)
- [x] **Drag a tab onto another PhDF window** to move it there (`window_at` + `send_to_window`,
      the target takes its reference first); elsewhere it still opens a new window
- [x] **Bookmarks**: Ctrl+B, red ribbon on the page, sidebar *Marks* tab with editable labels
      (`bookmarks` table, follows the doc id across saves)
- [x] **Where was I?** card when a document is reopened: page, how long ago, latest highlight
      (click to jump), latest open parked thought; dismisses itself
- [x] **Copy with citation**: Ctrl+Shift+C or the selection menu → “quote” — Title, p. 12
- [x] **Export Highlights to Note** (⋯ menu / palette): every annotation, by page, with pins,
      under `---` + `## Highlights` at the end of the integrated note, between
      `<!-- phdf:highlights -->` … `<!-- /phdf:highlights -->` markers (hidden in previews);
      re-exporting replaces only that section, the user's writing above it is kept
- [x] **Command palette** (Ctrl+K): every action, recent documents, “Go to page N”, “Search …”
- [x] **Window size & position** remembered per window (`window.<id>`, incl. maximized)
- [x] **Library** box on the welcome page: every document with cover (cached in
      `<data>/covers`), progress bar, time read; filter; missing files dimmed
- [x] **Reading stats** box under it: today / this week / streak + minutes per day for 14 days
      (bar chart with hover + table view); fed by real reading seconds (`reading_log` table,
      flushed every 30 s from the pace tracker)
- Not chosen this round: double-click to explain a word (#9), Turkish UI (#11)

### Phase 5.5 — Grading mode → `v0.5.5` (done)
For teachers / TAs grading a folder of exam PDFs one by one.
- **Entry**: a *Grade* button at the right of the toolbar, next to *How to use* (?) (owner moved it
  there from the left of Read); while the mode is on it stays
  highlighted. Clicking it asks for a **folder** of exam PDFs (subfolders included — LMS exports
  such as Moodle put each submission in its own folder).
- **One PDF at a time**: the first PDF opens; the user marks it with every normal tool (pen,
  highlight, notes). A bottom bar shows **Prev · n / N · [Grade] · Done**. Done saves and opens
  the next PDF; Prev goes back. The session remembers where it stopped.
- **Originals are never touched**: the marked copy is saved to `<folder>/graded/<same relative
  path>`. Reopening a PDF that already has a graded copy opens the copy.
- **Left sidebar**: instead of Chapters, a list of every PDF in the folder (done ✓ / current /
  not yet); click to jump.
- **Grades table** (the integrated note, right side) belongs to the **folder**, not to a PDF:
  `<folder>/<folder name>.grades.md`, created at the start with one row per PDF:
  `| # | Name | Grade | Comment |`. The user may add own columns; PhDF keeps unknown columns
  and only fills the cells it owns.
  - *Name* starts **empty** (owner: don't put the PDF names in the table). The file's short name
    (the student's folder for Moodle-style subfolders, `_123456_assignsubmission_file_` removed,
    else the file name) is only shown in the Exams list, on the tab and as the drawer's hint.
  - Rows are numbered in a stable order kept in `grading.progress.<folder>` (with done + index):
    files added later get new numbers at the end, so a row never changes owner.
- **Automated** toggle (on/off, remembered):
  - on → when a PDF opens, a drawer slides down from the top asking for the student's
    identification (name / number), pre-filled from the table if already typed; the grade is typed in the box
    next to Done; both are written into the table on Done.
  - off → no drawer, no box: the user fills the table by hand.
- **Export CSV** of the table (same columns, UTF-8 with BOM so Excel shows Turkish letters).
- Grading stays on across restarts (`grading.window.<id>`); closing the exam's tab or clicking
  *Grade* again stops it. The tab shows the student's name instead of the file title.
- Also in v0.5.5: **move annotations** — drag a sticky note or text box; a drawing after clicking it
  (`move_annotation`; ink is re-created with the same id). Undoable. Highlights don't move.

### v0.5.6 — macOS / Linux review & optimization (owner asked)
- [x] macOS: shortcut labels shown as ⌘ / ⌥ / ⇧ (`lib/platform.ts` `kbd()` — titles, menus,
      palette, Help); ⌃⌘F full screen, ⌘[ / ⌘] back / forward; `.app` Info.plist (version,
      Retina, dark mode, macOS 11+)
- [x] Clipboard falls back to `execCommand("copy")` where the async API is refused (WebKitGTK,
      older WKWebView) — `copyText()`
- [x] AI tools are found outside PATH too (a Finder-started app has a short PATH): ~/.local/bin,
      ~/.claude/local, Homebrew, /usr/local/bin, npm / Volta folders
- [x] OCR font on Linux: Debian / Arch / Fedora / openSUSE DejaVu paths, Liberation, Noto, then
      `fc-match`; Linux UI / mono fonts in the CSS stacks
- [x] Grading progress key: `os.path.normcase` (case-insensitive only on Windows; the old
      lower-cased keys on Windows stay valid)
- [x] Files on the command line open at start (`phdf a.pdf b.md`, "Open with");
      `packaging/linux/phdf.desktop`
- [x] Faster: annotations are read only from pages with an /Annots entry (655-page book:
      340 ms → 6 ms when a document opens; finding one for an edit likewise); window geometry is
      written once a move/resize settles; text-layer / link caches keep the last 80 pages per
      tab; the move-cursor hover check runs once per frame and only when something is movable
- Not tested on a real Mac / Linux machine yet (no hardware here) — CI builds them; the owner
  should try a build there.

### Phase 5.7 — Text styles & AI equation converter → `v0.5.7` (done)
**Text boxes (Add text)**
- Font **Sans / Serif / Mono**, size **8–36 pt** (presets + any number), **bold**; chosen when
  placing and changeable later on an existing box (click it → the editor shows the same controls).
- How: FreeText with rich text (`richtext=True`, CSS `style="font-family; font-size; font-weight;
  color"` → `/DS`). Plain FreeText can't do bold (MuPDF maps HeBo/TiBo/CoBo to the regular
  fonts); rich text renders bold + Turkish letters correctly (tested). Old boxes (plain /DA) keep
  working and are converted when edited. The box size follows the font size. Contents must also
  be written to `/Contents` (rich text leaves it empty).

**AI equation converter (owner's design)**
- The ✦ button stays as it is (whole-document AI menu). **New: a small ▾ next to it** opens a menu
  with **“Equation → LaTeX (AI)”**.
- Choosing it turns the page into a **snipping view** (dimmed, crosshair, like a screenshot tool):
  drag a rectangle over an equation; Esc cancels.
- The rectangle is rendered to a **PNG** (high resolution) in a hidden temp folder in the
  terminal's working folder (`.phdf-tmp/eq-<id>.png`, so Claude Code / Codex may read and write
  there without leaving their workspace). PhDF sends the AI in the terminal:
  *read the image, write only its LaTeX to `.phdf-tmp/eq-<id>.tex`*. If no AI runs in the
  terminal, the usual “start Claude / Codex” offer appears.
- A **preview box** waits for the answer (spinner, Cancel), then shows the **rendered equation**
  (KaTeX) and the **editable LaTeX**, with **Insert** and **Copy**.
- **Insert** puts `$$ … $$` (with a small `p. 12` source line) **at the cursor** in the side note;
  if the note was never clicked, at its end; the note opens if it was closed.
- Afterwards the PNG and .tex are **deleted** (also on Cancel; leftovers cleaned when the
  terminal starts), so nothing bloats the folder.
- Also: the Markdown preview renders `$…$` / `$$…$$` math with KaTeX.
- Done as planned. Notes: quick +/− clicks on the size are merged into one change (one undo
  step); the box height is `lines × size × 1.4 + 6` (MuPDF clips rich text that doesn't fit);
  the AI's answer is cleaned of `$$`, `\[ \]`, code fences. The equation flow was tested with a
  fake AI that writes the .tex — **not yet with real Claude Code / Codex** (their permission
  prompts and image reading are the parts to watch).

### Phase 6 — postponed
The owner postponed the planned Phase 6 (“didn't make much sense for now”); its items moved to
**Upcoming features** below. The number is kept free, so the next phase is Phase 7.

### Phase 7 — PDF Tools (owner: later)
- [ ] Rotate pages, extract / delete pages, reorder, merge PDFs, split a PDF

### → `v1.0` when Phases 0–5.5 and 7 are stable on all three OSes.

### Upcoming features (not scheduled — picked from here into a phase when the owner wants)
- **`phdf://` deep links**: clicking a pin/link in Obsidian opens PhDF at that page/annotation
  (register the URL scheme with the OS) — was Phase 6
- **Send to the currently open Obsidian note** (Local REST API plugin) — was Phase 6
- **Double-click a word → AI explains it** (offered as #9 in Phase 5.2)
- **Turkish UI** (offered as #11 in Phase 5.2)
- **App icon** — the owner is designing it (give a 1024×1024 PNG → `.ico` / `.icns`, wire into
  `phdf.spec` and the window)
- (done in Phase 5.1: the AI can read the whole PDF via the Markdown export — ✦ AI menu)

### Owner's notes for the next round (2026-10-16, not started — wait for "start")
1. **Default AI agent**: let the user pick a default agent (Claude Code, Codex or another one);
   later, whenever the AI is needed and none runs in the terminal, start the default one
   automatically instead of asking every time.
   - **First time (owner, 2026-10-16):** when the AI terminal opens (terminal button, ✦ menu,
     Ask AI) and no agent has been chosen yet, a popup inside the terminal panel asks to **add an
     agent**: Claude Code, Codex, or another command (typed in), with a link to *How to* for
     installing one. The choice is saved as the default.
   - **After that:** the panel opens and the default agent starts by itself; no question. It can
     be changed in Settings and from the terminal header (owner approved).
2. **Equation → LaTeX: an OK step**: after the rectangle is drawn, show the box with an **OK**
   button; only OK sends the request to the AI in the terminal (today it is sent at once).
3. **Swap terminal and note** in the right panel: the AI terminal and the integrated .md can trade
   places (terminal below the note, or note above the terminal), remembered.
4. **"How to use PhDF" as cards**: opening it shows the first section as one big card; click
   (or →) goes to the next card until the end; ← back; a close button.
5. **Markdown: edit in preview**: a mode where the rendered note can be edited directly (like
   Obsidian's live preview), not only Edit / Preview tabs.
6. **Other AI agents**: everywhere the app or docs talk about the AI (terminal guide, Help,
   README, prompts, "no AI is running" offer), say that any terminal AI agent can be installed and
   used the same way; keep Claude Code and Codex as the examples. Detection (`term_ai`) and the
   default-agent setting (1) should accept other names too.
7. **Highlighting behaves oddly**: owner reports it; reproduce first (ask the owner what exactly
   happens: wrong lines, gaps, offset, selection jumping?) before changing anything.
8. **Remove all em dashes (—)**: from the app's texts and the docs (scope to confirm: UI
   strings, Help, README, HANDOFF, generated notes such as `# Grades — <folder>` and
   `Parking Lot — <book>`; code comments too?). Use a plain hyphen, colon or comma instead.
9. **Terminal tabs**: more than one AI terminal (tabs in the terminal header, `+` to add, each its
   own shell / agent; closing one keeps the others).
10. **"Read as Markdown" switch in the AI menus** (owner's idea, proposal agreed in principle):
    a toggle at the bottom of the ✦ / Ask AI menus.
    - **On** (default): PhDF converts the document to Markdown once, caches it in
      `<data>/ai/` (as `ai_context` already does per page range — extend to "whole document,
      prepared in the background when the switch is on"), and the AI reads that: fast, few
      tokens, works for Codex too. The prompt also gives the PDF path and page, telling the AI to
      open the PDF itself only when it needs what Markdown loses (figures, tables as images,
      equations, layout).
    - **Off**: no conversion; the AI is pointed at the PDF and the page(s) and reads it itself
      (Claude Code reads PDFs with images; Codex may need its own tool for PDFs).
    - Remembered as a setting. **Owner decided: only in the ✦ AI menu, on by default — but off by
      default for big PDFs** (proposed: more than 300 pages; a whole-book conversion takes
      minutes). The menu says why it is off and the user can still turn it on for that document
      (remembered per document). Owner approved the page-marker plan below.
    - **Page markers (needed):** pymupdf4llm writes no page numbers at all (checked on Film Art:
      the only numbers are the book's own printed headers, e.g. "20 CHAPTER 1" on PDF page 41),
      so the AI could mix up pages. Convert page by page (`page_chunks=True`) and put a marker
      before each page, e.g. `<!-- PDF page 41 -->`, and tell the AI in the prompt that "page"
      means these markers (the printed numbers can differ).
    - **Whole document in the background:** with markers, one cached file per document revision
      serves every request (chapter / page ranges are cut from it), so after the first conversion
      every question starts at once. Cost measured: ~0.36 s per page (Film Art, 655 pages ≈ 4 min,
      once, in the background, without holding the render lock); show progress in the menu.
11. **Clean the AI cache** (`<data>/ai/`, today never deleted): keep only the newest revision of
    each document, delete files not used for 30 days, and cap the folder (e.g. 500 MB, oldest
    first). Run at startup and after a conversion. Also a "Clear AI cache" button in Settings.
12. **A nicer-looking Markdown note** (owner: "make it look better"; **owner approved these
    ideas**): headings with more rhythm (sizes, spacing, a thin rule under H1/H2),
    pin cards and their quotes as soft cards with the highlight's colour, nicer tables (zebra
    rows, rounded border; the grades table too), code blocks and callouts (`> [!note]` like
    Obsidian), task lists with real checkboxes, a comfortable reading width with centred text,
    better link / image styling; the Edit view closer to the Preview (live headings, dimmed
    Markdown marks). Best done together with #5 (edit in preview).
    - **Adjustable in Settings** (owner): a "Note appearance" section next to the existing *Aa*
      typography (font, size, spacing): theme / accent for headings and pin cards, reading width,
      table style, show or hide Markdown marks in Edit; a live sample and "Reset to default".

---

## 7. Future Ideas (candidate phases, add as we go)

- **Command palette** (Ctrl+K) & full keyboard navigation (optional vim keys)
- **Library**: tags, collections, full-text search across all PDFs (basic Library box done)
- **Citations**: Zotero / BibTeX import, citation keys in Obsidian quotes
- **Sync**: positions/annotations synced via the Obsidian vault folder (or any synced folder)
- **Two-way note sync**: keep the integrated note and its Obsidian vault copy in step (D20)
- More Focus pull-down items (owner: "maybe we add other things there later")
- **Flashcards**: turn highlights into Anki / Obsidian spaced-repetition cards
- **Text-to-speech** reading with word highlighting
- **Translation** of selection (local or via AI terminal)
- **Dual-page / book mode**, presentation mode
- **Basic page tools**: merge, split, rotate, reorder, extract
- **Other formats**: EPUB, XPS, CBZ (MuPDF supports these natively)
- **Plugin system** for community extensions
- **AI extras**: chat-with-PDF context files, auto-summaries per chapter into Obsidian
- **Mobile / tablet** companion (long-term, separate project)
- **PDFium engine** implementation if a closed-source edition is ever needed (D3)

---

## 8. Implementation Notes / Gotchas

- **Windows `.js` MIME type:** the registry often maps `.js` → `text/plain`; Python's `mimetypes`
  reads it, pywebview's local server then serves modules as text and WebView2 refuses them (blank
  window). Fixed by `fix_mimetypes()` in `app.py` — keep it.
- **TypeScript pinned to 5.x:** `svelte-check` does not yet support TypeScript 7 without extra
  setup. Revisit later.
- **Thread safety:** pywebview calls API methods on worker threads; MuPDF is not thread-safe, so
  `Api` serializes engine access with a lock, and `Store` serializes its SQLite connection.
- **pywebview exposes every public attribute** of the API object to JS → keep internals `_private`.
- **Dev mode:** `npm --prefix frontend run dev` + `PHDF_DEV=1 uv run phdf` (hot reload, devtools),
  or set it in `.env` (copy `.env.example`).
  `PHDF_DATA_DIR` overrides the data directory (useful for tests/packaged-app checks).
- **Page images** come from `RenderServer` (127.0.0.1, random port, random token in the path),
  not the JS bridge. URLs are cached as `immutable` because `doc_id` is a content hash —
  **Phase 2 must add a revision parameter** once annotations change how a page renders.
  PNG beat JPEG for text pages (smaller and faster to encode).
- **Text layer:** spans are positioned in PDF points inside a layer scaled by CSS `transform`,
  each span stretched with `scaleX` to its PDF bbox (canvas `measureText`), `<br>` after each line
  so copied text keeps line breaks.
- **Position model:** `scroll` = offset within the current page as a 0..1 fraction, so it
  survives zoom/window-size changes. Migration 2 added the `fit` column.
- **Web link previews** open in a separate pywebview window *without* `js_api` — never expose the
  app API to third-party pages.
- **Tab drag & drop uses pointer events + pointer capture**, not HTML5 DnD: capture keeps
  events flowing outside the window (→ tear-off detection) and synthetic `PointerEvent`s make it
  scriptable in tests. Drop targets are found with `elementsFromPoint` and `data-pane-bar` /
  `data-pane-body` attributes.
- **Session format** is `{panes: [{paths, active, width}], focused}` per window; the v0.1.0
  `{paths, active}` format is migrated on startup (`saved_window_ids` in `app.py`) and in the
  frontend (`normalize`).
- **Annotation ids:** we always write our own `/NM` (5 chars). MuPDF's own `fitz-…` names are
  not stable across sessions; annotations made elsewhere without `/NM` get `x<xref>`.
- **Dirty state is tracked by us** — PyMuPDF's `is_dirty` stays true after `saveIncr()`.
- **Free-text colour** lives in the `/DA` string, not in `annot.colors`.
- **Saving changes the content hash** (= doc id). `Core` keeps `old → new` aliases and renames
  the `documents` row, so the frontend keeps using the id it got for the whole session.
  `findPdf` also matches by path for files reopened after a save.
- **Render cache busting:** `Core` bumps a per-page revision on every annotation change; image
  URLs carry `&r=<rev>` (pages, thumbnails, link peek).
- **OCR runs outside the document lock**: render under the lock → recognise the PNG (thread-safe,
  no shared doc) → write the invisible words under the lock. Words use a system TTF (Arial /
  DejaVu) so Turkish letters extract correctly; Helvetica would turn them into “?”.
- **Export** works on `doc.tobytes()` (includes unsaved OCR text) in a separate document.
- **pymupdf4llm is pinned to 0.3.x**: from 1.27 on it requires `pymupdf-layout` (an AI layout
  model: onnxruntime + numpy, +70 MB to the app). 0.3.x keeps that optional; output is the
  classic heuristic Markdown. Revisit if export quality matters more than size.
- **Big PDFs:** never iterate every page on open (text checks, annotation scans…). Keep
  per-page work lazy; `Core.render` trims the engine cache. `.gitignore` ignores `*.pdf` (test
  books live in the repo folder).
- **Shell heredocs**: long Python snippets with curly quotes broke `bash -c`; write helper
  scripts to the scratchpad and run them instead.
- **Write files as UTF-8 explicitly** (`encoding="utf-8"`) on Windows; the default cp1252 once
  corrupted an em dash in `store.py`.
- **Screenshot testing:** WebView2 content is not captured reliably by `CopyFromScreen`; use
  `PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT=2)`. Don't force the window to the foreground in
  scripted tests. Phase 1 was verified with a scripted end-to-end run (restore, selection, search,
  internal/external link peek, history, zoom, thumbnails, tabs, dark pages, saved positions).
- **Free text is rich text since v0.5.7** (`/DS` CSS). Every change re-creates the box with the
  same /NM id (`update_annotation`, `move_annotation`) — MuPDF lays rich text out only on creation.
  Never keep a `pymupdf.Annot` from `list(doc[i].annots())` after the page object is gone: that
  segfaults (seen while testing, a test-script bug, not in PhDF).
- **Equation temp files**: `services/equations.py` only deletes `.phdf-tmp/eq-*` files;
  `term_start` cleans leftovers older than an hour.
- **Platform differences live in `lib/platform.ts`** (`isMac`, `kbd()`, `copyText()`). Write
  shortcut labels as "Ctrl+…" wrapped in `kbd()`; key handlers already accept Ctrl or ⌘.
- **`MdDoc.flush()` is queued:** two `write_text` calls on the same note at once raced on its
  `.phdf-tmp` file (PermissionError on Windows) — seen when grading wrote the table twice.
- **Grading's table is shared:** every exam tab gets the same `MdDoc` via `tab.attachNote()`;
  `detachNote()` on stop. The grading tab is closed with `ws.remove` + `releaseDocument` (it is
  saved first, so no Save sheet).

## 9. Next Steps

1. Owner: create the GitHub repo (install `gh` or use the web UI), push, confirm CI is green on
   Windows and see what macOS/Linux report.
2. Next on the owner's "start": Phase 7 PDF Tools, or something from *Upcoming features*
   (Phase 6 is postponed); then v1.0. Try the equation converter with real Claude / Codex.
