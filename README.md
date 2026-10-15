# PhDF

A lightweight, reader-first PDF app for heavy readers — with position memory, a built-in
Markdown editor, Obsidian integration, OCR, and a terminal-based AI side panel.

> **Status:** early development (v0.1 — core reader). See [`HANDOFF.md`](HANDOFF.md) for the
> full roadmap and design decisions.

## Keyboard shortcuts

| Action | Keys |
|---|---|
| Open PDF | Ctrl+O |
| New tab / close tab / next tab | Ctrl+T / Ctrl+W / Ctrl+Tab |
| Search (Enter next, Shift+Enter previous) | Ctrl+F |
| Go to page | Ctrl+G |
| Zoom in / out / actual size | Ctrl++ / Ctrl+- / Ctrl+0, or Ctrl+wheel |
| Back / forward (after links, outline, go-to) | Alt+← / Alt+→ |
| Previous / next page, first / last page | ← / →, Home / End |
| Toggle sidebar | Ctrl+\ |

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
