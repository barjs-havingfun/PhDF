# PhDF test checklist (v0.7.0)

Tick each item when it works (` [x]`). Write what went wrong under an item when it doesn't.
Open this file in PhDF itself: the checkboxes are clickable in **Live** or **Preview** mode.

Prepare: a normal PDF with text, a scanned PDF (no text), a big book (300+ pages), an `.epub`, a PDF with an outline (chapters) and links, and an Obsidian vault folder.

## 1. Start and window
- [x] `uv run phdf` starts; the first start shows the tutorial cards by itself (only once)
- [x] Title bar has PhDF's color (light / dark follows Windows); window corners are square
- [x] Window size and position are remembered after closing and reopening
- [ ] With a second monitor unplugged: PhDF opens on the main screen, and making a maximized window smaller keeps it on screen
- [x] F11 full screen: clicking the top-right corner does **not** close the app behind
- [x] Settings → Appearance: changing the app font (System / Inter / Atkinson / Literata) changes the whole UI

## 2. Opening, tabs and panes
- [x] Open… opens a PDF, an `.epub` and a `.md`; the start screen lists recent files and the Library
- [x] Ctrl+T new tab, Ctrl+W close, Ctrl+Tab next tab
- [x] Drag a tab to reorder; drop it on the left/right edge of a document for side-by-side panes (max 3)
- [x] Drag a tab outside the window → a smaller undocked window with just that document (named after it); onto another PhDF window → moves there
- [ ] Undocked window: **Dock**, or dragging its tab onto the main window, puts the tab back; closing its last tab closes it; after a restart its tabs are in the main window
- [x] Closing and reopening PhDF restores the open tabs and the page you were on
- [x] Reopening a document shows "Where was I?" and it disappears after ~6 seconds

## 3. Reading and navigation
- [x] Scrolling is smooth; zoom with Ctrl+wheel / touchpad pinch (small moves = small changes)
- [x] Zoom menu (click the %): slider, typed % + Enter, 50–200 % buttons, Fit Width / Fit Page / Actual Size
- [x] Ctrl+G go to page; ← / → previous / next page; Home / End; Alt+← / Alt+→ back / forward
- [x] Sidebar (Ctrl+\): outline, thumbnails, bookmarks; Ctrl+B bookmarks a page (red ribbon)
- [x] Ctrl+F search: hits highlighted, Enter / Shift+Enter step through them
- [x] Clicking an internal link shows the preview card; drag it by its top bar; Enlarge / Go to Page / Open Beside; the enlarged preview can be dragged by its top bar too
- [x] In the link preview: right-click selected text (copy, highlight, note, Ask AI) and on the page (bookmark, copy as image)
- [x] Dark pages (moon button) works

## 4. Text selection and highlights
- [ ] Selecting text **slowly** does not jump to select the whole page
- [ ] Selection menu: 5 highlight colors, underline, strikethrough, copy, copy with citation (Ctrl+Shift+C)
- [ ] Right-click on selected text opens the same menu at the pointer
- [ ] Note in MD: adds a highlight + a pin in the note, cursor under it; pin → "Go to PDF" jumps back
- [ ] Ctrl+S saves the annotations into the PDF ("- Edited" disappears); closing unsaved asks Save / Don't Save / Cancel
- [ ] Ctrl+Z / Ctrl+Y undo / redo highlights, deletes, moves

## 5. Notes, text boxes and drawing (toolbar)
- [ ] Sticky note: click on the page, write, it stays; drag it to move
- [ ] Text box: font Sans / Serif / Mono, size, bold; click it later to change; drag to move
- [ ] Draw: the line follows the pen **instantly**; after release it does not blink away; pen color and width bar
- [ ] Annotations panel lists everything by page; click jumps; filter and search work
- [ ] Right-click an annotation: Edit, colors, Copy Text, Copy Comment (highlights with a comment), Go to Pin, Delete
- [ ] Right-click an empty spot: Add Note / Text Here, Bookmark, Copy Page as Image (paste it somewhere), Ask AI About This Page, Park a Thought

## 6. The note (integrated .md)
- [ ] The note button opens `<pdf name>.md` beside the PDF; typing autosaves ("Saved ✓" in the status line)
- [ ] Edit / **Live** / Preview: Live hides the Markdown marks except on the line you edit; the choice is remembered
- [ ] Live shows `$x^2$` and `$$…$$` as equations; clicking one shows its LaTeX
- [ ] Live: `- [ ]` tasks are clickable checkboxes; `==mark==` is highlighted; `%%comment%%` is dimmed
- [ ] Format bar: every button works (bold, italic, strike, highlight, code, math, comment, clear, link, lists, quote, Insert…, clipboard)
- [ ] Paragraph style menu: Text, Heading 1–6, Quote, lists
- [ ] Drag the format bar's grip to the bottom / left / right; it stays there next time
- [ ] Shortcuts in the note: Ctrl+B, Ctrl+I, Ctrl+E, Ctrl+Shift+K (link), Ctrl+Shift+X, Ctrl+Shift+H; **Ctrl+K still opens the command palette**
- [ ] Right-click in the note: cut / copy / paste / paste as plain text, Format ›, Paragraph ›, Insert ›, Ask AI ›
- [ ] Zoom the note: Ctrl+wheel, Ctrl+= / −, and the % menu in the status line (slider, presets, reset)
- [ ] Click the file name at the top to rename it; the note still opens with its PDF afterwards
- [ ] Link an existing .md: it first explains what happens, then lets you choose the file
- [ ] Preview looks good: headings, pin cards, callouts `> [!tip]`, footnotes `[^1]`, tables, code blocks
- [ ] Aa: note font, size, spacing, width
- [ ] A web link in a note's Preview opens a large preview window (movable, scrollable) over PhDF, not inside the app; its top bar: Back, Open in Browser (opens the current page), ✕
- [ ] A standalone `.md` tab: the sidebar button (Ctrl+\) opens Contents (headings, click jumps, also in Preview) and Files (other notes in its folder, click opens)
- [ ] The % in the note's status line: text size, and Text width (slider, Narrow / Wide / Full); Full fills the whole note pane
- [ ] Note | Parking tabs: parked thoughts show there with a badge

## 7. Read & Focus
- [ ] Read menu: ✕ closes it; clicking outside closes it
- [ ] **Read like a book**: two pages fill the window, round buttons bottom left/right, ← / → / Space, slide animation, "✕ Close" (and Esc) returns to the same page
- [ ] Pages: Single / Two pages / Cover alone change the normal view; ← / → move by a spread; Fit Width fits both pages
- [ ] Reading ruler (S / M / L), Zen mode (Ctrl+. / Esc), page tints
- [ ] Focus: pomodoro runs and chimes; time left for the chapter / document appears after some reading
- [ ] Park (Ctrl+Shift+Space): type, Enter, back to reading; it appears in the Parking tab
- [ ] Library and reading stats on the start screen update after reading

## 8. E-books (EPUB)
- [ ] An `.epub` opens, reads, searches; the outline shows chapters
- [ ] Read → E-book text size A− / A+: pages are laid out again, you stay at about the same place
- [ ] Highlight / note / draw tools are hidden for e-books; copy, citation, Ask AI and the note still work

## 9. AI terminal
- [ ] Ctrl+` opens the terminal; the first time it asks for your agent (Claude Code / Codex / Gemini CLI / other / just the shell)
- [ ] Before the agent starts, the terminal goes to the PDF's folder and asks **Continue last session / New session**
- [ ] Claude: Continue runs `claude --continue`; Codex: `codex resume --last`
- [ ] + opens a new terminal tab with a plain shell and the "Start in this terminal" bar at the bottom; it disappears after your first Enter
- [ ] × closes a tab; the others keep running
- [ ] Folder button moves the terminal to the PDF's folder (opens a new tab if an AI runs there)
- [ ] Aa: terminal font and size (also in Settings → AI); menu closes when clicking outside, panel does not fold
- [ ] ⇅ puts the terminal below / above the note; dock at the bottom and back; drag the header; fold it by clicking
- [ ] Agent button in the header changes the default agent ("applies the next time a terminal opens")
- [ ] How to: install steps for Claude Code, Codex, Gemini CLI on your OS

## 10. Asking the AI
- [ ] Select text → Ask AI: Explain / Summarize / Translate are sent; My own question… is only typed
- [ ] ✦ menu: summarize document / chapter, explain page, key ideas, study questions, **Find similar research**, own question
- [ ] ✦ menu → Read as Markdown: progress while preparing; on = AI reads the Markdown copy; off = AI opens the PDF; big PDFs start off
- [ ] Ask AI from a note (right-click → Ask AI): selection, or the whole note when nothing is selected
- [ ] ▾ next to ✦ → Equation → LaTeX: draw a box, **OK**, the AI answers, Insert puts `$$…$$` into the note
- [ ] Settings → AI: cache size shown; Clear AI cache works

## 11. PhDF Tools
- [ ] The shiny **PhDF TOOLS** button (start screen), ⋯ → PDF Tools…, and the palette open it
- [ ] Select pages: click, Shift-click, Ctrl-click, Ctrl+A; drag pages to reorder (blue line shows where)
- [ ] Rotate left / right, duplicate, delete (also Delete key), blank page, insert another PDF; Ctrl+Z undoes
- [ ] Right-click a page: the same actions
- [ ] Save Copy writes `Name_phdfE.pdf` (then `_phdfE_2`), the **original is unchanged**; Open works
- [ ] Extract… asks where, suggests `Name_p_3-7_phdf.pdf`
- [ ] Split: every N pages, at the selected pages, at chapters → `Name_p_1-10_phdf.pdf` …
- [ ] Pages with annotations: asks Keep Them / Remove Them / Cancel
- [ ] Closing with unsaved changes asks Save Copy / Close Without Saving / Cancel

## 12. OCR, export, Obsidian, grading
- [ ] Scanned page: "This page has no text" bar → Recognize Text; then text can be selected and searched; Ctrl+S keeps it
- [ ] ⋯ → Export as Markdown / Export Highlights to Note / Export to Obsidian Vault
- [ ] Settings → Obsidian vault; selection → Send to Obsidian; Copy Note to Obsidian
- [ ] Grade button: pick a folder of exams; Prev / Done; grades table; Export CSV; originals untouched (`graded/` folder)

## 13. Everywhere
- [ ] Ctrl+K command palette finds actions, recent files, "Go to page N", "Search …"
- [ ] Every dropdown (Read, Focus, zoom, ✦, ⋯, Aa menus, format bar menus) closes when clicking outside it
- [ ] ? opens the tutorial cards: big, frosted, slide left / right; ← / → change cards **without** turning the PDF page
- [ ] Each card's **Details: how to use it** opens a scrolling how-to inside the card; clicking in it does not flip the card; changing cards closes it
- [ ] Toolbar, tabs and page area look seamless (no line between them)
- [ ] Light and dark Windows themes both look right

## 14. New: from the research list
- [ ] Ctrl+K: the focused PDF's bookmarks are listed (name and page); choosing one jumps there
- [ ] Scroll somewhere, close the tab within a second, reopen: it opens at that spot
- [ ] A password-protected PDF asks for its password; a wrong one says so; the right one opens it; Ctrl+S keeps it protected
- [ ] Ctrl+P (or ⋯ → Print…): All / Current page / range; the system print dialog shows the pages with annotations (Mac: opens in Preview)
- [ ] Right-click a page → Save Page as Image…: PNG or JPG, sharp
- [ ] Library: hover a cover → × removes it from the Library (file stays); a missing file → click → choose the moved file → it works again; a different PDF is refused
- [ ] Settings → About shows versions and sizes; Copy for a Bug Report copies it
- [ ] While typing in a note or a field: Ctrl+F, Ctrl+G, Ctrl+= / -, Alt+← do not act on the PDF; with Settings open, arrows don't turn pages
- [ ] Settings → Appearance → Fewer animations: tutorial cards and book view change without sliding; menus don't fade
- [ ] Settings → Theme: System follows Windows; Light and Dark override it (toolbar, menus, notes, terminal, title bar)
- [ ] Dark pages automatically: switching to Dark turns pages dark, Light turns them back
- [ ] Interface size 90 / 110 / 125 %: everything scales; selecting text and highlighting still hit the right words
- [ ] Reopen my last tabs off: the next start is an empty window; on: tabs come back
- [ ] Scroll speed Slow / Fast changes how far the wheel moves the page; Normal feels like before
- [ ] Closing with unsaved marks = Save automatically: closing a tab or the window saves without asking
- [ ] Focus timer settings: lengths, chime on/off, volume and Test
- [ ] Right-click the toolbar: untick a button and it disappears; Show All brings everything back; kept after restart
