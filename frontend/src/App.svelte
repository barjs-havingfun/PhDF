<script lang="ts">
  // App shell: toolbar, sidebar, side-by-side panes with tabs, tab drag & drop, link peek,
  // keyboard shortcuts and per-window session restore.
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
  import LinkPeek, { type Peek } from "./lib/LinkPeek.svelte";
  import PaneView from "./lib/PaneView.svelte";
  import Sidebar from "./lib/Sidebar.svelte";
  import { Tab } from "./lib/tab.svelte";
  import type Viewer from "./lib/viewer/Viewer.svelte";
  import { Pane, Workspace } from "./lib/workspace.svelte";

  const SIDEBAR_WIDTH = 232;
  const MIN_PANE_WIDTH = 220;

  interface SavedPane {
    paths: string[];
    active: number;
    width: number;
  }
  interface SavedSession {
    panes: SavedPane[];
    focused: number;
  }

  let info = $state<AppInfo | null>(null);
  const ws = new Workspace();
  let recents = $state<RecentDocument[]>([]);
  let error = $state<string | null>(null);

  let invert = $state(false);
  let sidebarOpen = $state(false);
  let sidebarMode = $state<"outline" | "pages">("pages");
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

  const active = $derived(ws.activeTab);
  const viewer = () => viewers.get(ws.focused.id);

  // --- documents & tabs -----------------------------------------------------------------------

  async function refreshRecents() {
    recents = await (await api()).recent_documents(12);
  }

  async function openPath(path: string, pane: Pane = ws.focused, activate = true) {
    error = null;
    try {
      const doc = await (await api()).open_document(path);
      let tab = ws.findByDoc(doc.docId);
      if (!tab) {
        tab = new Tab(doc);
        ws.add(tab, pane);
      }
      if (activate) ws.activate(tab);
      refreshRecents();
    } catch (e) {
      error = `Could not open ${path}: ${e}`;
    }
  }

  async function pickAndOpen(pane: Pane = ws.focused) {
    const path = await (await api()).pick_pdf();
    if (path) await openPath(path, pane);
  }

  function selectTab(tab: Tab) {
    ws.activate(tab);
    peek = null;
  }

  async function closeTab(tab: Tab) {
    ws.remove(tab);
    if (peek?.tab === tab) peek = null;
    (await api()).close_document(tab.doc.docId);
    if (!ws.activeTab) refreshRecents();
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

  function acceptDrop(tab: Tab, target: DropTarget): boolean {
    if (target.kind === "window") return ws.tabCount > 1;
    const pane = ws.pane(target.paneId);
    if (!pane) return false;
    if (target.kind === "split") return ws.canSplit(tab, pane);
    if (target.kind === "into") return !pane.tabs.includes(tab);
    return true;
  }

  async function dropTab(tab: Tab, target: DropTarget) {
    if (target.kind === "window") {
      // Tear off: the new window opens the document itself, then this window lets it go.
      await (await api()).open_window([tab.doc.path], target.screenX - 160, target.screenY - 20);
      await closeTab(tab);
      return;
    }
    const pane = ws.pane(target.paneId)!;
    if (target.kind === "bar") ws.move(tab, pane, target.index);
    else if (target.kind === "into") ws.move(tab, pane, pane.tabs.length);
    else ws.split(tab, pane, target.side);
  }

  function onTabDragStart(e: PointerEvent, tab: Tab) {
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

  function setSidebarMode(mode: "outline" | "pages") {
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

    if (mod && key === "o") pickAndOpen();
    else if (mod && key === "t") newTab();
    else if (mod && key === "w") active && closeTab(active);
    else if (mod && key === "tab") cycleTab(e.shiftKey ? -1 : 1);
    else if (mod && key === "f" && active) searchInput?.focus();
    else if (mod && key === "g" && active) startGoto();
    else if (mod && (key === "=" || key === "+") && active) viewer()?.zoomBy(1.2);
    else if (mod && key === "-" && active) viewer()?.zoomBy(1 / 1.2);
    else if (mod && key === "0" && active) viewer()?.setZoom(1);
    else if (mod && key === "\\") toggleSidebar();
    else if (e.altKey && key === "arrowleft") active?.goBack();
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
        paths: p.tabs.map((t) => t.doc.path),
        active: p.tabs.findIndex((t) => t.id === p.activeId),
        width: p.width,
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
      for (const path of saved.paths) await openPath(path, pane, false);
      pane.activeId = pane.tabs[saved.active]?.id ?? pane.tabs[0]?.id ?? null;
    }
    // Drop panes whose files have all gone missing.
    if (ws.panes.length > 1) ws.panes = ws.panes.filter((p) => p.tabs.length);
    if (!ws.panes.length) ws.panes = [new Pane()];
    ws.focusedId = (ws.panes[session.focused] ?? ws.panes[0]).id;
    error = null; // files that moved away since last time are just skipped
  }

  onMount(async () => {
    const py = await api();
    const appInfo = await py.app_info();
    setRenderBaseUrl(appInfo.renderBaseUrl);
    invert = await py.get_setting("invertPages", false);
    const sidebar = await py.get_setting("sidebar", { open: false, mode: "pages" as const });
    sidebarOpen = sidebar.open;
    sidebarMode = sidebar.mode;
    await restoreSession(appInfo.windowId);
    await refreshRecents();
    info = appInfo;
    restored = true;
  });
</script>

<svelte:window onkeydown={onKeydown} />

<div class="window" class:dragging={drag.tab}>
  {#if active && sidebarOpen}
    <div class="sidebar" style="width:{SIDEBAR_WIDTH}px">
      <Sidebar tab={active} mode={sidebarMode} {invert} onmode={setSidebarMode} />
    </div>
  {/if}

  <div class="main" style="left:{active && sidebarOpen ? SIDEBAR_WIDTH : 0}px">
    <header bind:clientHeight={toolbarHeight}>
      <div class="toolbar">
        <div class="group">
          <button class="tool" title="Sidebar (Ctrl+\)" onclick={toggleSidebar} disabled={!active}>
            <Icon name="sidebar" />
          </button>
          <button class="tool" title="Back (Alt+←)" onclick={() => active?.goBack()} disabled={!active?.back.length}>
            <Icon name="left" />
          </button>
          <button
            class="tool"
            title="Forward (Alt+→)"
            onclick={() => active?.goForward()}
            disabled={!active?.forward.length}
          >
            <Icon name="right" />
          </button>
        </div>

        <div class="title">
          {#if active}
            <span class="name">{active.doc.title}</span>
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
              <button class="subtitle" onclick={startGoto} title="Go to page (Ctrl+G)">
                Page {active.page + 1} of {active.pageCount}
              </button>
            {/if}
          {:else}
            <span class="name">PhDF</span>
          {/if}
        </div>

        <div class="group end">
          {#if active}
            <div class="segmented">
              <button title="Zoom out (Ctrl+-)" onclick={() => viewer()?.zoomBy(1 / 1.2)}>
                <Icon name="minus" size={14} />
              </button>
              <button class="zoom-label" onclick={() => (zoomMenu = !zoomMenu)} title="Zoom options">
                {Math.round(active.zoom * 100)}%
              </button>
              <button title="Zoom in (Ctrl++)" onclick={() => viewer()?.zoomBy(1.2)}>
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
                    Actual Size <span class="shortcut">Ctrl+0</span>
                  </button>
                </div>
              {/if}
            </div>

            <button class="tool" class:on={invert} title="Dark pages" onclick={toggleInvert}>
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
          <button class="tool" title="Open PDF (Ctrl+O)" onclick={() => pickAndOpen()} disabled={!info}>
            <Icon name="open" />
          </button>
        </div>
      </div>
    </header>

    <div class="panes" bind:this={panesEl}>
      {#if info}
        {#each ws.panes as pane, i (pane.id)}
          {#if i > 0}
            <div class="divider" role="separator" aria-orientation="vertical" onpointerdown={(e) => startResize(e, i)}></div>
          {/if}
          <PaneView
            {pane}
            focused={pane.id === ws.focused.id}
            multi={ws.panes.length > 1}
            {toolbarHeight}
            {invert}
            version={info.version}
            {recents}
            onfocus={() => ws.focus(pane)}
            onopen={() => pickAndOpen(pane)}
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

    {#if error}
      <div class="toast" role="alert">
        {error}
        <button onclick={() => (error = null)} aria-label="Dismiss"><Icon name="close" size={12} /></button>
      </div>
    {/if}
  </div>

  {#if drag.tab}
    <div class="ghost" style="left:{drag.x + 14}px;top:{drag.y + 10}px">
      <Icon name="doc" size={14} />
      <span>{drag.tab.doc.title}</span>
      {#if drag.target?.kind === "window"}<span class="ghost-hint">New Window</span>{/if}
    </div>
  {/if}

  {#if peek}
    <LinkPeek {peek} {invert} onclose={() => (peek = null)} />
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

  .toolbar {
    height: var(--toolbar-height);
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    align-items: center;
    gap: 12px;
    padding: 0 10px;
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
    max-width: 36vw;
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
    background: var(--popover);
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

  .menu button:hover {
    background: var(--accent);
    color: var(--accent-text);
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
    color: #ff3b30;
  }
</style>
