<script lang="ts">
  // App shell: toolbar, sidebar, side-by-side panes with tabs (PDFs and Markdown notes), tab drag
  // & drop, link peek, saving annotations, keyboard shortcuts and per-window session restore.
  import { kbd, copyText } from "./lib/platform";
  import { onMount } from "svelte";
  import {
    api,
    setRenderBaseUrl,
    type AppInfo,
    type FitMode,
    type PdfLink,
    type RecentDocument,
  } from "./lib/api";
  import { capture, drag, startTabDrag, type DropTarget } from "./lib/dnd.svelte";
  import Icon from "./lib/Icon.svelte";
  import { notify, ui } from "./lib/notify.svelte";
  import { ocrLanguages } from "./lib/ocr";
  import Settings from "./lib/Settings.svelte";
  import Help from "./lib/Help.svelte";
  import AiPanel from "./lib/ai/AiPanel.svelte";
  import DocAiMenu from "./lib/ai/DocAiMenu.svelte";
  import CommandPalette, { type Command } from "./lib/CommandPalette.svelte";
  import { citation } from "./lib/cite";
  import { loadInk, loadTextStyle } from "./lib/tab.svelte";
  import TerminalGuide from "./lib/ai/TerminalGuide.svelte";
  import { HEADER_HEIGHT, closeTerminal, loadLayout, openTerminal, saveLayout, term } from "./lib/ai/terminal.svelte";
  import FocusMenu from "./lib/focus/FocusMenu.svelte";
  import ParkingLot from "./lib/focus/ParkingLot.svelte";
  import ReadMenu from "./lib/focus/ReadMenu.svelte";
  import {
    clock,
    loadPace,
    loadPomodoroSettings,
    flushReading,
    loadReadSettings,
    noteActivity,
    pausePomodoro,
    saveReadSettings,
    startPomodoro,
    TINTS,
    type Tint,
    notePage,
    tickReading,
    pomodoro,
    read,
  } from "./lib/reading.svelte";
  import LinkPeek, { type Peek } from "./lib/LinkPeek.svelte";
  import PaneView from "./lib/PaneView.svelte";
  import Sidebar, { type SidebarMode } from "./lib/Sidebar.svelte";
  import { GradingSession, grading, loadGradingSettings, type Host } from "./lib/grading/grading.svelte";
  import { MdDoc } from "./lib/md.svelte";
  import type { Pin } from "./lib/pin";
  import { MdTab, Tab, type AnyTab } from "./lib/tab.svelte";
  import type Viewer from "./lib/viewer/Viewer.svelte";
  import { Pane, Workspace } from "./lib/workspace.svelte";

  const SIDEBAR_WIDTH = 232;
  const MIN_PANE_WIDTH = 220;

  interface SavedPane {
    paths: string[];
    active: number;
    width: number;
    mdOpen?: boolean[]; // integrated note shown, per tab
  }
  interface SavedSession {
    panes: SavedPane[];
    focused: number;
  }

  let info = $state<AppInfo | null>(null);
  const ws = new Workspace();
  let recents = $state<RecentDocument[]>([]);

  let invert = $state(false);
  let sidebarOpen = $state(false);
  let sidebarMode = $state<SidebarMode>("pages");
  let palette = $state(false);
  let restored = $state(false);

  let toolbarHeight = $state(52);
  let panesEl = $state<HTMLElement>();
  const viewers = new Map<number, Viewer>();
  let peek = $state<Peek | null>(null);

  let searchInput = $state<HTMLInputElement>();
  let searchText = $state("");
  let gotoInput = $state<HTMLInputElement>();
  let editingPage = $state(false);
  let zoomMenu = $state(false);
  let moreMenu = $state(false);
  let readMenu = $state(false);
  let focusMenu = $state(false);
  let parking = $state(false);
  let aiMenu = $state(false);
  let aiTools = $state(false);

  /** Focused tab of any kind; `active` is the same tab when it is a PDF. */
  const current = $derived(ws.activeTab);
  const active = $derived(current?.kind === "pdf" ? (current as Tab) : null);
  const note = $derived(current?.kind === "md" ? (current as MdTab) : null);

  // Close confirmation for tabs with unsaved annotations.
  type CloseChoice = "save" | "discard" | "cancel";
  let confirmClose = $state<{ tab: Tab; resolve: (choice: CloseChoice) => void } | null>(null);
  const viewer = () => viewers.get(ws.focused.id);

  // --- documents & tabs -----------------------------------------------------------------------

  async function refreshRecents() {
    recents = await (await api()).recent_documents(12);
  }

  async function openPath(
    path: string,
    pane: Pane = ws.focused,
    activate = true,
  ): Promise<AnyTab | null> {
    try {
      let tab: AnyTab | undefined;
      if (/\.md$/i.test(path)) {
        tab = ws.findByPath(path);
        if (!tab) {
          const md = new MdDoc(path);
          await md.load();
          tab = new MdTab(md);
          ws.add(tab, pane);
        }
      } else {
        const doc = await (await api()).open_document(path);
        tab = ws.findPdf(doc.docId, doc.path);
        if (!tab) {
          tab = new Tab(doc);
          ws.add(tab, pane);
        }
        refreshRecents();
      }
      if (activate) ws.activate(tab);
      return tab;
    } catch (e) {
      notify.error(`Could not open ${path}: ${e}`);
      return null;
    }
  }

  async function pickAndOpen(pane: Pane = ws.focused) {
    const path = await (await api()).pick_file("document");
    if (path) await openPath(path, pane);
  }

  async function newNote(pane: Pane = ws.focused) {
    const py = await api();
    const path = await py.pick_new_md("Untitled.md");
    if (!path) return;
    if (!(await py.read_text(path)).exists) {
      const name = (path.split(/[\\/]/).pop() ?? "Untitled").replace(/\.md$/i, "");
      await py.write_text(path, `# ${name}\n\n`);
    }
    await openPath(path, pane);
  }

  /** A pin clicked in a standalone note: open the note's PDF and go to the pin. */
  async function openPin(noteTab: MdTab, pin: Pin) {
    const pdfPath = await (await api()).pdf_for_md(noteTab.path);
    if (!pdfPath) {
      notify.error("This note is not linked to a PDF (no PDF with the same name next to it).");
      return;
    }
    const tab = await openPath(pdfPath, ws.paneOf(noteTab) ?? ws.focused);
    if (tab?.kind === "pdf") tab.reveal(pin.id, pin.page);
  }

  // --- export & Obsidian ------------------------------------------------------------------------

  /** Write a note into the vault; if it exists, offer to replace it. */
  async function toVault(title: string, text: string) {
    const py = await api();
    if (!(await py.get_setting("obsidian.vault", null))) {
      notify.show({ text: "Choose your Obsidian vault first.", action: { label: "Settings", run: () => (ui.settingsOpen = true) } });
      return;
    }
    const open = (path: string) => ({ label: "Open", run: () => py.open_in_obsidian(path) });
    const result = await py.obsidian_write(title, text);
    if (result.written) notify.show({ text: `Saved to Obsidian · ${title}.md`, action: open(result.path) });
    else
      notify.show({
        text: `“${title}.md” already exists in the vault.`,
        action: {
          label: "Replace",
          run: async () => {
            const r = await py.obsidian_write(title, text, true);
            notify.show({ text: `Replaced in Obsidian · ${title}.md`, action: open(r.path) });
          },
        },
      });
  }

  async function exportMarkdown(target: "file" | "vault") {
    moreMenu = false;
    const tab = active;
    if (!tab) return;
    notify.show({ text: "Converting to Markdown…" }, 60000);
    try {
      const text = await tab.exportMarkdown();
      notify.clear();
      if (target === "vault") return toVault(`${tab.title} (full text)`, text);
      const py = await api();
      const path = await py.pick_new_md(`${tab.title} (full text).md`);
      if (!path) return;
      await py.write_text(path, text);
      notify.show({ text: `Exported ${path.split(/[\\/]/).pop()}`, action: { label: "Open", run: () => openPath(path) } });
    } catch (e) {
      notify.error(`Export failed: ${e}`);
    }
  }

  async function copyNoteToVault() {
    moreMenu = false;
    if (note) return toVault(note.title, note.md.text);
    if (active) {
      const md = await active.ensureMd();
      await md.flush();
      return toVault(active.title, md.text);
    }
  }

  async function recognizeAll() {
    moreMenu = false;
    const tab = active;
    if (!tab) return;
    await tab.loadNoTextPages();
    const pages = [...(tab.noTextPages ?? [])];
    if (!pages.length) return notify.show({ text: "Every page already has text." });
    try {
      await tab.runOcr(pages, await ocrLanguages());
      notify.show({ text: kbd("Text recognized. Save with Ctrl+S to keep it in the PDF.") });
    } catch (e) {
      notify.error(`OCR failed: ${e}`);
    }
  }

  // --- Read Mode & Focus -------------------------------------------------------------------------

  function toggleZen() {
    read.zen = !read.zen;
    readMenu = false;
    if (read.zen) notify.show({ text: kbd("Zen mode — press Esc or Ctrl+. to exit.") }, 3000);
  }

  async function toggleFullscreen() {
    read.fullscreen = !read.fullscreen;
    readMenu = false;
    (await api()).toggle_fullscreen();
  }

  // Learn the reading pace from pages actually read (see reading.svelte.ts).
  $effect(() => {
    if (active) notePage(active.id, active.page, active.doc.docId);
  });

  // --- AI terminal -----------------------------------------------------------------------------

  /** Folder of the open document: the shell starts there. */
  const docFolder = $derived((current?.path ?? "").replace(/[\\/][^\\/]*$/, "") || null);

  /** The pane whose side column shows the terminal (falls back to the first pane). */
  const termPaneId = $derived(ws.pane(term.paneId ?? -1) ? term.paneId : ws.panes[0]?.id);

  function toggleTerminal() {
    if (term.open) closeTerminal();
    else openTerminal(docFolder, ws.focused.id);
  }

  function startBottomResize(e: PointerEvent) {
    const el = e.currentTarget as HTMLElement;
    capture(el, e.pointerId);
    const move = (ev: PointerEvent) => {
      const h = innerHeight - ev.clientY;
      if (h < HEADER_HEIGHT + 20) term.collapsed = true;
      else {
        term.collapsed = false;
        term.bottomHeight = Math.min(h, innerHeight - 160);
      }
    };
    const up = () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      saveLayout();
    };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
  }

  const bottomDock = $derived(term.open && term.dock === "bottom" ? (term.collapsed ? HEADER_HEIGHT : term.bottomHeight) : 0);

  async function openParkingList() {
    if (active) return active.showParking();
    const path = await (await api()).parking_path(note?.path ?? null);
    await openPath(path);
  }

  const parkingSource = $derived(active ? `${active.title}, p. ${active.page + 1}` : (note?.title ?? null));

  // --- undo, bookmarks, citation ----------------------------------------------------------------

  async function undo() {
    const label = await active?.undo();
    notify.show({ text: label ? `Undone: ${label}` : "Nothing to undo." }, 1800);
  }

  async function redo() {
    const label = await active?.redo();
    notify.show({ text: label ? `Redone: ${label}` : "Nothing to redo." }, 1800);
  }

  async function toggleBookmark() {
    if (!active) return;
    await active.loadBookmarks();
    const on = await active.toggleBookmark();
    notify.show({ text: on ? `Bookmarked page ${active.page + 1}.` : `Bookmark removed.` }, 1800);
  }

  async function copyWithCitation() {
    const sel = getSelection();
    if (!active || !sel) return;
    const pages = [sel.anchorNode, sel.focusNode]
      .map((n) => (n instanceof Element ? n : n?.parentElement)?.closest<HTMLElement>(".page")?.dataset.page)
      .filter((p): p is string => p !== undefined)
      .map(Number);
    await copyText(citation(active, sel.toString(), pages.length ? pages : [active.page]));
    notify.show({ text: "Copied with citation." }, 1800);
  }

  async function exportHighlights() {
    moreMenu = false;
    if (!active) return;
    const n = await active.exportHighlightsToNote();
    notify.show({ text: `${n} highlight${n === 1 ? "" : "s"} written under the line in ${active.md?.name}.` });
  }

  /** Equation → LaTeX: draw a rectangle on the page (see EquationSnip). */
  function startSnip() {
    aiTools = false;
    if (!active) return;
    active.tool = "select";
    active.snipping = true;
  }

  // --- grading mode -----------------------------------------------------------------------------

  const gradingHost: Host = {
    open: async (path) => {
      const pane = (grading.session?.tab && ws.paneOf(grading.session.tab)) || ws.focused;
      const tab = await openPath(path, pane);
      return tab?.kind === "pdf" ? tab : null;
    },
    close: async (tab) => {
      if (!ws.allTabs().includes(tab)) return;
      ws.remove(tab);
      if (peek?.tab === tab) peek = null;
      await releaseDocument(tab);
    },
  };

  const gradingKey = () => `grading.window.${info?.windowId ?? "main"}`;

  async function startGrading(folder?: string | null) {
    const py = await api();
    folder ??= await py.pick_folder();
    if (!folder) return;
    if (grading.session) await grading.session.stop();
    const session = await GradingSession.start(folder, gradingHost);
    if (!session) return;
    sidebarOpen = true;
    sidebarMode = "files";
    py.set_setting(gradingKey(), session.folder);
    notify.show({ text: `Grading ${session.exams.length} exams in “${session.title}”. Marked copies go to graded/.` }, 4000);
  }

  async function stopGrading() {
    if (!grading.session) return;
    await grading.session.stop();
    if (sidebarMode === "files") sidebarMode = "outline";
    (await api()).set_setting(gradingKey(), null);
  }

  function toggleGrading() {
    if (grading.session) stopGrading();
    else startGrading();
  }

  // --- command palette ----------------------------------------------------------------------------

  function setTint(tint: Tint) {
    read.tint = tint;
    saveReadSettings();
  }

  const commands = $derived.by((): Command[] => {
    const c: Command[] = [];
    const add = (group: string, title: string, run: () => void, keys?: string) =>
      c.push({ id: `${group}:${title}`, group, title, run, keys });
    const pdf = active;
    if (pdf) {
      add("Document", "Save annotations", saveCurrent, "Ctrl+S");
      add("Document", "Undo", undo, "Ctrl+Z");
      add("Document", "Redo", redo, "Ctrl+Y");
      add("Document", pdf.isBookmarked(pdf.page) ? "Remove bookmark" : "Bookmark this page", toggleBookmark, "Ctrl+B");
      add("Document", "Show bookmarks", () => ((sidebarOpen = true), (sidebarMode = "bookmarks")));
      add("Document", "Export highlights to note", exportHighlights);
      add("Document", "Export as Markdown…", () => exportMarkdown("file"));
      add("Document", "Export to Obsidian vault", () => exportMarkdown("vault"));
      add("Document", "Copy note to Obsidian", copyNoteToVault);
      add("Document", "Recognize text (OCR)", recognizeAll);
      add("Document", "Go to first page", () => pdf.navigate({ page: 0 }), "Home");
      add("Document", "Go to last page", () => pdf.navigate({ page: pdf.pageCount - 1 }), "End");
      add("Annotate", "Add note", () => (pdf.tool = "note"));
      add("Annotate", "Add text", () => (pdf.tool = "text"));
      add("Annotate", "Draw", () => (pdf.tool = "draw"));
      add("View", "Toggle annotations panel", () => (pdf.panelOpen = !pdf.panelOpen));
      add("View", "Toggle integrated note", () => pdf.toggleMd());
      add("View", "Show parking lot", () => pdf.showParking());
      add("View", "Zoom in", () => viewer()?.zoomBy(1.2), "Ctrl++");
      add("View", "Zoom out", () => viewer()?.zoomBy(1 / 1.2), "Ctrl+-");
      add("View", "Fit width", () => setFit("width"));
      add("View", "Fit page", () => setFit("page"));
      add("View", "Actual size", () => setFit("none"), "Ctrl+0");
      add("View", invert ? "Light pages" : "Dark pages", toggleInvert);
    }
    add("View", "Toggle sidebar", toggleSidebar, "Ctrl+\\");
    const g = grading.session;
    if (g) {
      add("Grading", "Done — next exam", () => g.next());
      add("Grading", "Previous exam", () => g.prev());
      add("Grading", "Export grades as CSV", () => g.exportCsv());
      add("Grading", "Stop grading", stopGrading);
    } else add("Grading", "Grade a folder of exams…", () => startGrading());
    add("Read & Focus", read.ruler ? "Hide reading ruler" : "Show reading ruler", () => ((read.ruler = !read.ruler), saveReadSettings()));
    add("Read & Focus", "Zen mode", toggleZen, "Ctrl+.");
    add("Read & Focus", "Full screen", toggleFullscreen, "F11");
    for (const [key, t] of Object.entries(TINTS)) add("Read & Focus", `Page tint: ${t.label}`, () => setTint(key as Tint));
    add("Read & Focus", pomodoro.running ? "Pause pomodoro" : "Start pomodoro", () => (pomodoro.running ? pausePomodoro() : startPomodoro()));
    add("Read & Focus", "Park a thought", () => (parking = true), "Ctrl+Shift+Space");
    add("AI", term.open ? "Hide terminal" : "Open terminal", toggleTerminal, "Ctrl+`");
    add("AI", "How to set up Claude Code / Codex", () => (term.guideOpen = true));
    if (pdf) add("AI", "Ask the AI about this document…", () => (aiMenu = true));
    if (pdf) add("AI", "Equation → LaTeX (AI)", () => startSnip());
    add("App", "Open…", () => pickAndOpen(), "Ctrl+O");
    add("App", "New note…", () => newNote());
    add("App", "New tab", () => newTab(), "Ctrl+T");
    add("App", "Settings", () => (ui.settingsOpen = true));
    add("App", "How to use PhDF", () => (ui.helpOpen = true));
    for (const r of recents) add("Recent", r.title ?? r.path, () => openPath(r.path));
    return c;
  });

  function dynamicCommands(q: string): Command[] {
    const out: Command[] = [];
    const pdf = active;
    if (pdf && /^\d+$/.test(q)) {
      const n = Math.min(Math.max(Number(q), 1), pdf.pageCount);
      out.push({ id: "goto", group: "Go to", title: `Go to page ${n}`, run: () => pdf.navigate({ page: n - 1 }) });
    }
    if (pdf && q.length >= 2 && !/^\d+$/.test(q)) {
      out.push({
        id: "search",
        group: "Search",
        title: `Search “${q}” in this document`,
        run: () => {
          searchText = q;
          pdf.search(q);
        },
      });
    }
    return out;
  }

  async function saveCurrent() {
    if (active) await active.save();
    else if (note) await note.md.flush();
  }

  function selectTab(tab: AnyTab) {
    ws.activate(tab);
    peek = null;
  }

  /** Save / Don't Save / Cancel for a tab with unsaved annotations. */
  async function askSave(tab: Tab): Promise<CloseChoice> {
    ws.activate(tab);
    const choice = await new Promise<CloseChoice>((resolve) => (confirmClose = { tab, resolve }));
    confirmClose = null;
    if (choice === "save") await tab.save();
    return choice;
  }

  async function closeTab(tab: AnyTab) {
    if (tab === grading.session?.tab) await stopGrading(); // closing the exam ends grading
    if (tab.kind === "pdf" && tab.dirty && (await askSave(tab)) === "cancel") return;
    ws.remove(tab);
    if (peek?.tab === tab) peek = null;
    await tab.md?.flush();
    await releaseDocument(tab);
    if (!ws.activeTab) refreshRecents();
  }

  /** Let the backend close a PDF once no other tab in this window shows it. */
  async function releaseDocument(tab: AnyTab) {
    if (tab.kind !== "pdf") return;
    const stillShown = ws.allTabs().some((t) => t !== tab && t.kind === "pdf" && t.doc.docId === tab.doc.docId);
    if (!stillShown) (await api()).close_document(tab.doc.docId);
  }

  /** "Open Beside" from a link preview: the same document, at the link target, in a pane beside. */
  function openBeside(source: Tab, page: number, y: number | null) {
    const tab = new Tab(source.doc);
    tab.welcomeBack = false;
    tab.zoom = source.zoom;
    tab.fit = source.fit;
    tab.pendingJump = { page, y };
    ws.placeBeside(tab, ws.paneOf(source) ?? ws.focused);
  }

  function newTab(pane: Pane = ws.focused) {
    pane.activeId = null;
    ws.focus(pane);
    refreshRecents();
  }

  function cycleTab(delta: number) {
    const pane = ws.focused;
    if (!pane.tabs.length) return;
    const i = pane.tabs.findIndex((t) => t.id === pane.activeId);
    ws.activate(pane.tabs[(i + delta + pane.tabs.length) % pane.tabs.length]);
  }

  // --- tab drag & drop ------------------------------------------------------------------------

  function acceptDrop(tab: AnyTab, target: DropTarget): boolean {
    if (target.kind === "window") return ws.tabCount > 1;
    const pane = ws.pane(target.paneId);
    if (!pane) return false;
    if (target.kind === "split") return ws.canSplit(tab, pane);
    if (target.kind === "into") return !pane.tabs.includes(tab);
    return true;
  }

  async function dropTab(tab: AnyTab, target: DropTarget) {
    if (target.kind === "window") {
      // Tear off: the new window takes its own reference first (unsaved annotations survive),
      // then this window lets the tab go.
      await tab.md?.flush();
      const py = await api();
      // Dropped on another PhDF window: move the tab there; anywhere else: a new window.
      const other = await py.window_at(target.screenX, target.screenY, devicePixelRatio);
      if (other) await py.send_to_window(other, tab.path);
      else await py.open_window([tab.path], target.screenX - 160, target.screenY - 20);
      ws.remove(tab);
      await releaseDocument(tab);
      return;
    }
    const pane = ws.pane(target.paneId)!;
    if (target.kind === "bar") ws.move(tab, pane, target.index);
    else if (target.kind === "into") ws.move(tab, pane, pane.tabs.length);
    else ws.split(tab, pane, target.side);
  }

  function onTabDragStart(e: PointerEvent, tab: AnyTab) {
    startTabDrag(e, tab, { accept: acceptDrop, drop: dropTab });
  }

  // --- pane resizing --------------------------------------------------------------------------

  function startResize(e: PointerEvent, index: number) {
    const left = ws.panes[index - 1];
    const right = ws.panes[index];
    const total = ws.panes.reduce((s, p) => s + p.width, 0);
    const px = panesEl!.clientWidth;
    const pair = left.width + right.width;
    const min = (MIN_PANE_WIDTH / px) * total;
    const start = e.clientX;
    const startLeft = left.width;
    const el = e.currentTarget as HTMLElement;
    capture(el, e.pointerId);
    const move = (ev: PointerEvent) => {
      const w = startLeft + ((ev.clientX - start) / px) * total;
      left.width = Math.min(Math.max(w, min), pair - min);
      right.width = pair - left.width;
    };
    const up = () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
    };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
  }

  // --- links ----------------------------------------------------------------------------------

  function onLink(link: PdfLink, event: MouseEvent) {
    if (!active) return;
    peek = { tab: active, link, x: event.clientX, y: event.clientY };
  }

  // --- search & go to page --------------------------------------------------------------------

  let searchTimer: ReturnType<typeof setTimeout> | undefined;
  function onSearchInput() {
    clearTimeout(searchTimer);
    const q = searchText;
    const tab = active;
    searchTimer = setTimeout(() => tab?.search(q), 250);
  }

  function onSearchKey(e: KeyboardEvent) {
    if (!active) return;
    if (e.key === "Enter") {
      e.preventDefault();
      if (active.searchQuery !== searchText) {
        clearTimeout(searchTimer);
        active.search(searchText);
      } else active.stepSearch(e.shiftKey ? -1 : 1);
    } else if (e.key === "Escape") {
      searchText = "";
      active.clearSearch();
      searchInput?.blur();
    }
  }

  // Each tab keeps its own query; show it when the focused tab changes.
  $effect(() => {
    searchText = active?.searchQuery ?? "";
  });

  async function startGoto() {
    if (!active) return;
    editingPage = true;
    await Promise.resolve();
    gotoInput?.select();
  }

  function onGotoKey(e: KeyboardEvent) {
    if (e.key === "Enter" && active) {
      const n = parseInt(gotoInput?.value ?? "", 10);
      if (!Number.isNaN(n)) active.navigate({ page: n - 1 });
      editingPage = false;
    } else if (e.key === "Escape") editingPage = false;
  }

  // --- zoom & view ----------------------------------------------------------------------------

  function setFit(mode: FitMode) {
    zoomMenu = false;
    if (mode === "none") viewer()?.setZoom(1);
    else viewer()?.setFit(mode);
  }

  function toggleInvert() {
    invert = !invert;
    api().then((py) => py.set_setting("invertPages", invert));
  }

  function toggleSidebar() {
    sidebarOpen = !sidebarOpen;
  }

  function setSidebarMode(mode: SidebarMode) {
    sidebarMode = mode;
  }

  // --- keyboard -------------------------------------------------------------------------------

  function inTextField(e: KeyboardEvent) {
    const el = e.target as HTMLElement;
    return el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable;
  }

  function onKeydown(e: KeyboardEvent) {
    const mod = e.ctrlKey || e.metaKey;
    const key = e.key.toLowerCase();
    let handled = true;

    // Terminal toggle works everywhere; other shortcuts stay out of the terminal's way.
    if (mod && (e.code === "Backquote" || key === "`")) {
      e.preventDefault();
      return toggleTerminal();
    }
    if ((e.target as HTMLElement).closest?.(".xterm")) return;

    if (mod && e.shiftKey && (key === " " || e.code === "Space")) parking = !parking;
    else if (mod && key === ".") toggleZen();
    else if (key === "f11" || (e.metaKey && e.ctrlKey && key === "f")) toggleFullscreen(); // ⌃⌘F on a Mac
    else if (key === "escape" && read.zen && !peek && !parking) toggleZen();
    else if (mod && key === "o") pickAndOpen();
    else if (mod && key === "s") saveCurrent();
    else if (mod && key === "k") palette = !palette;
    else if (mod && !e.shiftKey && key === "z" && active && !inTextField(e)) undo();
    else if (mod && (key === "y" || (e.shiftKey && key === "z")) && active && !inTextField(e)) redo();
    else if (mod && key === "b" && active && !inTextField(e)) toggleBookmark();
    else if (mod && e.shiftKey && key === "c" && active && getSelection()?.toString()) copyWithCitation();
    else if (mod && key === "t") newTab();
    else if (mod && key === "w") current && closeTab(current);
    else if (key === "escape" && active && active.tool !== "select") active.tool = "select";
    else if (mod && key === "tab") cycleTab(e.shiftKey ? -1 : 1);
    else if (mod && key === "f" && active) searchInput?.focus();
    else if (mod && key === "g" && active) startGoto();
    else if (mod && (key === "=" || key === "+") && active) viewer()?.zoomBy(1.2);
    else if (mod && key === "-" && active) viewer()?.zoomBy(1 / 1.2);
    else if (mod && key === "0" && active) viewer()?.setZoom(1);
    else if (mod && key === "\\") toggleSidebar();
    else if ((e.altKey && key === "arrowleft") || (e.metaKey && key === "[")) active?.goBack(); // ⌘[ ⌘] on a Mac
    else if (e.metaKey && key === "]") active?.goForward();
    else if (e.altKey && key === "arrowright") active?.goForward();
    else if (active && !mod && !e.altKey && !inTextField(e) && !peek) {
      if (key === "arrowright") active.pendingJump = { page: active.page + 1 };
      else if (key === "arrowleft") active.pendingJump = { page: Math.max(active.page - 1, 0) };
      else if (key === "home") active.navigate({ page: 0 });
      else if (key === "end") active.navigate({ page: active.pageCount - 1 });
      else handled = false;
    } else handled = false;

    if (handled) e.preventDefault();
  }

  // --- session --------------------------------------------------------------------------------

  function sessionSnapshot(): SavedSession {
    return {
      panes: ws.panes.map((p) => ({
        paths: p.tabs.map((t) => t.path),
        active: p.tabs.findIndex((t) => t.id === p.activeId),
        width: p.width,
        mdOpen: p.tabs.map((t) => t.kind === "pdf" && t.mdOpen),
      })),
      focused: ws.panes.indexOf(ws.focused),
    };
  }

  // Remember this window's panes/tabs and the sidebar across launches.
  let saveTimer: ReturnType<typeof setTimeout> | undefined;
  $effect(() => {
    if (!restored || !info) return;
    const key = `session.${info.windowId}`;
    const session = sessionSnapshot();
    const sidebar = { open: sidebarOpen, mode: sidebarMode };
    clearTimeout(saveTimer);
    saveTimer = setTimeout(async () => {
      const py = await api();
      py.set_setting(key, session);
      py.set_setting("sidebar", sidebar);
    }, 300);
  });

  /** v0.1.0 stored {paths, active}; newer versions store panes. */
  function normalize(raw: unknown): SavedSession {
    const s = (raw ?? {}) as Partial<SavedSession> & { paths?: string[]; active?: number };
    if (Array.isArray(s.panes)) return { panes: s.panes, focused: s.focused ?? 0 };
    return { panes: [{ paths: s.paths ?? [], active: s.active ?? 0, width: 1 }], focused: 0 };
  }

  async function restoreSession(windowId: string) {
    const py = await api();
    const session = normalize(await py.get_setting(`session.${windowId}`, null));
    const panes = session.panes.length ? session.panes.map(() => new Pane()) : [new Pane()];
    ws.panes = panes;
    for (const [i, saved] of session.panes.entries()) {
      const pane = panes[i];
      pane.width = saved.width || 1;
      for (const [j, path] of saved.paths.entries()) {
        const tab = await openPath(path, pane, false);
        if (tab?.kind === "pdf" && saved.mdOpen?.[j]) await tab.toggleMd(true);
      }
      pane.activeId = pane.tabs[saved.active]?.id ?? pane.tabs[0]?.id ?? null;
    }
    // Drop panes whose files have all gone missing.
    if (ws.panes.length > 1) ws.panes = ws.panes.filter((p) => p.tabs.length);
    if (!ws.panes.length) ws.panes = [new Pane()];
    ws.focusedId = (ws.panes[session.focused] ?? ws.panes[0]).id;
    notify.clear(); // files that moved away since last time are just skipped
  }

  onMount(async () => {
    const py = await api();
    const appInfo = await py.app_info();
    setRenderBaseUrl(appInfo.renderBaseUrl);
    invert = await py.get_setting("invertPages", false);
    await Promise.all([loadReadSettings(), loadPomodoroSettings(), loadPace(), loadLayout(), loadInk(), loadTextStyle(), loadGradingSettings()]);
    const sidebar = await py.get_setting("sidebar", { open: false, mode: "pages" as const });
    sidebarOpen = sidebar.open;
    sidebarMode = sidebar.mode;
    await restoreSession(appInfo.windowId);
    setInterval(() => tickReading(), 1000);
    for (const type of ["pointermove", "keydown", "wheel", "pointerdown"]) {
      window.addEventListener(type, () => noteActivity(), { passive: true, capture: true });
    }
    // Closing the window with unsaved annotations: the backend held the close and asks us.
    window.addEventListener("phdf:close-request", async () => {
      for (const t of ws.allTabs()) {
        if (t.kind === "pdf" && t.dirty && (await askSave(t)) === "cancel") return;
      }
      for (const t of ws.allTabs()) await t.md?.flush();
      flushReading();
      (await api()).close_window();
    });
    // A tab dragged here from another PhDF window.
    window.addEventListener("phdf:open-path", (e) => openPath((e as CustomEvent<string>).detail));
    window.addEventListener("beforeunload", () => flushReading());
    // Notes may be edited in Obsidian or elsewhere meanwhile: reload them when we come back.
    window.addEventListener("focus", () => {
      for (const t of ws.allTabs()) t.md?.checkExternal();
    });
    await refreshRecents();
    info = appInfo;
    restored = true;
    // Grading was on when this window closed: carry on where it stopped.
    const gradingFolder = await py.get_setting<string | null>(gradingKey(), null);
    if (gradingFolder) await startGrading(gradingFolder);
    // Files PhDF was started with ("Open with", command line).
    for (const path of await py.startup_paths()) await openPath(path);
  });
</script>

<svelte:window onkeydown={onKeydown} />

<div class="window" class:dragging={drag.tab}>
  {#if active && sidebarOpen && !read.zen}
    <div class="sidebar" style="width:{SIDEBAR_WIDTH}px">
      <Sidebar tab={active} mode={sidebarMode} {invert} onmode={setSidebarMode} />
    </div>
  {/if}

  <div class="main" style="left:{active && sidebarOpen && !read.zen ? SIDEBAR_WIDTH : 0}px">
    <header bind:clientHeight={toolbarHeight} class:hidden={read.zen}>
      <div class="toolbar">
        <div class="group">
          <button class="tool" title={kbd("Sidebar (Ctrl+\\)")} onclick={toggleSidebar} disabled={!active}>
            <Icon name="sidebar" />
          </button>
          <button class="tool nav" title={kbd("Back (Alt+←)")} onclick={() => active?.goBack()} disabled={!active?.back.length}>
            <Icon name="left" />
          </button>
          <button
            class="tool nav"
            title={kbd("Forward (Alt+→)")}
            onclick={() => active?.goForward()}
            disabled={!active?.forward.length}
          >
            <Icon name="right" />
          </button>
          <div class="drop">
            <button class="pill" class:on={readMenu || read.ruler || read.tint !== "none"} onclick={() => (readMenu = !readMenu)}>
              <Icon name="book" size={15} /> <span class="pill-label">Read</span> <Icon name="chevron" size={12} />
            </button>
            {#if readMenu}
              <ReadMenu onclose={() => (readMenu = false)} onzen={toggleZen} onfullscreen={toggleFullscreen} />
            {/if}
          </div>
          <div class="drop">
            <button class="pill" class:on={focusMenu || pomodoro.phase !== "idle"} onclick={() => (focusMenu = !focusMenu)}>
              <Icon name="timer" size={15} />
              {#if pomodoro.phase !== "idle"}
                <span class="mini-clock" class:break={pomodoro.phase === "break"} class:paused={!pomodoro.running}>
                  {clock(pomodoro.remaining)}
                </span>
              {:else}
                <span class="pill-label">Focus</span>
              {/if}
              <Icon name="chevron" size={12} />
            </button>
            {#if focusMenu}
              <FocusMenu tab={active} onclose={() => (focusMenu = false)} />
            {/if}
          </div>
          <button
            class="pill park"
            class:on={parking}
            title={kbd("Parking lot — park a stray thought (Ctrl+Shift+Space)")}
            onclick={() => (parking = !parking)}
          >
            <Icon name="park" size={15} /> <span class="pill-label">Park</span>
          </button>
        </div>

        <div class="title">
          {#if active}
            <span class="name">
              {active.title}{#if active.dirty}<span class="edited">— Edited</span>{/if}
            </span>
            {#if editingPage}
              <span class="subtitle">
                Page <input
                  class="goto"
                  bind:this={gotoInput}
                  value={active.page + 1}
                  onkeydown={onGotoKey}
                  onblur={() => (editingPage = false)}
                  aria-label="Go to page"
                /> of {active.pageCount}
              </span>
            {:else}
              <button class="subtitle" onclick={startGoto} title={kbd("Go to page (Ctrl+G)")}>
                Page {active.page + 1} of {active.pageCount}
              </button>
            {/if}
          {:else if note}
            <span class="name">{note.title}</span>
            <span class="subtitle static">Markdown note</span>
          {:else}
            <span class="name">PhDF</span>
          {/if}
        </div>

        <div class="group end">
          {#if active}
            {@const pdf = active}
            <div class="tools">
              <button
                class="tool"
                class:on={pdf.tool === "note"}
                title="Add note: click on the page (Esc to stop)"
                onclick={() => (pdf.tool = pdf.tool === "note" ? "select" : "note")}
              >
                <Icon name="note" />
              </button>
              <button
                class="tool"
                class:on={pdf.tool === "text"}
                title="Add text: click on the page (Esc to stop)"
                onclick={() => (pdf.tool = pdf.tool === "text" ? "select" : "text")}
              >
                <Icon name="text" />
              </button>
              <button
                class="tool"
                class:on={pdf.tool === "draw"}
                title="Draw (Esc to stop)"
                onclick={() => (pdf.tool = pdf.tool === "draw" ? "select" : "draw")}
              >
                <Icon name="pen" />
              </button>
              <button
                class="tool"
                class:on={pdf.panelOpen}
                title="Annotations"
                onclick={() => (pdf.panelOpen = !pdf.panelOpen)}
              >
                <Icon name="list" />
              </button>
              <button
                class="tool"
                class:on={pdf.mdOpen}
                title="Integrated .md note"
                onclick={() => pdf.toggleMd()}
              >
                <Icon name="mdnote" />
              </button>
            </div>

            <div class="segmented zoom">
              <button title={kbd("Zoom out (Ctrl+-)")} onclick={() => viewer()?.zoomBy(1 / 1.2)}>
                <Icon name="minus" size={14} />
              </button>
              <button class="zoom-label" onclick={() => (zoomMenu = !zoomMenu)} title="Zoom options">
                {Math.round(active.zoom * 100)}%
              </button>
              <button title={kbd("Zoom in (Ctrl++)")} onclick={() => viewer()?.zoomBy(1.2)}>
                <Icon name="plus" size={14} />
              </button>
              {#if zoomMenu}
                <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
                <div class="menu-backdrop" onclick={() => (zoomMenu = false)}></div>
                <div class="menu" role="menu">
                  <button role="menuitemradio" aria-checked={active.fit === "width"} onclick={() => setFit("width")}>
                    Fit Width
                  </button>
                  <button role="menuitemradio" aria-checked={active.fit === "page"} onclick={() => setFit("page")}>
                    Fit Page
                  </button>
                  <button role="menuitemradio" aria-checked={false} onclick={() => setFit("none")}>
                    Actual Size <span class="shortcut">{kbd("Ctrl+0")}</span>
                  </button>
                </div>
              {/if}
            </div>

            <button class="tool dark" class:on={invert} title="Dark pages" onclick={toggleInvert}>
              <Icon name="moon" />
            </button>

            <label class="search">
              <Icon name="search" size={14} />
              <input
                bind:this={searchInput}
                bind:value={searchText}
                oninput={onSearchInput}
                onkeydown={onSearchKey}
                placeholder="Search"
                spellcheck="false"
              />
              {#if active.searchQuery}
                <span class="count">
                  {#if active.searching}…{:else if active.searchHits.length}
                    {active.searchIndex + 1}/{active.searchHits.length}
                  {:else}0{/if}
                </span>
              {/if}
            </label>
          {/if}
          {#if active}
            <div class="drop ai-drop">
              <button class="tool" class:on={aiMenu} title="Ask the AI about this document, chapter or page" onclick={() => (aiMenu = !aiMenu)}>
                <Icon name="sparkle" />
              </button>
              <button class="tool caret" class:on={aiTools} title="More AI tools" onclick={() => (aiTools = !aiTools)}>
                <Icon name="chevron" size={12} />
              </button>
              {#if aiMenu}
                <DocAiMenu tab={active} paneId={ws.focused.id} onclose={() => (aiMenu = false)} />
              {/if}
              {#if aiTools}
                <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
                <div class="menu-backdrop" onclick={() => (aiTools = false)}></div>
                <div class="menu right ai-tools" role="menu">
                  <button role="menuitem" onclick={startSnip}>
                    Equation → LaTeX (AI)
                    <span class="sub">Draw a rectangle around an equation; the AI writes its LaTeX into your note.</span>
                  </button>
                </div>
              {/if}
            </div>
          {/if}
          <button class="tool" class:on={term.open} title={kbd("AI terminal (Ctrl+`)")} onclick={toggleTerminal} disabled={!info}>
            <Icon name="terminal" />
          </button>

          <button
            class="tool grade"
            class:on={!!grading.session}
            title={grading.session ? `Grading “${grading.session.title}” — click to stop` : "Grade a folder of exam PDFs"}
            onclick={toggleGrading}
            disabled={!info}
          >
            <Icon name="grade" />
          </button>
          <button class="tool help" title="How to use PhDF" onclick={() => (ui.helpOpen = true)}>
            <Icon name="help" />
          </button>
          <div class="more">
            <button class="tool" class:on={moreMenu} title="More" onclick={() => (moreMenu = !moreMenu)} disabled={!info}>
              <Icon name="more" />
            </button>
            {#if moreMenu}
              <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
              <div class="menu-backdrop" onclick={() => (moreMenu = false)}></div>
              <div class="menu right" role="menu">
                {#if active}
                  {@const pdf = active}
                  <div class="narrow-tools">
                    <button role="menuitemcheckbox" aria-checked={pdf.tool === "note"} onclick={() => ((moreMenu = false), (pdf.tool = pdf.tool === "note" ? "select" : "note"))}>Add Note</button>
                    <button role="menuitemcheckbox" aria-checked={pdf.tool === "text"} onclick={() => ((moreMenu = false), (pdf.tool = pdf.tool === "text" ? "select" : "text"))}>Add Text</button>
                    <button role="menuitemcheckbox" aria-checked={pdf.tool === "draw"} onclick={() => ((moreMenu = false), (pdf.tool = pdf.tool === "draw" ? "select" : "draw"))}>Draw</button>
                    <button role="menuitemcheckbox" aria-checked={pdf.panelOpen} onclick={() => ((moreMenu = false), (pdf.panelOpen = !pdf.panelOpen))}>Annotations</button>
                    <button role="menuitemcheckbox" aria-checked={pdf.mdOpen} onclick={() => ((moreMenu = false), pdf.toggleMd())}>Integrated .md Note</button>
                    <div class="menu-sep"></div>
                  </div>
                  <div class="narrow-zoom">
                    <button role="menuitem" onclick={() => viewer()?.zoomBy(1.2)}>Zoom In <span class="shortcut">{kbd("Ctrl++")}</span></button>
                    <button role="menuitem" onclick={() => viewer()?.zoomBy(1 / 1.2)}>Zoom Out <span class="shortcut">{kbd("Ctrl+-")}</span></button>
                    <button role="menuitemradio" aria-checked={pdf.fit === "width"} onclick={() => ((moreMenu = false), setFit("width"))}>Fit Width</button>
                    <button role="menuitemradio" aria-checked={pdf.fit === "page"} onclick={() => ((moreMenu = false), setFit("page"))}>Fit Page</button>
                    <button role="menuitemcheckbox" aria-checked={invert} onclick={() => ((moreMenu = false), toggleInvert())}>Dark Pages</button>
                    <div class="menu-sep"></div>
                  </div>
                  {#if grading.session}
                    {@const g = grading.session}
                    <button role="menuitem" onclick={() => ((moreMenu = false), g.exportCsv())}>Export Grades as CSV…</button>
                    <button role="menuitem" onclick={() => ((moreMenu = false), stopGrading())}>Stop Grading</button>
                    <div class="menu-sep"></div>
                  {/if}
                  <button role="menuitem" onclick={exportHighlights}>Export Highlights to Note</button>
                  <button role="menuitem" onclick={() => exportMarkdown("file")}>Export as Markdown…</button>
                  <button role="menuitem" onclick={() => exportMarkdown("vault")}>Export to Obsidian Vault</button>
                  <button role="menuitem" onclick={copyNoteToVault}>Copy Note to Obsidian</button>
                  <div class="menu-sep"></div>
                  <button role="menuitem" onclick={recognizeAll} disabled={!!active.ocrProgress}>Recognize Text (OCR)</button>
                  <div class="menu-sep"></div>
                {:else if note}
                  <button role="menuitem" onclick={copyNoteToVault}>Copy Note to Obsidian</button>
                  <div class="menu-sep"></div>
                {/if}
                <button role="menuitem" onclick={() => ((moreMenu = false), (ui.settingsOpen = true))}>Settings…</button>
              </div>
            {/if}
          </div>
          <button class="tool" title={kbd("Open PDF or Markdown (Ctrl+O)")} onclick={() => pickAndOpen()} disabled={!info}>
            <Icon name="open" />
          </button>
        </div>
      </div>
    </header>

    <div class="panes" bind:this={panesEl} style="bottom:{bottomDock}px">
      {#if info}
        {#each ws.panes as pane, i (pane.id)}
          {#if i > 0}
            <div class="divider" role="separator" aria-orientation="vertical" onpointerdown={(e) => startResize(e, i)}></div>
          {/if}
          <PaneView
            {pane}
            focused={pane.id === ws.focused.id}
            multi={ws.panes.length > 1}
            toolbarHeight={read.zen ? 0 : toolbarHeight}
            zen={read.zen}
            termHere={term.open && term.dock === "side" && pane.id === termPaneId}
            {invert}
            version={info.version}
            {recents}
            onfocus={() => ws.focus(pane)}
            onopen={() => pickAndOpen(pane)}
            onnewnote={() => newNote(pane)}
            onmdpin={openPin}
            onpickmd={async () => (await api()).pick_file("md")}
            onopenpath={(path) => openPath(path, pane)}
            onselect={selectTab}
            onclose={closeTab}
            onnew={() => newTab(pane)}
            ondragstart={onTabDragStart}
            onlink={onLink}
            onviewer={(v) => (v ? viewers.set(pane.id, v) : viewers.delete(pane.id))}
          />
        {/each}
      {:else}
        <p class="hint" style="padding-top:{toolbarHeight + 40}px">Starting…</p>
      {/if}
    </div>

    {#if term.open && term.dock === "bottom"}
      <div class="bottom-dock" style="height:{bottomDock}px">
        {#if !term.collapsed}
          <div class="b-divider" role="separator" aria-orientation="horizontal" onpointerdown={startBottomResize}></div>
        {/if}
        <AiPanel />
      </div>
    {/if}

    {#if term.dragging}
      <div class="dock-zone side" class:on={term.dropTarget === "side"}>Dock at the side</div>
      <div class="dock-zone bottom" class:on={term.dropTarget === "bottom"}>Dock at the bottom</div>
    {/if}

    {#if notify.current}
      {@const n = notify.current}
      <div class="toast" class:error={n.error} role={n.error ? "alert" : "status"}>
        <span>{n.text}</span>
        {#if n.action}
          <button class="action" onclick={() => (n.action!.run(), notify.clear())}>{n.action.label}</button>
        {/if}
        {#if n.action2}
          <button class="action" onclick={() => (n.action2!.run(), notify.clear())}>{n.action2.label}</button>
        {/if}
        <button onclick={() => notify.clear()} aria-label="Dismiss"><Icon name="close" size={12} /></button>
      </div>
    {/if}
  </div>

  {#if drag.tab}
    <div class="ghost" style="left:{drag.x + 14}px;top:{drag.y + 10}px">
      <Icon name="doc" size={14} />
      <span>{drag.tab.title}</span>
      {#if drag.target?.kind === "window"}<span class="ghost-hint">New Window</span>{/if}
    </div>
  {/if}

  {#if peek}
    <LinkPeek {peek} {invert} onclose={() => (peek = null)} onsplit={openBeside} />
  {/if}

  {#if read.zen}
    <button class="zen-exit" onclick={toggleZen} title="Exit zen mode (Esc)">Exit Zen</button>
  {/if}

  {#if parking}
    <ParkingLot
      source={parkingSource}
      document={active?.path ?? note?.path ?? null}
      onclose={() => (parking = false)}
      onparked={() => active?.parkingChanged()}
      onopen={openParkingList}
    />
  {/if}

  {#if palette}
    <CommandPalette commands={commands} dynamic={dynamicCommands} onclose={() => (palette = false)} />
  {/if}

  {#if term.guideOpen}
    <TerminalGuide onclose={() => (term.guideOpen = false)} />
  {/if}

  {#if ui.helpOpen}
    <Help onclose={() => (ui.helpOpen = false)} />
  {/if}

  {#if ui.settingsOpen}
    <Settings onclose={() => (ui.settingsOpen = false)} />
  {/if}

  {#if confirmClose}
    {@const c = confirmClose}
    <div class="sheet-backdrop">
      <div class="sheet" role="alertdialog" aria-labelledby="save-title">
        <div class="sheet-icon">Ph</div>
        <h2 id="save-title">Do you want to save the changes made to “{c.tab.title}”?</h2>
        <p>Your annotations will be lost if you don’t save them.</p>
        <div class="sheet-actions">
          <button class="plain" onclick={() => c.resolve("discard")}>Don’t Save</button>
          <span class="grow"></span>
          <button class="plain" onclick={() => c.resolve("cancel")}>Cancel</button>
          <button class="default" onclick={() => c.resolve("save")}>Save</button>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .window {
    position: relative;
    height: 100%;
    overflow: hidden;
  }

  .window.dragging {
    cursor: grabbing;
  }

  .sidebar {
    position: absolute;
    inset: 0 auto 0 0;
  }

  .main {
    position: absolute;
    inset: 0 0 0 0;
  }

  /* Translucent unified toolbar; panes scroll underneath it. */
  header {
    position: absolute;
    inset: 0 0 auto 0;
    z-index: 10;
    background: var(--toolbar);
    backdrop-filter: saturate(180%) blur(20px);
  }

  .panes {
    position: absolute;
    inset: 0;
    display: flex;
  }

  .divider {
    position: relative;
    z-index: 9;
    flex: none;
    width: 1px;
    background: var(--separator);
    cursor: col-resize;
  }

  /* Wider invisible grab area. */
  .divider::before {
    content: "";
    position: absolute;
    inset: 0 -4px;
  }

  .ghost {
    position: fixed;
    z-index: 50;
    display: flex;
    align-items: center;
    gap: 6px;
    max-width: 280px;
    padding: 5px 10px;
    border-radius: 8px;
    background: var(--popover);
    backdrop-filter: blur(20px);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 8px 24px rgb(0 0 0 / 0.25);
    font-size: 12px;
    pointer-events: none;
    white-space: nowrap;
  }

  .ghost span:first-of-type {
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .ghost-hint {
    color: var(--accent);
    font-weight: 500;
  }

  header.hidden {
    display: none;
  }

  .bottom-dock {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 9;
    border-top: 0.5px solid var(--separator);
  }

  .b-divider {
    position: absolute;
    top: -4px;
    left: 0;
    right: 0;
    height: 8px;
    z-index: 2;
    cursor: row-resize;
  }

  .dock-zone {
    position: fixed;
    z-index: 55;
    display: grid;
    place-items: center;
    border-radius: 12px;
    border: 2px dashed var(--accent);
    background: rgb(0 122 255 / 0.08);
    color: var(--accent);
    font-weight: 600;
    pointer-events: none;
    transition: background 0.12s;
  }

  .dock-zone.on {
    background: rgb(0 122 255 / 0.22);
  }

  .dock-zone.side {
    top: 70px;
    right: 10px;
    bottom: 240px;
    width: 40%;
  }

  .dock-zone.bottom {
    left: 10px;
    right: 10px;
    bottom: 10px;
    height: 200px;
  }

  .drop {
    position: relative;
    margin-left: 4px;
  }

  .pill {
    display: flex;
    align-items: center;
    gap: 4px;
    height: 26px;
    padding: 0 8px;
    border-radius: 7px;
    color: var(--secondary);
    font-size: 12px;
    font-weight: 500;
  }

  .pill:hover,
  .pill.on {
    background: var(--hover);
    color: var(--text);
  }

  /* Park stands out: a purple button (text like the other buttons); on hover a light streak
     sweeps across it from left to right. */
  .pill.park {
    position: relative;
    overflow: hidden;
    margin-left: 4px;
    /* Same purple as the outline, dark on the left to light on the right. */
    background: linear-gradient(90deg, rgb(120 50 190 / 0.45), rgb(200 130 250 / 0.45));
    box-shadow:
      inset 0 0 0 1px rgb(175 82 222 / 0.45),
      0 0 6px rgb(175 82 222 / 0.18);
    transition: box-shadow 0.2s, filter 0.2s;
  }

  .pill.park:hover,
  .pill.park.on {
    filter: brightness(1.15);
    box-shadow:
      inset 0 0 0 1px rgb(175 82 222 / 0.6),
      0 0 8px rgb(175 82 222 / 0.28);
  }

  .pill.park::after {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(105deg, transparent 35%, rgb(255 255 255 / 0.4) 50%, transparent 65%);
    transform: translateX(-110%);
    pointer-events: none;
  }

  .pill.park:hover::after {
    transform: translateX(110%);
    transition: transform 0.6s ease-out;
  }

  .ai-drop {
    display: flex;
    margin-left: 0;
  }

  .tool.caret {
    width: 16px;
    margin-left: -3px;
  }

  .menu.ai-tools {
    width: 270px;
  }

  .menu.ai-tools button {
    flex-direction: column;
    padding: 5px 10px;
  }

  .menu.ai-tools .sub {
    font-size: 11px;
    opacity: 0.75;
    white-space: normal;
  }

  .mini-clock {
    font-variant-numeric: tabular-nums;
    color: var(--accent);
    font-weight: 600;
  }

  .mini-clock.break {
    color: #34c759;
  }

  .mini-clock.paused {
    opacity: 0.6;
  }

  .zen-exit {
    position: fixed;
    top: 8px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 30;
    padding: 4px 14px;
    border-radius: 14px;
    background: var(--popover);
    backdrop-filter: blur(20px);
    box-shadow: 0 0 0 0.5px var(--separator);
    font-size: 12px;
    color: var(--secondary);
    opacity: 0;
    transition: opacity 0.2s;
  }

  .zen-exit:hover,
  .zen-exit:focus-visible {
    opacity: 1;
  }

  .tools {
    display: flex;
    gap: 2px;
    padding-right: 4px;
    margin-right: 2px;
    border-right: 0.5px solid var(--separator);
  }

  .edited {
    margin-left: 0.35em;
    font-weight: 400;
    color: var(--secondary);
  }

  .subtitle.static {
    cursor: default;
  }

  .sheet-backdrop {
    position: fixed;
    inset: 0;
    z-index: 60;
    display: grid;
    place-items: start center;
    padding-top: 90px;
    background: rgb(0 0 0 / 0.18);
  }

  .sheet {
    width: 340px;
    padding: 20px 20px 16px;
    border-radius: 14px;
    background: var(--popover);
    backdrop-filter: saturate(180%) blur(30px);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 20px 50px rgb(0 0 0 / 0.3);
    text-align: center;
    animation: sheet-in 0.16s ease-out;
  }

  @keyframes sheet-in {
    from {
      opacity: 0;
      transform: translateY(-8px) scale(0.98);
    }
  }

  .sheet-icon {
    width: 52px;
    height: 52px;
    margin: 0 auto 10px;
    border-radius: 13px;
    display: grid;
    place-items: center;
    font: 700 22px/1 var(--font);
    color: white;
    background: linear-gradient(160deg, #5e9bff, #3a55e8 55%, #6a3fd8);
  }

  .sheet h2 {
    margin: 0;
    font-size: 13px;
    font-weight: 600;
  }

  .sheet p {
    margin: 6px 0 16px;
    font-size: 12px;
    color: var(--secondary);
  }

  .sheet-actions {
    display: flex;
    gap: 8px;
  }

  .sheet-actions .grow {
    flex: 1;
  }

  .sheet-actions button {
    padding: 4px 12px;
    border-radius: 6px;
    font-weight: 500;
  }

  .sheet-actions .plain {
    background: var(--hover);
  }

  .sheet-actions .default {
    background: var(--accent);
    color: var(--accent-text);
  }

  /* Side groups take what they need; the title gets the rest and truncates — nothing overlaps.
     As the window narrows, groups collapse into the ⋯ menu (container queries below). */
  .toolbar {
    height: var(--toolbar-height);
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 12px;
    padding: 0 10px;
    container: toolbar / inline-size;
  }

  .narrow-tools,
  .narrow-zoom {
    display: none;
  }

  .menu .narrow-tools button[aria-checked="true"]::before,
  .menu .narrow-zoom button[aria-checked="true"]::before {
    content: "✓";
    position: absolute;
    left: 7px;
  }

  @container toolbar (max-width: 1280px) {
    .pill-label {
      display: none;
    }
  }

  @container toolbar (max-width: 1120px) {
    .search {
      flex-basis: 130px;
    }
  }

  @container toolbar (max-width: 1020px) {
    .tools {
      display: none;
    }
    .narrow-tools {
      display: block;
    }
  }

  @container toolbar (max-width: 860px) {
    .zoom,
    .dark {
      display: none !important;
    }
    .narrow-zoom {
      display: block;
    }
  }

  @container toolbar (max-width: 720px) {
    .search {
      flex: 0 0 30px;
      min-width: 30px;
      padding: 0 8px;
      cursor: pointer;
    }
    .search input,
    .search .count {
      display: none;
    }
    .search:focus-within {
      position: absolute;
      right: 10px;
      z-index: 22;
      width: 220px;
      background: var(--popover-solid);
      box-shadow:
        0 0 0 0.5px var(--separator),
        0 0 0 3px var(--focus-ring);
    }
    .search:focus-within input,
    .search:focus-within .count {
      display: block;
    }
  }

  @container toolbar (max-width: 600px) {
    .nav {
      display: none;
    }
  }

  .group {
    display: flex;
    align-items: center;
    gap: 2px;
    min-width: 0;
  }

  .group.end {
    justify-content: flex-end;
    gap: 6px;
  }

  .tool {
    flex: none;
    display: grid;
    place-items: center;
    width: 32px;
    height: 28px;
    border-radius: var(--radius-s);
    color: var(--secondary);
  }

  .tool:hover:not(:disabled) {
    background: var(--hover);
    color: var(--text);
  }

  .tool:active:not(:disabled),
  .tool.on {
    background: var(--pressed);
    color: var(--text);
  }

  .tool:disabled {
    opacity: 0.35;
  }

  .title {
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 0;
    text-align: center;
  }

  .name {
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
  }

  .subtitle {
    font-size: 11px;
    color: var(--secondary);
    border-radius: 4px;
    padding: 0 4px;
  }

  button.subtitle:hover {
    background: var(--hover);
  }

  .goto {
    width: 4em;
    font: inherit;
    text-align: center;
    color: var(--text);
    background: var(--surface);
    border: none;
    border-radius: 4px;
    outline: 2px solid var(--focus-ring);
  }

  .segmented {
    position: relative;
    flex: none;
    display: flex;
    align-items: center;
    height: 26px;
    border-radius: var(--radius-s);
    background: var(--hover);
  }

  .segmented > button {
    display: grid;
    place-items: center;
    min-width: 28px;
    height: 100%;
    border-radius: var(--radius-s);
  }

  .segmented > button:hover {
    background: var(--hover);
  }

  .zoom-label {
    min-width: 48px !important;
    font-size: 12px;
    font-variant-numeric: tabular-nums;
  }

  .menu-backdrop {
    position: fixed;
    inset: 0;
    z-index: 20;
  }

  .menu {
    position: absolute;
    top: calc(100% + 6px);
    left: 50%;
    transform: translateX(-50%);
    z-index: 21;
    min-width: 170px;
    padding: 5px;
    border-radius: 9px;
    background: var(--popover-solid);
    backdrop-filter: saturate(180%) blur(24px);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 8px 28px rgb(0 0 0 / 0.22);
  }

  .menu button {
    display: flex;
    justify-content: space-between;
    width: 100%;
    padding: 3px 10px 3px 22px;
    border-radius: 5px;
    text-align: left;
    position: relative;
  }

  .menu button[aria-checked="true"]::before {
    content: "✓";
    position: absolute;
    left: 7px;
  }

  .menu button:hover:not(:disabled) {
    background: var(--accent);
    color: var(--accent-text);
  }

  .menu button:disabled {
    opacity: 0.4;
  }

  .more {
    position: relative;
  }

  .menu.right {
    left: auto;
    right: 0;
    transform: none;
    min-width: 220px;
  }

  .menu-sep {
    height: 0.5px;
    margin: 4px 6px;
    background: var(--separator);
  }

  .toast button.action {
    padding: 2px 10px;
    border-radius: 6px;
    background: var(--accent);
    color: var(--accent-text);
    font-weight: 500;
  }

  .shortcut {
    color: var(--tertiary);
  }

  .menu button:hover .shortcut {
    color: inherit;
  }

  .search {
    flex: 0 1 190px;
    min-width: 90px;
    display: flex;
    align-items: center;
    gap: 5px;
    height: 26px;
    padding: 0 8px;
    border-radius: 7px;
    background: var(--hover);
    color: var(--secondary);
  }

  .search:focus-within {
    box-shadow: 0 0 0 3px var(--focus-ring);
  }

  .search input {
    flex: 1;
    min-width: 0;
    border: none;
    outline: none;
    background: none;
    font: inherit;
    color: var(--text);
  }

  .count {
    font-size: 11px;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  .hint {
    width: 100%;
    text-align: center;
    color: var(--secondary);
  }

  .toast {
    position: absolute;
    left: 50%;
    bottom: 20px;
    transform: translateX(-50%);
    z-index: 30;
    display: flex;
    align-items: center;
    gap: 10px;
    max-width: 80%;
    padding: 8px 12px;
    border-radius: 10px;
    background: var(--popover);
    backdrop-filter: blur(20px);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 6px 24px rgb(0 0 0 / 0.2);
  }

  .toast.error {
    color: #ff3b30;
  }
</style>
