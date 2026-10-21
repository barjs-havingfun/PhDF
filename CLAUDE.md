# PhDF: notes for Claude

Reader-first PDF app: Python backend (pywebview + PyMuPDF + SQLite) and a Svelte 5 / TypeScript
frontend. Current state and open work: `HANDOFF.md`. **Don't read `OLDLOG.md`** (old archive)
unless the owner asks.

## Working with the owner
- Discuss first; write code only after the owner says "start" / "başla". The owner writes in
  Turkish or English; project docs and UI are English.
- Never commit or push: the owner does git by hand.
- Keep token use low: find code with grep and read only the parts you change; batch edits;
  test only what changed, once at the end (`uv run pytest tests/test_<area>.py`, plus
  `npm --prefix frontend run check` + `npm --prefix frontend test` if the frontend changed). The owner tests the UI by hand.
- No em dashes in UI strings, generated notes or docs. Repo is LF: after editing on Windows run
  `sed -i 's/\r$//'` on changed files. Update `HANDOFF.md` (open work, gotchas) at the end.

## Code map
Backend `backend/phdf/`
- `app.py`: entry (`uv run phdf`), creates windows, render server, startup cleanups.
- `api/` package: `core.py` `Core` (shared by windows: open docs + refcounts, id aliases after
  saves, `open_id` for identical copies, page render revisions, `lock`, `tell_windows`);
  `Api` (one per window, exposed to JS as `window.pywebview.api.*`; public methods only,
  internals `_private`) is built in `__init__.py` from one class per feature file:
  `windows` (app, dialogs, closing, theme, zoom, updates, settings, cleanup), `documents`
  (open, text, search, positions, bookmarks), `annotations` (+ save / revert), `library`
  (reading stats, Library, About), `ocr_export`, `notes` (grading folders, vault, parking,
  Markdown files), `ai` (terminal, equations, AI context / cache), `tools` (PhDF Tools),
  `links`. Per-window state: `base.py` `ApiBase`.
- `engine/base.py` (interface, dataclasses) + `engine/mupdf.py` (all PyMuPDF specifics).
- `db/store.py`: SQLite; append-only `MIGRATIONS`; settings are JSON key/values.
- `services/`: small path-based modules used by `Api`: `terminal` (PTY sessions, AI process
  detection), `ai_cache`, `equations`, `grading`, `ocr`, `parking`, `render_server`,
  `webview_memory`, `pdftools` (PhDF Tools sessions), `ai_markdown`, `workers` (OCR and Markdown
  conversion in worker processes: MuPDF is not thread-safe).
- `docid.py` (content hash), `paths.py` (data dir, `PHDF_DATA_DIR`), `env.py` (`.env`).
- `selftest.py`: `PhDF --self-test`, a no-window check of a built app (release CI runs it).

Frontend `frontend/src/`
- `App.svelte`: shell: windows / panes / tabs, opening files, sidebar, session restore,
  toasts. It hands its actions to `lib/commands.ts` (palette commands), `lib/shortcuts.ts`
  (keyboard) and asks through `lib/ask.svelte.ts` (password, Save / Don't Save; shown by
  `AskSheets`). `lib/Toolbar.svelte`: the toolbar (its own menus, search, go to page; actions
  come in as `on…` props); its ⋯ menu is `lib/MoreMenu.svelte`.
- `lib/api.ts`: typed mirror of `Api`. **Add every new backend method here.**
- State classes (`*.svelte.ts`): `tab.svelte.ts` (`Tab`: view, history, search, annotations +
  undo, OCR, integrated note / parking; `MdTab`), `workspace.svelte.ts` (panes), `md.svelte.ts`
  (`MdDoc`: load / autosave / reload), `reading.svelte.ts` (Read / Focus / pace / pomodoro),
  `notify.svelte.ts` (toasts, `ui` sheet flags), `theme.svelte.ts` (System / Light / Dark), `prefs.svelte.ts` (general settings, toolbar buttons), `dnd.svelte.ts` (tab drag).
- `lib/viewer/`: `Viewer.svelte` (virtualized scroll, zoom, selection → rects, ink, moving
  annotations), `PageView.svelte` (image, text layer, links, selection fix).
- `lib/annot/` (selection menu, right-click `ContextMenu`, editor, annotations panel), `lib/md/`
  (CodeMirror `MdEditor`, `format.ts` commands, `FormatBar`, right-click `EditorMenu` with Ask
  AI, `MdSidebar` (a standalone note's Contents / Files), `live.ts` Live mode, markdown-it `render.ts`, typography), `lib/ai/` (`terminal.svelte.ts`: terminal tabs, default agent,
  `askAi`, terminal font, go to folder; `AiPanel`, `AgentPicker`, `TerminalGuide`, `DocAiMenu`, equation flow),
  `lib/focus/`, `lib/grading/`, `lib/library/` (Library, `kinds.ts` tags / filter), `PaneView`, `Sidebar`, `LinkPeek`, `Help`,
  `Settings` (incl. About), `PrintSheet`, `PdfTools` (PhDF Tools view), `CommandPalette`, `platform.ts` (`kbd()`, `copyText()`), `updates.ts` (opt-in update check), `outside.ts` (close menus on outside press), `pin.ts`, `cite.ts`.

## Patterns
- Engine access: `with self._core.lock:`; slow work outside the lock on a copy.
- Annotation edits return `{dirty, revs}`; the frontend applies them and page images reload
  through `&r=<rev>`. Undo: raw `_add/_update/_delete` + public wrappers that `record()` a step.
- New feature state that should persist: a settings key (`get_setting` / `set_setting`).
- Document identity (read before touching ids, saves, copies or caches):
  - *Content id* `document_id(path)`: SHA-256 of size + first 1 MB. Positions, bookmarks and
    the Library follow it across renames and moves.
  - *Copy id* `copy_id(content, path)`: an identical copy of a file that is already open (or
    whose content matches an old id) gets an id of its own, so edits never land in the other
    file. It depends on the path, so a moved copy is recognised by content + its old path
    (`library_relink`).
  - *Session id*: the id a window opened a document under. A save changes the content, so the
    document gets a new id and the old one becomes an alias (`Core.resolve`). Windows keep the
    old id; compare `resolve(a) == resolve(b)`, never the raw ids. Each window holds one
    reference per document (`_open`).
  - *Text generation* (`Core.text_revs`): "0" is the text on disk, and each unsaved OCR change
    gets a new random label. AI Markdown copies are named `<id>-<part>[-t<size>]-r<label>`
    (`-t`: an e-book's text size), so text that was discarded or laid out again never matches.
  - Passwords (`Core.passwords`) live in memory under the current id and follow saves.
- Comments are short and explain why. Platform-specific code goes in `lib/platform.ts`.
- Frontend tests: Vitest, `frontend/src/test/*.test.ts` (pure modules; `api` mocked with `vi.mock`).
- Tests: `tests/test_<area>.py`, `Api(Core(default_engine(), Store(tmp)), "main")` with
  `PHDF_DATA_DIR` set to a temp folder; `sample_pdf` fixture in `conftest.py`.
