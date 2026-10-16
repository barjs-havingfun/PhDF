# PhDF - Handoff

> Status: **v0.6.0** (2026-10-16). Repo: github.com/barjs-havingfun/PhDF; the owner commits and
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
**v1.0** when Phases 0-5.5 and 7 are stable on all three OSes.

**Upcoming (unscheduled):** `phdf://` deep links from Obsidian; send to the currently open
Obsidian note (Local REST API plugin); double-click a word → AI explains it; Turkish UI; app icon
(owner designs a 1024×1024 PNG → `.ico` / `.icns`, wire into `phdf.spec` and the window).
Smaller leftovers: two-way note ↔ vault sync, OCR of a selected area, password-protected PDFs,
rotated text in the text layer, frameless window with Mac traffic lights.

**Ideas:** tags / collections / full-text search across PDFs, Zotero / BibTeX, sync through a
folder, flashcards from highlights, text-to-speech, translation, dual-page mode, EPUB / XPS /
CBZ, plugins, mobile companion.

## Gotchas (read before changing related code)
- **Windows `.js` MIME**: `fix_mimetypes()` in `app.py` must stay (else a blank window).
- **TypeScript pinned to 5.x** (svelte-check). **pymupdf4llm pinned to 0.3.x** (1.x pulls a
  +70 MB layout model).
- **Threads**: pywebview calls the API on worker threads; MuPDF is not thread-safe → all engine
  access under `core.lock`; slow work (OCR recognition, Markdown conversion on `to_bytes()`
  copies) runs outside it. `Store` serializes its one SQLite connection.
- **pywebview exposes every public attribute** of `Api` → internals are `_private`. Web link
  previews open in a window **without** `js_api`.
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
  `{panes: [{paths, active, width}], focused}` per window (`session.<windowId>`).
- **`MdDoc.flush()` is queued** (two writes raced on the `.phdf-tmp` file). Grading shares one
  `MdDoc` across exam tabs (`attachNote` / `detachNote`).
- **Menus inside the toolbar / note header**: `backdrop-filter` and container queries make
  `position: fixed` relative to that bar, so a full-screen backdrop div only covers the bar. Close
  such menus with `outsideClose()` (`lib/outside.ts`) or a document `pointerdown` listener.
- **Platform differences** live in `lib/platform.ts` (`kbd()`, `copyText()`, `isMac`).
- **Equation temp files**: only `.phdf-tmp/eq-*` are deleted; `term_start` cleans leftovers > 1 h.
- **Screenshots of the app**: use `PrintWindow(..., PW_RENDERFULLCONTENT=2)`; don't force focus.
- **Windows shell**: write long Python snippets to a script file (quoting breaks); write files as
  UTF-8 explicitly. **Line endings**: the repo is LF (`.gitattributes`), but some editors (and
  Claude's Edit tool here) save CRLF; convert changed files back (`sed -i 's/\r$//'`).
- **Dev mode**: `npm --prefix frontend run dev` + `PHDF_DEV=1 uv run phdf` (or `.env`);
  `PHDF_DATA_DIR` overrides the data folder.
