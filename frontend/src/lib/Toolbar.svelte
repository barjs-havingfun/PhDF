<script lang="ts">
  // The window toolbar: sidebar / back / forward, Read / Focus / Park, title and page, annotation
  // tools, zoom, dark pages, search, AI, terminal, grading, help, the ⋯ menu and Open. Narrow
  // windows fold groups into ⋯ (container queries). The actions themselves live in App.
  import { kbd } from "./platform";
  import type { FitMode } from "./api";
  import Icon from "./Icon.svelte";
  import { ui } from "./notify.svelte";
  import DocAiMenu from "./ai/DocAiMenu.svelte";
  import { term } from "./ai/terminal.svelte";
  import FocusMenu from "./focus/FocusMenu.svelte";
  import ReadMenu from "./focus/ReadMenu.svelte";
  import { grading } from "./grading/grading.svelte";
  import { clock, pomodoro, read } from "./reading.svelte";
  import type { MdTab, Tab } from "./tab.svelte";
  import type Viewer from "./viewer/Viewer.svelte";

  interface Props {
    active: Tab | null; // focused PDF tab
    note: MdTab | null; // focused Markdown tab
    ready: boolean; // the backend answered (app info loaded)
    invert: boolean;
    parking: boolean;
    paneId: number;
    viewer: () => Viewer | undefined;
    ontogglesidebar: () => void;
    onzen: () => void;
    onfullscreen: () => void;
    onpark: () => void;
    onsetfit: (mode: FitMode) => void;
    oninvert: () => void;
    onsnip: () => void;
    onterminal: () => void;
    ongrading: () => void;
    onstopgrading: () => void;
    onexporthighlights: () => void;
    onexportmarkdown: (target: "file" | "vault") => void;
    oncopynote: () => void;
    onrecognize: () => void;
    onopen: () => void;
  }

  let {
    active, note, ready, invert, parking, paneId, viewer,
    ontogglesidebar, onzen, onfullscreen, onpark, onsetfit, oninvert, onsnip, onterminal, ongrading,
    onstopgrading, onexporthighlights, onexportmarkdown, oncopynote, onrecognize, onopen,
  }: Props = $props(); // prettier-ignore

  let zoomMenu = $state(false);
  let moreMenu = $state(false);
  let readMenu = $state(false);
  let focusMenu = $state(false);
  let aiMenu = $state(false);
  let aiTools = $state(false);

  // A press anywhere else closes the open menu (each menu's wrapper has a data-menu name). The
  // menus' own backdrops can't do it: in this toolbar, position:fixed only covers the toolbar.
  $effect(() => {
    if (!(zoomMenu || moreMenu || readMenu || focusMenu || aiMenu || aiTools)) return;
    const down = (e: PointerEvent) => {
      const inside = (e.target as Element).closest?.("[data-menu]")?.getAttribute("data-menu");
      if (inside !== "read") readMenu = false;
      if (inside !== "focus") focusMenu = false;
      if (inside !== "zoom") zoomMenu = false;
      if (inside !== "more") moreMenu = false;
      if (inside !== "ai") aiMenu = aiTools = false;
    };
    document.addEventListener("pointerdown", down, true);
    return () => document.removeEventListener("pointerdown", down, true);
  });

  /** A ⋯ menu item: close the menu, then act. */
  const more = (run: () => void) => () => {
    moreMenu = false;
    run();
  };

  /** A zoom typed in the zoom menu (10-800 %). */
  function setPercent(value: string) {
    const n = Number(value);
    if (Number.isFinite(n) && n > 0) viewer()?.setZoom(Math.min(800, Math.max(10, n)) / 100);
  }

  function setFit(mode: FitMode) {
    zoomMenu = false;
    onsetfit(mode);
  }

  export function openAiMenu() {
    aiMenu = true;
  }

  // --- search & go to page --------------------------------------------------------------------

  let searchInput = $state<HTMLInputElement>();
  let searchText = $state("");
  let gotoInput = $state<HTMLInputElement>();
  let editingPage = $state(false);

  export function focusSearch() {
    searchInput?.focus();
  }

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

  // Each tab keeps its own query; show it when the focused tab changes (or searches).
  $effect(() => {
    searchText = active?.searchQuery ?? "";
  });

  export async function startGoto() {
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
</script>

<div class="toolbar">
  <div class="group">
    <button class="tool" title={kbd("Sidebar (Ctrl+\\)")} onclick={ontogglesidebar} disabled={!active}>
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
    <div class="drop" data-menu="read">
      <button class="pill" class:on={readMenu || read.ruler || read.tint !== "none"} onclick={() => (readMenu = !readMenu)}>
        <Icon name="book" size={15} /> <span class="pill-label">Read</span> <Icon name="chevron" size={12} />
      </button>
      {#if readMenu}
        <ReadMenu onclose={() => (readMenu = false)} onzen={() => ((readMenu = false), onzen())} onfullscreen={() => ((readMenu = false), onfullscreen())} />
      {/if}
    </div>
    <div class="drop" data-menu="focus">
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
      title={kbd("Parking lot: park a stray thought (Ctrl+Shift+Space)")}
      onclick={onpark}
    >
      <Icon name="park" size={15} /> <span class="pill-label">Park</span>
    </button>
  </div>

  <div class="title">
    {#if active}
      <span class="name">
        {active.title}{#if active.dirty}<span class="edited">- Edited</span>{/if}
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

      <div class="segmented zoom" data-menu="zoom">
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
            <div class="zoom-fine">
              <input
                type="range"
                min="25"
                max="500"
                step="5"
                value={Math.round(active.zoom * 100)}
                oninput={(e) => viewer()?.setZoom(Number(e.currentTarget.value) / 100)}
                aria-label="Zoom"
              />
              <label class="pct">
                <input
                  type="number"
                  min="10"
                  max="800"
                  value={Math.round(active.zoom * 100)}
                  onkeydown={(e) => e.key === "Enter" && setPercent(e.currentTarget.value)}
                  onchange={(e) => setPercent(e.currentTarget.value)}
                  aria-label="Zoom in percent"
                />%
              </label>
              <div class="presets">
                {#each [50, 75, 100, 125, 150, 200] as p}
                  <button class:on={Math.round(active.zoom * 100) === p} onclick={() => viewer()?.setZoom(p / 100)}>{p}%</button>
                {/each}
              </div>
            </div>
            <div class="menu-sep"></div>
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

      <button class="tool dark" class:on={invert} title="Dark pages" onclick={oninvert}>
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
      <div class="drop ai-drop" data-menu="ai">
        <button class="tool" class:on={aiMenu} title="Ask the AI about this document, chapter or page" onclick={() => (aiMenu = !aiMenu)}>
          <Icon name="sparkle" />
        </button>
        <button class="tool caret" class:on={aiTools} title="More AI tools" onclick={() => (aiTools = !aiTools)}>
          <Icon name="chevron" size={12} />
        </button>
        {#if aiMenu}
          <DocAiMenu tab={active} {paneId} onclose={() => (aiMenu = false)} />
        {/if}
        {#if aiTools}
          <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
          <div class="menu-backdrop" onclick={() => (aiTools = false)}></div>
          <div class="menu right ai-tools" role="menu">
            <button role="menuitem" onclick={() => ((aiTools = false), onsnip())}>
              Equation → LaTeX (AI)
              <span class="sub">Draw a rectangle around an equation; the AI writes its LaTeX into your note.</span>
            </button>
          </div>
        {/if}
      </div>
    {/if}
    <button class="tool" class:on={term.open} title={kbd("AI terminal (Ctrl+`)")} onclick={onterminal} disabled={!ready}>
      <Icon name="terminal" />
    </button>

    <button
      class="tool grade"
      class:on={!!grading.session}
      title={grading.session ? `Grading “${grading.session.title}”: click to stop` : "Grade a folder of exam PDFs"}
      onclick={ongrading}
      disabled={!ready}
    >
      <Icon name="grade" />
    </button>
    <button class="tool help" title="How to use PhDF" onclick={() => (ui.helpOpen = true)}>
      <Icon name="help" />
    </button>
    <div class="more" data-menu="more">
      <button class="tool" class:on={moreMenu} title="More" onclick={() => (moreMenu = !moreMenu)} disabled={!ready}>
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
              <button role="menuitemcheckbox" aria-checked={invert} onclick={() => ((moreMenu = false), oninvert())}>Dark Pages</button>
              <div class="menu-sep"></div>
            </div>
            {#if grading.session}
              {@const g = grading.session}
              <button role="menuitem" onclick={() => ((moreMenu = false), g.exportCsv())}>Export Grades as CSV…</button>
              <button role="menuitem" onclick={() => ((moreMenu = false), onstopgrading())}>Stop Grading</button>
              <div class="menu-sep"></div>
            {/if}
            <button role="menuitem" onclick={more(() => (ui.tools = { path: pdf.path }))}>PDF Tools… (rotate, reorder, split…)</button>
            <div class="menu-sep"></div>
            <button role="menuitem" onclick={more(onexporthighlights)}>Export Highlights to Note</button>
            <button role="menuitem" onclick={more(() => onexportmarkdown("file"))}>Export as Markdown…</button>
            <button role="menuitem" onclick={more(() => onexportmarkdown("vault"))}>Export to Obsidian Vault</button>
            <button role="menuitem" onclick={more(oncopynote)}>Copy Note to Obsidian</button>
            <div class="menu-sep"></div>
            <button role="menuitem" onclick={more(onrecognize)} disabled={!!active.ocrProgress}>Recognize Text (OCR)</button>
            <div class="menu-sep"></div>
          {:else if note}
            <button role="menuitem" onclick={more(oncopynote)}>Copy Note to Obsidian</button>
            <div class="menu-sep"></div>
          {/if}
          <button role="menuitem" onclick={() => ((moreMenu = false), (ui.settingsOpen = true))}>Settings…</button>
        </div>
      {/if}
    </div>
    <button class="tool" title={kbd("Open PDF or Markdown (Ctrl+O)")} onclick={() => onopen()} disabled={!ready}>
      <Icon name="open" />
    </button>
  </div>
</div>

<style>
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

  /* Side groups take what they need; the title gets the rest and truncates, so nothing overlaps.
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

  .zoom-fine {
    display: grid;
    grid-template-columns: 1fr auto;
    align-items: center;
    gap: 6px 8px;
    width: 230px;
    padding: 6px 8px 4px;
  }

  .zoom-fine input[type="range"] {
    width: 100%;
    accent-color: var(--accent);
  }

  .pct {
    display: flex;
    align-items: center;
    gap: 2px;
    font-size: 12px;
    color: var(--secondary);
  }

  .pct input {
    width: 54px;
    height: 24px;
    padding: 0 4px;
    border: none;
    border-radius: 5px;
    background: var(--hover);
    color: var(--text);
    font: inherit;
    text-align: right;
  }

  .presets {
    grid-column: 1 / -1;
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  .menu .presets button {
    width: auto;
    padding: 2px 7px;
    border-radius: 5px;
    background: var(--hover);
    font-size: 11px;
  }

  .menu .presets button.on {
    background: var(--accent);
    color: var(--accent-text);
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
</style>
