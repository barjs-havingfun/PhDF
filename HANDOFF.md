# PhDF - Handoff

> Status: **v0.7.0** (2026-10-17). Repo: github.com/barjs-havingfun/PhDF; the owner commits and
> pushes by hand. Ask the owner before starting new work ("start" / "başla").
> Code map and conventions: `CLAUDE.md`. Full history up to v0.5.8: `OLDLOG.md` (archive, don't
> read unless asked). Original requirements: `notes.md`.

## What PhDF is
A lightweight, reader-first, cross-platform PDF app (Windows primary, macOS / Linux built by CI)
for heavy readers: remembers your place, lives next to Markdown notes (integrated `.md` per PDF,
pins, Obsidian bridge), OCR, export to Markdown, reading aids (ruler, zen, tints, pomodoro,
parking lot), grading mode for teachers, and an embedded terminal for AI agents (Claude Code,
Codex or any other). Non-goals: PDF authoring, forms, signatures.

## Key decisions (why it is built this way)
- **Python + pywebview** (OS webview, no bundled Chromium) + **Svelte 5 / TS / Vite** frontend.
- **PyMuPDF** behind a `PdfEngine` interface (MuPDF is AGPL; PDFium is the fallback if a
  closed-source edition is ever needed). License **AGPL-3.0** + **CLA** for contributors.
- **SQLite** store; document id = **content hash** (positions survive renames; a save gives a new
  id, `Core` keeps aliases).
- Annotations are written **into the PDF** (own `/NM` ids), saved with **Ctrl+S** (incremental).
- Integrated note = `<pdf>.md` next to the PDF; parking lot = `<pdf>.parking.md`; pins
  `⎘ phdf · p.12 · §2.1 · #id` link note ↔ highlight both ways.
- Obsidian v1 = copies into the vault, not sync. OCR = MuPDF's Tesseract, language files
  downloaded on demand. AI = the user's own terminal CLI (no API keys in PhDF).
- macOS-style UI (tokens in `frontend/src/app.css`); no engine name in the UI.
- Owner's text style: no em dashes in UI texts, generated notes or docs (comments may keep them).

## Open work (owner's notes; wait for "start")
2-5: done (see below).
6: done (see below).
10: done (see below).
12: done (see below).
13: done (see below).
Done in v0.6.0 (2026-10-16, not yet tested by the owner):
- **#2 Equation OK step**: the box first shows the drawn area with **OK** / Cancel; only OK
  renders it and asks the AI (`confirmEquation`).
- **#3 Terminal below the note**: ⇅ in the terminal header (side dock) swaps it with the note
  (`term.below`, saved in `terminal.layout`; `.side.swap` = column-reverse in `PaneView`).
- **#4 Help as cards**: big frosted-glass cards (one per section + shortcuts) that slide left / in from the right; click / → next, ← back, dots. Opens by itself on the first start (`help.seen`).
- **#5 Live mode**: Edit | **Live** | Preview (remembered, `md.mode`). `md/live.ts` hides Markdown
  marks except on the lines being edited (headings, emphasis, strike, inline code, links, quotes),
  bullets as •, tasks as clickable checkboxes, rules, `==mark==`, dimmed `%%comments%%`. The
  format bar shows in Edit and Live. The editor now parses GitHub-flavoured Markdown.
- Terminal font / size also in **Settings → AI** (same as the terminal's **Aa**).
- **Markdown overhaul (#12 + owner's wishes)**: bigger format bar with SVG icons, grouped,
  shortcuts in tooltips (Ctrl+B / I / E, Ctrl+Shift+K link / X / H; Ctrl+K is always the palette); paragraph style menu previews each
  style. **Zoom**: Ctrl+wheel, Ctrl+= / - / 0 in a note (`zoomText`, range 10-32 px), % in the new
  status line (words, reading time, Saved ✓). **Rename** by clicking the file name (`rename_file`
  keeps the PDF link; PhDF's `.parking.md` / `.grades.md` can't be renamed). **Link an existing
  .md** first explains that the current note stays on disk but stops opening with the PDF.
  Preview: heading rhythm with rules, pin cards, callouts `> [!type]` with colours and icons,
  footnotes, task checkboxes, zebra tables, code blocks, links, images. Empty notes show a hint.
- **App font** (Settings → Appearance): System, Inter, Atkinson Hyperlegible, Literata
  (`ui.font`; sets `--font`, which notes on "System" follow).
- **#13 Drawing is fast**: points in a plain array, the live line redrawn once per frame
  (coalesced pointer events); a finished stroke stays drawn (`tab.pendingInk`) until the page
  image with the saved drawing has loaded, so it never blinks away.
- **#6 + #19 Any agent, Gemini CLI**: Gemini CLI is a known agent (card, + picker, detection,
  `ai_tools()`, terminal guide: `npm install -g @google/gemini-cli`, needs Node.js 20+, Sign in
  with Google; resume `gemini --resume latest`, checked in its 0.64 code). Guide, Help, README,
  prompts say any terminal AI works the same way.
- **#10 Read as Markdown** (✦ menu switch): on by default, off over 300 pages, remembered per
  file (`ai.markdown.<lower-cased path>`, so it survives saves). On: the whole
  document converts in the background (`ai_markdown_prepare` / `_status`, progress in the menu)
  with `<!-- PDF page N -->` markers (`services/ai_markdown.py`); ranges are cut from it. Off: the
  AI is told to open the PDF pages. Copies are keyed by a **text revision** (only OCR bumps it),
  not render revisions, and follow the document to its new id on save (renamed to `r0`).
- **Link preview**: drag the small card by its header; right-click inside it: on selected text
  the selection menu (copy, citation, highlight, Note in MD, Ask AI), else the page menu. The
  menus are rendered outside the card (its blur / transform would trap `position: fixed`).
  `PeekPage` uses `PageView`, so the selection fix applies there too.
- **Live mode shows math**: `$…$` / `$$…$$` typeset with KaTeX (a state field in `live.ts`; a
  `$$` block may span lines); click it, or put the cursor in it, to edit the LaTeX.
- **Two-page view** (Read → Pages: Single / Two pages / Two, cover alone; `read.pages`): the
  viewer lays pages out in rows (`rows`, `layout.tops / lefts`); Fit Width fits a whole row;
  ← / → step by row (`stepRow`); switching keeps the place.
- **EPUB** (and other e-books MuPDF reads): opened like PDFs, laid out on an A5-like page with the
  Read menu's **E-book text size** (`epub.fontsize`, `MuPdfEngine.reflow`); changing it lays open
  books out again in place (`epub_text_size` → `phdf:reflow` → `Tab.reflow`). E-books keep no
  annotations: the annotation tools are hidden (`tab.isBook`); copy, cite, Ask AI, notes,
  search, AI Markdown (`to_bytes` converts to PDF) work.
- **Book view** (Read → Read like a book, `read.book`, `focus/BookView.svelte`): one spread of two
  pages filling the window (cover alone if Pages says so), bottom-corner turn buttons, ← / → /
  Space, a short slide; Esc returns to the normal view at the same page.
- **Note zoom menu**: click the % in the note's status line: slider, presets, reset.
- **App icon** from the owner's `logo.png`: `packaging/make_icons.py` makes `packaging/icons/`
  (`phdf.ico` for the exe + window, `phdf.icns` for the Mac app, `phdf.png` for Linux) and
  `frontend/src/assets/logo.png` (start screen, tutorial). Rerun it after changing the logo.
  pywebview's `start(icon=…)` is used on Windows too and needs the `.ico` there.
- **Menus close on any outside press** (`lib/outside.ts`, toolbar `data-menu` wrappers, note and
  terminal **Aa**). The terminal's **Aa** no longer folds the panel.
- **#14 PDF right-click** (`annot/ContextMenu.svelte`, `Viewer` `oncontext`): on an annotation:
  Edit, colour, Copy Text, Note in MD / Go to Pin, Delete; on selected text: the selection menu;
  on an empty spot: Add Note / Text Here, Bookmark, Copy Page as Image, Ask AI About This Page
  (typed, not sent), Park a Thought.
- **#15 Note format bar + right-click** (`md/format.ts` commands, `md/FormatBar.svelte`,
  `md/EditorMenu.svelte`): bold / italic / strike / highlight / code / math / comment, clear,
  link, paragraph style (body, H1-6, quote, lists, tasks), insert (footnote, table, callout, rule,
  code / math block), cut / copy / paste / paste as plain text. Ctrl+B / Ctrl+I in the note.
  The bar's grip drags it to any side (`md.formatBar` setting). Preview now renders `==mark==`
  and hides `%%comments%%`; footnotes and callouts render as plain text until #12.
- **#16 Ask AI from a note**: in the note's right-click menu, same presets as the PDF; the
  selection as a quote, or the whole note file when nothing is selected.
- **#17 Terminal (owner)**: header button **Go to the PDF's folder** (`cd` / `Set-Location`;
  if an AI runs in that tab, a new tab opens there instead) and **Aa**: font (Cascadia Mono,
  Consolas, bundled JetBrains Mono, Courier New, SF Mono / Menlo, DejaVu) and size 9-28,
  remembered (`terminal.font`).
- **Agent start (owner)**: before any agent starts, the shell `cd`s to the open document's folder
  (sessions are per folder), then a bar at the bottom asks **Continue last session** (`claude
  --continue`, `codex resume --last`) or **New session**; agents without a known flag start
  directly. Flags in `RESUME` (`terminal.svelte.ts`); verify them when the CLIs update.

Also open:
- **Owner to test v0.5.8 by hand**: slow text selection (across lines, backwards, into the
  margin); terminal tabs (+, ×, Ask AI while an AI runs in another tab); the *Add an AI agent*
  card (first open); a + tab asks which installed agent to start (or just the shell); Settings → AI (agent, cache, Clear); the
  toolbar after its move to `Toolbar.svelte` (menus, search Ctrl+F, go to page Ctrl+G, narrow
  window folding into ⋯).
- Equation converter not yet tried with real Claude Code / Codex (permission prompts, image
  reading). CI on GitHub: check Windows is green and what macOS / Linux report.

**Phase 7, PDF tools: built 2026-10-16 (v0.6.0, not yet tested by the owner):**
- **Entry**: a big, shiny **PhDF TOOLS** button on the welcome / new-tab screen (next to Open);
  also ⋯ → "PDF Tools…" and the palette for the open PDF. Opens a tools view: pick a PDF, then a
  grid of page thumbnails (click / Shift / Ctrl to select, drag to reorder, right-click actions).
- **Tools**: rotate left / right (real rotation, saved in the file), delete, duplicate, insert a
  blank page, reorder (drag), insert another PDF (merge), extract selected pages, split (every N
  pages / at chapter starts / at the selected pages). Undo while editing. Crop: later.
- **Saving: always a copy**, never the original: `<name>_phdfE.pdf` next to it (`_phdfE_2` … if
  it exists). Extract / split: `<name>_p_3-7_phdf.pdf` (ask where for extract, offer Open).
- **Annotations**: if the pages written have annotations, ask: keep them in the new file or
  remove them. **No updating** of note pins, bookmarks or positions (the result is a new file).
- Built as planned: `services/pdftools.py` (`ToolsSession`: original bytes + operations; undo
  = replay without the last), `Api.tools_*`, `lib/PdfTools.svelte` (full-window view, opened via
  `ui.tools`). Session ids are 64 hex so `RenderServer` serves thumbnails. Crop: not yet.

Done in v0.7.0 (2026-10-17, not yet tested by the owner):
- **Tutorial**: shorter cards about what PhDF is good for, each with a **Details: how to use
  it** button that opens a scrolling step-by-step list inside the card (`Help.svelte`).
- **Window on a disconnected monitor**: `app.on_screen()` checks a saved position against the
  connected monitors; off-screen positions are dropped at start (window centered), and
  un-maximizing onto a missing monitor moves the window to the main screen.
- **Note text width**: the note's % menu (status line) has a Text width slider and Narrow /
  Wide / Full; range 480-1600 px, the max = **Full** (`--md-width: none`), default now 900 px.
- **Enlarged link preview** moves by its header too (`sheetMoved` in `LinkPeek.svelte`).
- **Dragging a tab out = undocking** (like MATLAB): a smaller window with just that document
  (id starts with `d`, title `<file> - PhDF`, size not remembered). Its toolbar has **Dock**
  (`Api.dock`: tabs go to a main window, a new one if none is open), it closes with its last
  tab, and at the next start its tabs are merged into the main window (`saved_window_ids`).
  Dropping onto another PhDF window still moves the tab there; an undocked window's only tab
  can be dragged back that way (dropped elsewhere it stays).
- **Sidebar for standalone notes** (`md/MdSidebar.svelte`, same Ctrl+\ toggle): **Contents**
  (the note's `#` headings, click to jump, also in Preview via `MdDoc.reveal.heading`) and
  **Files** (the other `.md` notes in its folder, `Api.md_files`, without `.parking.md` /
  `.grades.md`). Its tab is remembered in the `sidebar` setting (`mdMode`).
- **Web links never take over the app window**: a document-level click handler in `App.svelte`
  sends `http(s)` links (notes' Preview, anywhere in the UI) to `peek_url(url, large=True)`: a
  movable, on-top native window at 80 % of the app window. Every web preview gets a bar on top
  (`services/webpeek.py`: Back, Open in Browser, close) injected after each load; the page's
  only JS API is `PeekBridge` (those two actions), never `Api`.
- **From the research list (easy items)**:
  - **Bookmarks in the palette** (Ctrl+K lists the focused PDF's bookmarks; loaded when it opens).
  - **Reading spot saved on close**: the viewer used to *cancel* its pending 400 ms position save
    when a tab closed; now it writes it (`flushPosition`, also on `pagehide`).
  - **Password-protected PDFs**: `engine.open(path, password)` raises `PasswordRequired`;
    `open_document` answers `{needsPassword, wrong}` and the app asks (sheet). Passwords live
    in `Core.passwords` for the session only (also used to reopen after a full save). PDF
    Tools, export and AI Markdown open files themselves and don't handle encrypted PDFs yet.
  - **Print** (Ctrl+P, ⋯ menu, palette; `PrintSheet.svelte`): all / current / range, pages
    rendered at 150 DPI into a print-only `#phdf-print` layer, then `window.print()` (annotations
    as shown, saved or not; max 500 pages). macOS (WKWebView has no print): opens the PDF in
    Preview via `open_in_default_app`.
  - **Save Page as Image…** (right-click a page): PNG or JPEG at about 200 DPI (`page_image`).
  - **Library**: × on a cover removes it from the Library (file untouched, `library_remove`);
    a missing file's cover is **find file…** (`library_relink`, accepts only the same content
    hash so bookmarks and history stay right).
  - **Settings → About**: versions, OS, web view, data folder, database / cache sizes, OCR
    languages and the last 20 error toasts (`notify.recent`); **Copy for a Bug Report**.
  - **Keyboard**: no global shortcut while a dialog (password, save, print, Settings) is open;
    Ctrl+F / G / zoom / Alt+arrows / Ctrl+Shift+C no longer act on the PDF while typing in a
    field or note.
  - **Fewer animations** (Settings → Appearance, `ui.reduceMotion`, default = the OS setting):
    a `reduce-motion` class stops CSS animations / transitions; Help and book view slide with
    duration 0.
- **More settings** (Settings sheet):
  - **Theme** System (default) / Light / Dark (`theme.svelte.ts`, setting `ui.theme`):
    `data-theme` on `<html>`; `app.css` has the dark tokens twice (OS dark unless
    `data-theme="light"`, and `[data-theme="dark"]`). Theme changes fire `phdf:theme` (title
    bar, terminal colors). **Dark pages automatically** (`autoDarkPages`) sets the moon state
    with the theme.
  - **Interface size** 90 / 100 / 110 / 125 %: the web view's own zoom (`services/uizoom.py`:
    WebView2 `ZoomFactor`, WKWebView `pageZoom`, WebKitGTK zoom level), not CSS zoom, so
    coordinates stay consistent. Applied per window at start (`loadPrefs`).
  - **General**: reopen last tabs (`session.restore`, read by `saved_window_ids` too: off =
    one window, no tabs), scroll speed Slow / Normal / Fast (the viewer scales wheel deltas;
    Normal leaves scrolling to the browser), closing with unsaved marks: Ask / Save automatically
    (`askSave`). Stored in `prefs` (`prefs.svelte.ts`).
  - **Focus timer**: focus and break length, chime on/off, volume, Test.
  - **Toolbar buttons**: right-click the toolbar to tick which buttons show
    (`prefs.toolbarHidden`; sidebar and ⋯ always stay; Show All).
**v1.0** when Phases 0-5.5 and 7 are stable on all three OSes.

**Upcoming (unscheduled):** `phdf://` deep links from Obsidian; send to the currently open
Obsidian note (Local REST API plugin); double-click a word → AI explains it; Turkish UI.
Smaller leftovers: two-way note ↔ vault sync, OCR of a selected area, password-protected PDFs,
rotated text in the text layer. (Window frame: kept native, colored like the toolbar via DWM, `services/titlebar.py`; owner chose this over a frameless window.)

**Ideas:** tags / collections / full-text search across PDFs, Zotero / BibTeX, sync through a
folder, flashcards from highlights, text-to-speech, translation, dual-page mode, EPUB / XPS /
CBZ, plugins, mobile companion.

## Performance, reliability and cleanup: future work

Expansion research and preparation: [FUTURE_EXPANSION_RESEARCH.md](FUTURE_EXPANSION_RESEARCH.md)
(2026-10-16). Covers improvements to existing features, 18 proposed additions, architecture,
validation, dependencies, and sources. Proposals are not implementation commitments.

Code review 2026-10-16. Backlog only; no implementation changes made. Prioritize data loss
and wrong-file saves before optimization. Baseline: 80 Python tests passed, 1 skipped;
Svelte check, Ruff lint/format and frontend build passed (large editor chunk warning).
Reproduced items are marked below; other findings are from static inspection and need
focused regression coverage plus desktop interaction checks.

### Reliability bugs
- **P1, reproduced: identical PDF copies share a writable document.** `Core.acquire` keys
  instances by content hash, so opening A.pdf then identical B.pdf and saving edits through
  B's returned id writes A. Separate writable file identity from content/history identity.
- **P1: window close can lose recent note edits.** `Api._on_closing` only holds closure for
  dirty PDF annotations; Markdown-only edits can miss the awaited frontend flush. Always
  await note persistence before closing, including parking notes and grading state.
- **P1: shared PDF, independent frontend edit state.** `App.openBeside` and other windows
  create separate Tab annotation lists, dirty flags, revisions and undo stacks for the same
  backend document. Share edit state or broadcast changes to every view.
- **P1, reproduced: rejected Tools operation leaves rendering on a closed document.**
  `ToolsSession.apply` rebuilds on failure, but `Api.tools_apply` only reattaches the renderer
  on success. Deleting all pages triggers it. Reattach on error too.
- **P1: Tools extract permits the source as destination.** Reject the source path/file identity
  in the backend to enforce the promise that the original is never overwritten.
- **Tools Change PDF discards unsaved changes.** `PdfTools.openFile` closes the old session
  without confirmation; failure opening its replacement leaves stale UI state. Confirm first
  and acquire the replacement before releasing the old session.
- **Tools undo after Save Copy leaves saved=true.** Track the saved history position.
- **Competing note writers.** Integrated/standalone notes and windows can hold separate MdDoc
  buffers and queues for one file, sharing a fixed `.phdf-tmp` filename. Share note ownership
  and serialize backend writes per normalized path; handle conflicting buffers explicitly.
- **External note reload can replace newly typed edits.** `MdDoc.checkExternal` checks dirty
  only before awaited I/O; verify an edit generation before applying the loaded text.
- **Two-page visibility excludes the right page of the last live row.** `Viewer.pageAt`
  returns a row's first page; expand liveRange's end to include the whole row.
- **Viewer teardown cancels the pending position save.** Flush the latest location before
  clearing the 400 ms timer so rapid tab changes preserve reading position.
- **Book view consumes typing keys and ignores links.** Its capture handler needs editable
  target checks; PageView's empty onlink callback needs the normal preview/navigation flow.
- **Tools merge undo reopens external files.** Snapshot inserted PDF bytes instead of relying
  on an unchanged source path during replay.
- **Reproduced: render cache overcounts replacement entries.** `_remember` adds new bytes
  without subtracting the prior entry. Concurrent misses can trigger this. Correct accounting
  and combine concurrent requests for the same image.
- **AI Markdown job registration races.** Status checking and registration are separate;
  duplicate workers can write the same `.part`. Register atomically and define active-job
  behavior when saving changes the document/cache identity.

### Follow-up bug search (2026-10-16)
- **Reproduced: discarded OCR survives in AI context.** OCR, create AI context, close without
  saving, reopen: the disk/text layer is original but AI context still contains unsaved OCR.
  `Core.release` keeps text_revs and the matching cache file. Invalidate discarded text/cache
  identity without accidentally reusing a previous unsaved revision on subsequent OCR.
  Reproduction used a stub recognizer/converter to isolate lifecycle behavior.
- **Reproduced: EPUB reflow leaves AI page context stale.** After changing text size from 11
  to 24, a fixture grew from 3 to 16 pages, but ai_context reused the original page-1 file
  without converting again. Cache identity must include layout, because page boundaries change.
  Converter was stubbed to extract actual page text for this check.
- **EPUB reflow leaves other windows stale.** Backend relayout changes the shared document;
  only the initiating frontend receives new page sizes/revisions. Broadcast to all views.
  `Tab.reflow` also leaves the cached outline/back-forward destinations and per-page text
  presence state at the old pagination; invalidate/remap these too.
- **P1: native window close bypasses Tools' unsaved confirmation.** Tools wrappers report
  dirty=false even after operations, and `_has_unsaved` only checks normal opened documents.
  Clicking the OS close button can lose Tools work without its save/cancel dialog. Include
  Tools state in the window close protocol, not only the Tools panel's Close button.
- **P1: typed grades are not committed on window close or Ctrl+S.** Grade/identification
  inputs live in GradingSession fields; closing flushes MdDocs but does not call commit/leave,
  and Tab.save does not commit them either. Persist pending grading inputs before either path.
- **Grading marks an exam Done before saving succeeds.** `GradingSession.next` updates done
  before show/leave saves. Save failure leaves the current exam marked complete; a later
  progress write can persist it. Mark complete only after successful persistence.
- **Markdown preview links use default webview navigation.** `MdEditor.onPreviewClick` only
  handles pins and does not intercept ordinary anchors. Route external links through the
  existing open_external API, retain in-note fragment navigation, and define relative-link
  handling so clicking a note link cannot navigate away from the app shell.

### Performance investigations (costly paths identified, desktop impact not benchmarked)
- Search scans pages while holding the global Core lock, blocking rendering in every window.
  Use a safe snapshot or cancellable batches; avoid running obsolete queued searches.
- `PdfDocument.page_sizes` visits all pages during open under the shared lock, contrary to the
  large-document guidance below. Investigate cached/progressive page dimensions.
- Tools split serializes the whole document for every part under the global lock. Copy only
  required pages into each output, with link/annotation preservation verified.
- Sidebar and Tools thumbnail grids create DOM nodes for every page. Virtualize them.
- Live Markdown math reparses the entire note per edit; repeated block membership checks add
  work in equation-heavy notes. Investigate incremental parsing.
- MuPDF's store is emptied every four renders (`store_shrink(100)`). Benchmark a less
  aggressive policy against scanned-book memory before changing it.

### Cleanup candidates
- README is stale: v0.5.8 status; Tools and icon still listed as upcoming.
- Consolidate duplicate PDF edit state and note ownership before deleting isolated code.
- Prefer Markdown parser extensions to preprocessing regexes: footnotes currently process
  code-block contents too (`md/render.ts`). Add representative rendering checks.
- Investigate WOFF2-only assets and loading selected font families while retaining language
  coverage. The frontend build emits many font formats/subsets.
- Split `api.py` into feature services with a thin bridge and explicit lock ownership.
- No whole feature module/dependency was established as unused; do not delete by guesswork.

## Gotchas (read before changing related code)
- **Windows `.js` MIME**: `fix_mimetypes()` in `app.py` must stay (else a blank window).
- **TypeScript pinned to 5.x** (svelte-check). **pymupdf4llm pinned to 0.3.x** (1.x pulls a
  +70 MB layout model).
- **Threads**: pywebview calls the API on worker threads; MuPDF is not thread-safe → all engine
  access under `core.lock`; slow work (OCR recognition, Markdown conversion on `to_bytes()`
  copies) runs outside it. `Store` serializes its one SQLite connection.
- **pywebview exposes every public attribute** of `Api` → internals are `_private`. Web link
  previews get only `webpeek.PeekBridge` (open in browser, close), never `Api`.
- **Page images** come from `RenderServer` (127.0.0.1, random port + token), not the bridge;
  URLs carry `&r=<rev>`; `Core` bumps per-page revisions on every change. Revisions restart at 0
  each launch (so `r<rev>` in AI cache names can't be compared across launches).
- **Big PDFs**: never loop over all pages on open; annotations are read only from pages with
  `/Annots`; `Core.render` trims MuPDF's cache.
- **Annotations**: own 5-char `/NM` ids (MuPDF's `fitz-…` are unstable; others get `x<xref>`).
  Dirty state is ours (PyMuPDF's `is_dirty` stays set). Free-text colour is in `/DA`. Free text
  is rich text (`/DS` CSS) since v0.5.7 and is **re-created** (same id) on every change; never
  keep a `pymupdf.Annot` after its page object is gone (segfault).
- **OCR** words use a system TTF so Turkish letters extract; Helvetica turns them into "?".
- **Text layer**: spans positioned in PDF points, stretched with `scaleX`, `<br>` per line; the
  `.end-of-content` box (v0.5.8) keeps slow selections from jumping to the page end.
- **Position** = page + 0..1 offset within it (survives zoom / resize).
- **Tab drag & drop** uses pointer events + capture, not HTML5 DnD. Session format
  `{panes: [{paths, active, width}], focused}` per window (`session.<windowId>`). Window ids
  starting with `d` are detached (undocked) windows: never restored as windows, see `dock`.
- **`MdDoc.flush()` is queued** (two writes raced on the `.phdf-tmp` file). Grading shares one
  `MdDoc` across exam tabs (`attachNote` / `detachNote`).
- **Menus inside the toolbar / note header**: `backdrop-filter` and container queries make
  `position: fixed` relative to that bar, so a full-screen backdrop div only covers the bar. Close
  such menus with `outsideClose()` (`lib/outside.ts`) or a document `pointerdown` listener.
- **Mixed-DPI monitors (Windows)**: pywebview makes the process *system* DPI aware, so on a monitor
  with other scaling Windows stretches the window (blurry, and edge pixels let clicks reach the
  window behind: the owner's 150 % + 100 % setup closed Chrome via PhDF's top-right corner).
  `app.per_monitor_dpi()` sets Per-Monitor-V2 before any window (setting `window.perMonitorDpi`,
  Settings → Appearance, default on). Not confirmed by the owner yet; a script can't bring a
  test window to the front, so the corner couldn't be verified automatically.
- **Closing a window from JS** (`close_window`): destroy it a moment later, so pywebview can
  return the call's result first (else "Cannot access a disposed object" in the console).
- **Platform differences** live in `lib/platform.ts` (`kbd()`, `copyText()`, `isMac`).
- **Equation temp files**: only `.phdf-tmp/eq-*` are deleted; `term_start` cleans leftovers > 1 h.
- **Screenshots of the app**: use `PrintWindow(..., PW_RENDERFULLCONTENT=2)`; don't force focus.
- **Windows shell**: write long Python snippets to a script file (quoting breaks); write files as
  UTF-8 explicitly. **Line endings**: the repo is LF (`.gitattributes`), but some editors (and
  Claude's Edit tool here) save CRLF; convert changed files back (`sed -i 's/\r$//'`).
- **Dev mode**: `npm --prefix frontend run dev` + `PHDF_DEV=1 uv run phdf` (or `.env`);
  `PHDF_DATA_DIR` overrides the data folder.
