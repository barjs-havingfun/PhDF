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
  `npm --prefix frontend run check` if the frontend changed). The owner tests the UI by hand.
- No em dashes in UI strings, generated notes or docs. Repo is LF: after editing on Windows run
  `sed -i 's/\r$//'` on changed files. Update `HANDOFF.md` (open work, gotchas) at the end.

## Code map
Backend `backend/phdf/`
- `app.py`: entry (`uv run phdf`), creates windows, render server, startup cleanups.
- `api.py`: `Core` (shared by windows: open docs + refcounts, id aliases after saves, page
  render revisions, `lock`) and `Api` (one per window, exposed to JS as
  `window.pywebview.api.*`; public methods only, internals `_private`). Grouped by feature:
  documents, annotations, bookmarks, reading stats / library, OCR, export, grading, Obsidian,
  AI terminal (`term_*`, `ai_context`, `ai_cache_*`, equations), parking, markdown files, links,
  settings.
- `engine/base.py` (interface, dataclasses) + `engine/mupdf.py` (all PyMuPDF specifics).
- `db/store.py`: SQLite; append-only `MIGRATIONS`; settings are JSON key/values.
- `services/`: small path-based modules used by `Api`: `terminal` (PTY sessions, AI process
  detection), `ai_cache`, `equations`, `grading`, `ocr`, `parking`, `render_server`,
  `webview_memory`, `pdftools` (PhDF Tools sessions), `ai_markdown`.
- `docid.py` (content hash), `paths.py` (data dir, `PHDF_DATA_DIR`), `env.py` (`.env`).

Frontend `frontend/src/`
- `App.svelte`: shell: windows / panes / tabs, opening files, sidebar, palette commands,
  keyboard shortcuts (`onKeydown`), session restore, sheets, toasts. `lib/Toolbar.svelte`: the
  toolbar (its own menus, search, go to page; actions come in as `on…` props).
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
  `lib/focus/`, `lib/grading/`, `lib/library/`, `PaneView`, `Sidebar`, `LinkPeek`, `Help`,
  `Settings` (incl. About), `PrintSheet`, `PdfTools` (PhDF Tools view), `CommandPalette`, `platform.ts` (`kbd()`, `copyText()`), `updates.ts` (opt-in update check), `outside.ts` (close menus on outside press), `pin.ts`, `cite.ts`.

## Patterns
- Engine access: `with self._core.lock:`; slow work outside the lock on a copy.
- Annotation edits return `{dirty, revs}`; the frontend applies them and page images reload
  through `&r=<rev>`. Undo: raw `_add/_update/_delete` + public wrappers that `record()` a step.
- New feature state that should persist: a settings key (`get_setting` / `set_setting`).
- Comments are short and explain why. Platform-specific code goes in `lib/platform.ts`.
- Tests: `tests/test_<area>.py`, `Api(Core(default_engine(), Store(tmp)), "main")` with
  `PHDF_DATA_DIR` set to a temp folder; `sample_pdf` fixture in `conftest.py`.
