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
  import PrintSheet from "./lib/PrintSheet.svelte";
  import { loadTheme, theme } from "./lib/theme.svelte";
  import { loadPrefs, prefs } from "./lib/prefs.svelte";
  import { checkAtStart } from "./lib/updates";
  import AskSheets from "./lib/AskSheets.svelte";
  import { appCommands, typedCommands } from "./lib/commands";
  import { handleShortcut } from "./lib/shortcuts";
  import { askCloseChoice, askPassword, asking, type CloseChoice } from "./lib/ask.svelte";
  import PdfTools from "./lib/PdfTools.svelte";
  import BookView from "./lib/focus/BookView.svelte";
  import AiPanel from "./lib/ai/AiPanel.svelte";
  import CommandPalette from "./lib/CommandPalette.svelte";
  import type { SnipKind } from "./lib/ai/equation.svelte";
  import { citation } from "./lib/cite";
  import { loadInk, loadTextStyle } from "./lib/tab.svelte";
  import { loadAppFont } from "./lib/md/typography.svelte";
  import TerminalGuide from "./lib/ai/TerminalGuide.svelte";
  import {
    HEADER_HEIGHT,
    closeTerminal,
    loadLayout,
    openTerminal,
    saveLayout,
    term,
  } from "./lib/ai/terminal.svelte";
  import ParkingLot from "./lib/focus/ParkingLot.svelte";
  import {
    loadPace,
    loadPomodoroSettings,
    flushReading,
    loadReadSettings,
    noteActivity,
    notePage,
    tickReading,
    read,
  } from "./lib/reading.svelte";
  import LinkPeek, { type Peek } from "./lib/LinkPeek.svelte";
  import PaneView from "./lib/PaneView.svelte";
  import Sidebar, { type SidebarMode } from "./lib/Sidebar.svelte";
  import MdSidebar, { type MdSidebarMode } from "./lib/md/MdSidebar.svelte";
  import Toolbar from "./lib/Toolbar.svelte";
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
  let mdSidebarMode = $state<MdSidebarMode>("contents");
  let palette = $state(false);
  // The palette lists the bookmarks of the focused PDF.
  $effect(() => {
    if (palette) active?.loadBookmarks();
  });
  // Fewer animations (Settings → Appearance), applied to the whole window.
  $effect(() => void document.documentElement.classList.toggle("reduce-motion", ui.reduceMotion));
  let restored = $state(false);

  let toolbarHeight = $state(52);
  let panesEl = $state<HTMLElement>();
  const viewers = new Map<number, Viewer>();
  let peek = $state<Peek | null>(null);

  let toolbar = $state<Toolbar>();
  let pdfTools = $state<PdfTools>();
  let parking = $state(false);

  /** Focused tab of any kind; `active` is the same tab when it is a PDF. */
  const current = $derived(ws.activeTab);
  const active = $derived(current?.kind === "pdf" ? (current as Tab) : null);
  const sidebarShown = $derived(sidebarOpen && !read.zen);
  const note = $derived(current?.kind === "md" ? (current as MdTab) : null);

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
        const py = await api();
        let doc = await py.open_document(path);
        while ("needsPassword" in doc) {
          const password = await askPassword(path.split(/[\/]/).pop() ?? path, doc.wrong);
          if (password === null) return null;
          doc = await py.open_document(path, password);
        }
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

  // --- export & the vault -------------------------------------------------------------------------

  /** Write a note into the vault; if it exists, offer to replace it. */
  async function toVault(title: string, text: string) {
    const py = await api();
    if (!(await py.get_setting("obsidian.vault", null))) {
      notify.show({ text: "Choose your vault first (Settings → Vault).", action: { label: "Settings", run: () => (ui.settingsOpen = true) } });
      return;
    }
    const open = (path: string) => ({ label: "Open", run: () => py.open_in_vault(path) });
    const result = await py.obsidian_write(title, text);
    if (result.written) notify.show({ text: `Saved to vault · ${title}.md`, action: open(result.path) });
    else
      notify.show({
        text: `“${title}.md” already exists in the vault.`,
        action: {
          label: "Replace",
          run: async () => {
            const r = await py.obsidian_write(title, text, true);
            notify.show({ text: `Replaced in vault · ${title}.md`, action: open(r.path) });
          },
        },
      });
  }

  async function exportMarkdown(target: "file" | "vault") {
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
    if (note) return toVault(note.title, note.md.text);
    if (active) {
      const md = await active.ensureMd();
      await md.flush();
      return toVault(active.title, md.text);
    }
  }

  async function recognizeAll() {
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
    if (read.zen) notify.show({ text: kbd("Zen mode: press Esc or Ctrl+. to exit.") }, 3000);
  }

  async function toggleFullscreen() {
    read.fullscreen = !read.fullscreen;
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
  $effect(() => void (term.docFolder = docFolder)); // for the terminal's "PDF folder" button
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
    if (!active) return;
    const n = await active.exportHighlightsToNote();
    notify.show({ text: `${n} highlight${n === 1 ? "" : "s"} written under the line in ${active.md?.name}.` });
  }

  /** Equation → LaTeX / Image → AI: draw a rectangle on the page (see EquationSnip). */
  function startSnip(kind: SnipKind = "equation") {
    if (!active) return;
    active.tool = "select";
    active.snipping = kind;
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

  const commands = $derived(
    appCommands({
      active, invert, recents, docFolder, paneId: ws.focused.id, viewer,
      saveCurrent, undo, redo, toggleBookmark, exportHighlights, exportMarkdown, copyNoteToVault, recognizeAll,
      setFit, toggleInvert, toggleSidebar, stopGrading, toggleZen, toggleFullscreen, toggleTerminal, startSnip, openPath,
      showBookmarks: () => ((sidebarOpen = true), (sidebarMode = "bookmarks")),
      startGrading: () => startGrading(),
      park: () => (parking = true),
      openAiMenu: () => toolbar?.openAiMenu(),
      pickAndOpen: () => pickAndOpen(),
      newNote: () => newNote(),
      newTab: () => newTab(),
    }),
  ); // prettier-ignore

  async function saveCurrent() {
    if (active === grading.session?.tab) grading.session?.commit(); // typed grade / name
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
    // Settings → General: save without asking.
    if (prefs.unsaved === "save") {
      await tab.save();
      return "save";
    }
    const choice = await askCloseChoice(tab);
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
    // An undocked window's only tab may leave too: dropped onto a PhDF window, it goes back.
    if (target.kind === "window") return ws.tabCount > 1 || !!info?.detached;
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
      else if (ws.tabCount === 1) return; // undocked window: it already is its own window
      else await py.open_window([tab.path], target.screenX - 160, target.screenY - 20, true);
      ws.remove(tab);
      await releaseDocument(tab);
      return;
    }
    const pane = ws.pane(target.paneId)!;
    if (target.kind === "bar") ws.move(tab, pane, target.index);
    else if (target.kind === "into") ws.move(tab, pane, pane.tabs.length);
    else ws.split(tab, pane, target.side);
  }

  /** Detached window: its tabs go back to the main window, then it closes. */
  async function dock() {
    const tabs = ws.allTabs();
    for (const t of tabs) await t.md?.flush();
    const py = await api();
    await py.dock(tabs.map((t) => t.path));
    for (const t of tabs) {
      ws.remove(t);
      await releaseDocument(t);
    }
    await py.close_window();
  }

  // A detached window whose last tab was closed has nothing left to show.
  $effect(() => {
    if (restored && info?.detached && ws.tabCount === 0) api().then((py) => py.close_window());
  });

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

  // --- zoom & view ----------------------------------------------------------------------------

  function setFit(mode: FitMode) {
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

  function onKeydown(e: KeyboardEvent) {
    handleShortcut(e, {
      active, current, viewer, toggleTerminal, toggleZen, toggleFullscreen, saveCurrent, undo, redo, toggleBookmark,
      copyWithCitation, closeTab, cycleTab, toggleSidebar,
      dialogOpen: !!(asking.password || asking.close || ui.print || ui.settingsOpen),
      peekOpen: !!peek,
      parkingOpen: parking,
      toggleParking: () => (parking = !parking),
      pickAndOpen: () => pickAndOpen(),
      togglePalette: () => (palette = !palette),
      newTab: () => newTab(),
      focusSearch: () => toolbar?.focusSearch(),
      startGoto: () => toolbar?.startGoto(),
    }); // prettier-ignore
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
    const sidebar = { open: sidebarOpen, mode: sidebarMode, mdMode: mdSidebarMode };
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
    if (appInfo.smoke) reportReady(); // watches on its own: a later start-up step may stall
    // Each call is a round trip to the backend: ask for all the settings at once.
    await Promise.all([
      py.get_setting("invertPages", false).then((v) => (invert = v)),
      py.get_setting("ui.reduceMotion", matchMedia("(prefers-reduced-motion: reduce)").matches).then((v) => (ui.reduceMotion = v)),
      loadReadSettings(), loadPomodoroSettings(), loadPace(), loadLayout(), loadInk(), loadTextStyle(), loadGradingSettings(), loadAppFont(),
    ]); // prettier-ignore
    // Light / dark theme (also colors the Windows title bar); dark pages follow it if asked.
    addEventListener("phdf:theme", (e) => {
      const dark = (e as CustomEvent<boolean>).detail;
      if (theme.autoDarkPages && invert !== dark) invert = dark;
    });
    await Promise.all([loadTheme(), loadPrefs()]);
    // E-books laid out again (Read menu → text size): update their tabs.
    window.addEventListener("phdf:reflow", (e) => {
      for (const change of (e as CustomEvent<{ docId: string; pageSizes: [number, number][]; revs: Record<number, number> }[]>).detail) {
        for (const tab of ws.allTabs()) if (tab.kind === "pdf" && tab.doc.docId === change.docId) tab.reflow(change);
      }
    });
    // The same document changed in another tab or window: marks, save state, layout.
    type DocChange = { docId: string; dirty: boolean; revs: Record<number, number>; source?: Tab };
    window.addEventListener("phdf:doc-changed", (e) => {
      const c = (e as CustomEvent<DocChange>).detail;
      for (const tab of ws.allTabs()) if (tab.kind === "pdf" && tab !== c.source && tab.doc.docId === c.docId) tab.sync(c);
    });
    window.addEventListener("phdf:doc-reflowed", (e) => {
      const c = (e as CustomEvent<{ docId: string; pageSizes: [number, number][]; revs: Record<number, number> }>).detail;
      for (const tab of ws.allTabs()) if (tab.kind === "pdf" && tab.doc.docId === c.docId) tab.reflow(c);
    });
    window.addEventListener("phdf:doc-sizes", (e) => {
      const c = (e as CustomEvent<{ docId: string; pageSizes: [number, number][] }>).detail;
      for (const tab of ws.allTabs()) if (tab.kind === "pdf" && tab.doc.docId === c.docId) tab.resize(c.pageSizes);
    });
    // First start: show the tour once.
    if (!(await (await api()).get_setting("help.seen", false))) {
      ui.helpOpen = true;
      (await api()).set_setting("help.seen", true);
    }
    const sidebar = await py.get_setting<{ open: boolean; mode: SidebarMode; mdMode?: MdSidebarMode }>("sidebar", { open: false, mode: "pages" });
    sidebarOpen = sidebar.open;
    sidebarMode = sidebar.mode;
    mdSidebarMode = sidebar.mdMode ?? "contents";
    // Settings → General → "Reopen my last tabs" (an undocked window always shows its tab).
    if (prefs.restore || appInfo.detached) await restoreSession(appInfo.windowId);
    if (appInfo.windowId === "main") checkAtStart();
    setInterval(() => tickReading(), 1000);
    for (const type of ["pointermove", "keydown", "wheel", "pointerdown"]) {
      window.addEventListener(type, () => noteActivity(), { passive: true, capture: true });
    }
    // Closing the window with unsaved annotations: the backend held the close and asks us.
    // The window's close button: the backend always asks here first (notes being typed,
    // grades, PDF Tools work and unsaved marks are only known to the page).
    window.addEventListener("phdf:close-request", async () => {
      const py = await api();
      py.close_ack();
      if (pdfTools && !(await pdfTools.settle())) return;
      for (const t of ws.allTabs()) {
        if (t.kind === "pdf" && t.dirty && (await askSave(t)) === "cancel") return;
      }
      grading.session?.commit();
      for (const t of ws.allTabs()) {
        await t.md?.flush();
        if (t.kind === "pdf") await t.parking?.flush();
      }
      flushReading();
      py.close_window();
    });
    // A tab dragged here from another PhDF window.
    window.addEventListener("phdf:open-path", (e) => openPath((e as CustomEvent<string>).detail));
    // A link in a note (or anywhere in the UI) never takes over the app window: web pages open
    // in the large preview window, other targets are ignored. In-page `#` links still work.
    document.addEventListener("click", (e) => {
      const a = (e.target as Element).closest?.("a[href]") as HTMLAnchorElement | null;
      if (!a || e.defaultPrevented || a.getAttribute("href")!.startsWith("#")) return;
      e.preventDefault();
      if (/^https?:/i.test(a.href)) api().then((py) => py.peek_url(a.href, true));
      else if (/^mailto:/i.test(a.href)) api().then((py) => py.open_external(a.href));
    });
    window.addEventListener("beforeunload", () => flushReading());
    // Notes may be edited in another app meanwhile: reload them when we come back.
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

  /** Release CI (`PhDF --smoke-ui <file>`): tell the backend once a page image is really on
   *  screen, so a blank window or a broken bridge fails the check instead of passing it. */
  async function reportReady() {
    const end = Date.now() + 75_000; // the backend gives up at 90 s
    let shown = false;
    while (!shown && Date.now() < end) {
      const img = document.querySelector<HTMLImageElement>("img[src*='/page/']");
      shown = !!img?.complete && img.naturalWidth > 0;
      if (!shown) await new Promise((r) => setTimeout(r, 250));
    }
    (await api()).ui_ready({ tabs: ws.allTabs().length, pageImage: shown, pages: active?.pageCount ?? 0 });
  }
</script>

<svelte:window onkeydown={onKeydown} />

<div class="window" class:dragging={drag.tab}>
  {#if sidebarShown && current?.kind === "md"}
    <div class="sidebar" style="width:{SIDEBAR_WIDTH}px">
      <MdSidebar md={current.md} mode={mdSidebarMode} onmode={(m) => (mdSidebarMode = m)} onopen={(p) => openPath(p)} />
    </div>
  {:else if active && sidebarShown}
    <div class="sidebar" style="width:{SIDEBAR_WIDTH}px">
      <Sidebar tab={active} mode={sidebarMode} {invert} onmode={setSidebarMode} />
    </div>
  {/if}

  <div class="main" style="left:{sidebarShown && (active || current?.kind === "md") ? SIDEBAR_WIDTH : 0}px">
    <header bind:clientHeight={toolbarHeight} class:hidden={read.zen}>
      <Toolbar
        bind:this={toolbar}
        {active}
        {note}
        ready={!!info}
        {invert}
        {parking}
        paneId={ws.focused.id}
        {viewer}
        ontogglesidebar={toggleSidebar}
        cansidebar={!!active || current?.kind === "md"}
        onzen={toggleZen}
        onfullscreen={toggleFullscreen}
        onpark={() => (parking = !parking)}
        onsetfit={setFit}
        oninvert={toggleInvert}
        onsnip={startSnip}
        onterminal={toggleTerminal}
        ongrading={toggleGrading}
        onstopgrading={stopGrading}
        onexporthighlights={exportHighlights}
        onexportmarkdown={exportMarkdown}
        oncopynote={copyNoteToVault}
        onsave={saveCurrent}
        onrecognize={recognizeAll}
        onopen={() => pickAndOpen()}
        onhome={() => newTab()}
        ondock={info?.detached ? dock : undefined}
      />
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
            onpark={() => (parking = true)}
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
    <CommandPalette commands={commands} dynamic={(q) => typedCommands(q, active)} onclose={() => (palette = false)} />
  {/if}

  {#if term.guideOpen}
    <TerminalGuide onclose={() => (term.guideOpen = false)} />
  {/if}

  {#if read.book && active}
    <BookView tab={active} {invert} top={read.zen ? 0 : toolbarHeight} onclose={() => (read.book = false)} />
  {/if}
  {#if ui.tools}
    <PdfTools bind:this={pdfTools} path={ui.tools.path} onopenpath={(p) => openPath(p)} onclose={() => (ui.tools = null)} />
  {/if}
  {#if ui.helpOpen}
    <Help onclose={() => (ui.helpOpen = false)} />
  {/if}

  {#if ui.settingsOpen}
    <Settings onclose={() => (ui.settingsOpen = false)} />
  {/if}

  {#if ui.print && active}
    <PrintSheet tab={active} onclose={() => (ui.print = false)} />
  {/if}

  <AskSheets />
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
    z-index: 11; /* above the book view (10), so its menus open on top of it */
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
    border-radius: 10px;
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
    border-radius: 16px;
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

  .zen-exit {
    position: fixed;
    top: 8px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 30;
    padding: 4px 14px;
    border-radius: 18px;
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

  .toast button.action {
    padding: 2px 10px;
    border-radius: 8px;
    background: var(--accent);
    color: var(--accent-text);
    font-weight: 500;
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
    border-radius: 13px;
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
