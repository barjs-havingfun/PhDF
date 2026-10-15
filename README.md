# PhDF

A lightweight, reader-first PDF app for heavy readers — with position memory, a built-in
Markdown editor, Obsidian integration, OCR, and a terminal-based AI side panel.

> **Status:** early development (v0.4.1 — Read mode, Focus, parking lot). See [`HANDOFF.md`](HANDOFF.md) for the
> full roadmap and design decisions.

## Keyboard shortcuts

| Action | Keys |
|---|---|
| Open PDF or Markdown | Ctrl+O |
| Save annotations | Ctrl+S |
| New tab / close tab / next tab | Ctrl+T / Ctrl+W / Ctrl+Tab |
| Search (Enter next, Shift+Enter previous) | Ctrl+F |
| Go to page | Ctrl+G |
| Zoom in / out / actual size | Ctrl++ / Ctrl+- / Ctrl+0, or Ctrl+wheel |
| Back / forward (after links, outline, go-to) | Alt+← / Alt+→ |
| Previous / next page, first / last page | ← / →, Home / End |
| Toggle sidebar | Ctrl+\ |
| Zen mode / full screen | Ctrl+. / F11 |
| Parking lot (park a stray thought) | Ctrl+Shift+Space |
| Delete selected annotation | Delete |

**Tabs & panes:** drag a tab to reorder it; drop it on the left/right edge of a document to view
up to three side by side (drag the divider to resize); drop it outside the window to open it in a
new window.

**Read & Focus:** the *Read* menu (top left) turns on a reading ruler, zen mode, full screen
or a page tint — each on its own. *Focus* has a small pomodoro and shows how long the chapter
and the document will take at your reading pace (fast scrolling doesn't count). The lightbulb
(Ctrl+Shift+Space) parks a stray thought in `<book>.parking.md` next to the PDF; it shows up in the
**Parking** tab of the note panel.

**OCR, export & Obsidian:** scanned pages show a *Recognize Text* bar (language files are
downloaded on first use — no Tesseract install needed). The ⋯ menu exports the document as
Markdown (to a file or your Obsidian vault) and copies notes to Obsidian; *Send to Obsidian* in
the selection menu adds the quote to the book's note in your vault (set it in ⋯ → Settings).

**Annotations & notes:** select text to highlight / underline / strike it or send it to the
PDF's integrated note (**Note in MD**). The note is `<pdf name>.md` next to the PDF and opens beside
it in the same tab; each quote starts with a pin like `⎘ phdf · p.12 · §2.1 · #k7q2` — click
**Go to PDF ↗** to jump to the highlight, or click the highlight to jump to its note.

## Stack

- **Backend:** Python 3.12 · [pywebview](https://pywebview.flowrl.com/) · [PyMuPDF](https://pymupdf.readthedocs.io/) · SQLite
- **Frontend:** Svelte 5 · TypeScript · Vite
- **Platforms:** Windows (primary), macOS and Linux (experimental)

## Development

Requirements: [uv](https://docs.astral.sh/uv/) and Node.js 20+.

```sh
# install dependencies
uv sync
npm --prefix frontend install

# option 1: run against the built frontend
npm --prefix frontend run build
uv run phdf

# option 2: hot reload — run the Vite dev server, then start the app in dev mode
npm --prefix frontend run dev
PHDF_DEV=1 uv run phdf          # PowerShell: $env:PHDF_DEV=1; uv run phdf
```

Settings like `PHDF_DEV` can also go in a `.env` file — copy `.env.example` to `.env`
(it is git-ignored).

Checks:

```sh
uv run ruff check . && uv run ruff format --check .
uv run pytest
npm --prefix frontend run check
```

Package a standalone app (output in `dist/PhDF/`):

```sh
npm --prefix frontend run build
uv run pyinstaller phdf.spec --noconfirm
```

### Linux

pywebview uses GTK + WebKit2 on Linux. Install the system packages first, e.g. on Debian/Ubuntu:

```sh
sudo apt install libgirepository-2.0-dev libcairo2-dev pkg-config gir1.2-webkit2-4.1
```

## License

PhDF is licensed under the [GNU Affero General Public License v3.0](LICENSE) (or later).
Contributions require agreeing to the [Contributor License Agreement](CLA.md).
