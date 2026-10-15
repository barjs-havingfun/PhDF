<script lang="ts">
  // App shell: toolbar, tabs, sidebar, viewer, link peek, keyboard shortcuts and session restore.
  import { onMount } from "svelte";
  import {
    api,
    setRenderBaseUrl,
    type AppInfo,
    type FitMode,
    type PdfLink,
    type RecentDocument,
  } from "./lib/api";
  import Icon from "./lib/Icon.svelte";
  import LinkPeek, { type Peek } from "./lib/LinkPeek.svelte";
  import Sidebar from "./lib/Sidebar.svelte";
  import { Tab } from "./lib/tab.svelte";
  import TabBar from "./lib/TabBar.svelte";
  import Viewer from "./lib/viewer/Viewer.svelte";
  import Welcome from "./lib/Welcome.svelte";

  const SIDEBAR_WIDTH = 232;

  let info = $state<AppInfo | null>(null);
  let tabs = $state<Tab[]>([]);
  let activeId = $state<number | null>(null);
  let recents = $state<RecentDocument[]>([]);
  let error = $state<string | null>(null);

  let invert = $state(false);
  let sidebarOpen = $state(false);
  let sidebarMode = $state<"outline" | "pages">("pages");
  let restored = $state(false);

  let headerHeight = $state(52);
  let viewer = $state<Viewer>();
  let peek = $state<Peek | null>(null);

  let searchInput = $state<HTMLInputElement>();
  let searchText = $state("");
  let gotoInput = $state<HTMLInputElement>();
  let editingPage = $state(false);
  let zoomMenu = $state(false);

  const active = $derived(tabs.find((t) => t.id === activeId) ?? null);

  // --- documents & tabs -----------------------------------------------------------------------

  async function refreshRecents() {
    recents = await (await api()).recent_documents(12);
  }

  async function openPath(path: string, activate = true) {
    error = null;
    try {
      const doc = await (await api()).open_document(path);
      let tab = tabs.find((t) => t.doc.docId === doc.docId);
      if (!tab) {
        tab = new Tab(doc);
        tabs.push(tab);
      }
      if (activate) activeId = tab.id;
      refreshRecents();
    } catch (e) {
      error = `Could not open ${path}: ${e}`;
    }
  }

  async function pickAndOpen() {
    const path = await (await api()).pick_pdf();
    if (path) await openPath(path);
  }

  function selectTab(id: number) {
    activeId = id;
    peek = null;
  }

  async function closeTab(id: number) {
    const i = tabs.findIndex((t) => t.id === id);
    if (i < 0) return;
    const [tab] = tabs.splice(i, 1);
    if (activeId === id) activeId = (tabs[i] ?? tabs[i - 1])?.id ?? null;
    (await api()).close_document(tab.doc.docId);
    if (activeId === null) refreshRecents();
  }

  function newTab() {
    activeId = null;
    refreshRecents();
  }

  function cycleTab(delta: number) {
    if (!tabs.length) return;
    const i = tabs.findIndex((t) => t.id === activeId);
    activeId = tabs[(i + delta + tabs.length) % tabs.length].id;
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
    searchTimer = setTimeout(() => active?.search(q), 250);
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

  // Each tab keeps its own query; show it when switching tabs.
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
    if (mode === "none") viewer?.setZoom(1);
    else viewer?.setFit(mode);
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
    else if (mod && key === "w") activeId !== null && closeTab(activeId);
    else if (mod && key === "tab") cycleTab(e.shiftKey ? -1 : 1);
    else if (mod && key === "f" && active) searchInput?.focus();
    else if (mod && key === "g" && active) startGoto();
    else if (mod && (key === "=" || key === "+") && active) viewer?.zoomBy(1.2);
    else if (mod && key === "-" && active) viewer?.zoomBy(1 / 1.2);
    else if (mod && key === "0" && active) viewer?.setZoom(1);
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

  // Remember open tabs, the active one and the sidebar across launches.
  $effect(() => {
    if (!restored) return;
    const session = {
      paths: tabs.map((t) => t.doc.path),
      active: tabs.findIndex((t) => t.id === activeId),
    };
    const sidebar = { open: sidebarOpen, mode: sidebarMode };
    api().then((py) => {
      py.set_setting("session", session);
      py.set_setting("sidebar", sidebar);
    });
  });

  onMount(async () => {
    const py = await api();
    const appInfo = await py.app_info();
    setRenderBaseUrl(appInfo.renderBaseUrl);
    invert = await py.get_setting("invertPages", false);
    const sidebar = await py.get_setting("sidebar", { open: false, mode: "pages" as const });
    sidebarOpen = sidebar.open;
    sidebarMode = sidebar.mode;

    const session = await py.get_setting("session", { paths: [] as string[], active: -1 });
    for (const path of session.paths) await openPath(path, false);
    activeId = tabs[session.active]?.id ?? tabs[0]?.id ?? null;
    error = null; // files that moved away since last time are just skipped
    await refreshRecents();
    info = appInfo;
    restored = true;
  });
</script>

<svelte:window onkeydown={onKeydown} />

<div class="window">
  {#if active && sidebarOpen}
    <div class="sidebar" style="width:{SIDEBAR_WIDTH}px">
      <Sidebar tab={active} mode={sidebarMode} {invert} onmode={setSidebarMode} />
    </div>
  {/if}

  <div class="main" style="left:{active && sidebarOpen ? SIDEBAR_WIDTH : 0}px">
    <header bind:clientHeight={headerHeight}>
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
              <button title="Zoom out (Ctrl+-)" onclick={() => viewer?.zoomBy(1 / 1.2)}>
                <Icon name="minus" size={14} />
              </button>
              <button class="zoom-label" onclick={() => (zoomMenu = !zoomMenu)} title="Zoom options">
                {Math.round(active.zoom * 100)}%
              </button>
              <button title="Zoom in (Ctrl++)" onclick={() => viewer?.zoomBy(1.2)}>
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
          <button class="tool" title="Open PDF (Ctrl+O)" onclick={pickAndOpen} disabled={!info}>
            <Icon name="open" />
          </button>
        </div>
      </div>

      {#if tabs.length}
        <TabBar {tabs} {activeId} onselect={selectTab} onclose={closeTab} onnew={newTab} />
      {/if}
    </header>

    {#if active}
      {#key active.id}
        <Viewer bind:this={viewer} tab={active} topInset={headerHeight} {invert} onlink={onLink} />
      {/key}
    {:else}
      <div class="home" style="padding-top:{headerHeight + 24}px">
        {#if info}
          <Welcome version={info.version} {recents} onopen={pickAndOpen} onopenpath={openPath} />
        {:else}
          <p class="hint">Starting…</p>
        {/if}
      </div>
    {/if}

    {#if error}
      <div class="toast" role="alert">
        {error}
        <button onclick={() => (error = null)} aria-label="Dismiss"><Icon name="close" size={12} /></button>
      </div>
    {/if}
  </div>

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

  .sidebar {
    position: absolute;
    inset: 0 auto 0 0;
  }

  .main {
    position: absolute;
    inset: 0 0 0 0;
  }

  /* Translucent unified toolbar (+ tabs); content scrolls underneath it. */
  header {
    position: absolute;
    inset: 0 0 auto 0;
    z-index: 10;
    background: var(--toolbar);
    backdrop-filter: saturate(180%) blur(20px);
    border-bottom: 0.5px solid var(--separator);
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

  .home {
    position: absolute;
    inset: 0;
    overflow: auto;
    padding: 0 24px 32px;
  }

  .hint {
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
