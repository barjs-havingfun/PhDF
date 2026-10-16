<script lang="ts">
  // The terminal panel. Its header: terminal tabs (+ for another shell), click to collapse/expand
  // like a drawer, drag to dock it at the side or the bottom, buttons to move / restart / close.
  import { kbd } from "../platform";
  import { onMount } from "svelte";
  import { capture } from "../dnd.svelte";
  import Icon from "../Icon.svelte";
  import AgentPicker from "./AgentPicker.svelte";
  import { outsideClose } from "../outside";
  import {
    activateTab,
    agentLabel,
    attach,
    chooseAgent,
    closeTab,
    closeTerminal,
    dismissAgentAsk,
    newTab,
    refit,
    restart,
    runningAi,
    saveLayout,
    goToFolder,
    setFont,
    startInNewTab,
    answerResume,
    TERM_FONTS,
    TERM_SIZES,
    term,
    type Dock,
  } from "./terminal.svelte";
  import { api } from "../api";

  let { topInset = 0 }: { topInset?: number } = $props();

  let fontMenu = $state(false);
  let fontWrap = $state<HTMLElement>();
  $effect(() => {
    if (fontMenu) return outsideClose(() => fontWrap, () => (fontMenu = false));
  });

  // A tab opened with +: which installed agent to start in it (the default one first).
  let installed = $state<string[] | null>(null);
  $effect(() => {
    if (term.pickFor === null) return;
    api()
      .then((py) => py.ai_tools())
      .then((tools) => {
        const found = Object.keys(tools).filter((t) => tools[t as keyof typeof tools]);
        const own = term.agent && !(term.agent in tools) ? [term.agent] : []; // can't be checked
        installed = [...own, ...found].sort((a, b) => Number(b === term.agent) - Number(a === term.agent));
      });
  });

  let body: HTMLDivElement;

  // Adopt the terminal as soon as it exists (it may still be starting when the panel mounts).
  $effect(() => {
    if (term.ready) attach(body);
  });

  onMount(() => {
    const observer = new ResizeObserver(() => refit());
    observer.observe(body);
    // Show which AI runs (polled lightly while the panel is visible).
    const timer = setInterval(() => runningAi(), 4000);
    runningAi();
    return () => {
      observer.disconnect();
      clearInterval(timer);
    };
  });

  $effect(() => {
    if (!term.collapsed) refit();
  });

  function toggleCollapse() {
    term.collapsed = !term.collapsed;
    saveLayout();
  }

  function moveTo(dock: Dock) {
    term.dock = dock;
    term.collapsed = false;
    saveLayout();
  }

  // Drag the header to another dock; a plain click toggles the drawer.
  function onHeaderDown(e: PointerEvent) {
    if (e.button !== 0 || (e.target as HTMLElement).closest("button")) return;
    const el = e.currentTarget as HTMLElement;
    const start = { x: e.clientX, y: e.clientY };
    let dragging = false;
    capture(el, e.pointerId);
    const move = (ev: PointerEvent) => {
      if (!dragging && Math.hypot(ev.clientX - start.x, ev.clientY - start.y) < 6) return;
      dragging = true;
      term.dragging = true;
      const bottomZone = ev.clientY > innerHeight - Math.min(220, innerHeight * 0.3);
      const sideZone = ev.clientX > innerWidth * 0.55;
      term.dropTarget = bottomZone ? "bottom" : sideZone ? "side" : null;
    };
    const up = () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      if (!dragging) return toggleCollapse();
      if (term.dropTarget) moveTo(term.dropTarget);
      term.dragging = false;
      term.dropTarget = null;
    };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
  }
</script>

<section class="ai-panel" class:collapsed={term.collapsed} style="padding-top:{topInset}px">
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <header onpointerdown={onHeaderDown} title="Click to collapse / expand · drag to dock at the side or bottom">
    <span class="chev" class:closed={term.collapsed}><Icon name="chevron" size={12} /></span>
    <Icon name="terminal" size={14} />
    <div class="tabs" role="tablist">
      {#each term.tabs as t (t.id)}
        <span class="tab" class:on={t.id === term.active}>
          <button role="tab" aria-selected={t.id === term.active} title={t.ai ? `${t.name} · ${t.ai} running` : t.name} onclick={() => activateTab(t.id)}>
            {t.name}{#if t.ai}<span class="ai-chip">{t.ai}</span>{/if}
          </button>
          <button class="x" title="Close this terminal (stops its shell)" aria-label="Close {t.name}" onclick={() => closeTab(t.id)}>
            <Icon name="close" size={10} />
          </button>
        </span>
      {/each}
      <button class="btn add" title="New terminal" aria-label="New terminal" onclick={() => newTab()}><Icon name="plus" size={13} /></button>
    </div>
    <span class="grow"></span>
    {#if term.agent !== null}
      <button class="howto agent" title="Default AI agent, started in new terminals. Click to change." onclick={() => (term.agentAsk = true)}>
        <Icon name="sparkle" size={12} /> {agentLabel(term.agent)}
      </button>
    {/if}
    <button class="btn" title="Go to the PDF's folder" disabled={!term.docFolder} onclick={() => term.docFolder && goToFolder(term.docFolder)}>
      <Icon name="folder" size={14} />
    </button>
    <div class="font-wrap" bind:this={fontWrap} onpointerdown={(e) => e.stopPropagation()}>
      <button class="btn aa" class:on={fontMenu} title="Terminal font and size" onclick={() => (fontMenu = !fontMenu)}>Aa</button>
      {#if fontMenu}
        <div class="font-menu" role="menu">
          <div class="size">
            <button title="Smaller" disabled={term.font.size <= TERM_SIZES.min} onclick={() => setFont({ size: term.font.size - 1 })}>A−</button>
            <span>{term.font.size} px</span>
            <button title="Larger" disabled={term.font.size >= TERM_SIZES.max} onclick={() => setFont({ size: term.font.size + 1 })}>A+</button>
          </div>
          {#each TERM_FONTS as f}
            <button role="menuitemradio" aria-checked={term.font.name === f.name} style="font-family:{f.family}" onclick={() => setFont({ name: f.name })}>
              {f.name}
            </button>
          {/each}
        </div>
      {/if}
    </div>
    <button class="howto" title="How to install an AI agent (Claude Code, Codex, Gemini CLI or another)" onclick={() => (term.guideOpen = true)}>
      <Icon name="help" size={13} /> How to
    </button>
    {#if term.dock === "side"}
      <button class="btn" title={term.below ? "Put the terminal above the note" : "Put the terminal below the note"} onclick={() => ((term.below = !term.below), saveLayout())}>⇅</button>
      <button class="btn" title="Dock at the bottom" onclick={() => moveTo("bottom")}><Icon name="dockBottom" size={14} /></button>
    {:else}
      <button class="btn" title="Dock at the side" onclick={() => moveTo("side")}><Icon name="dockSide" size={14} /></button>
    {/if}
    <button class="btn" title="Restart the shell" onclick={() => restart()}><Icon name="restart" size={14} /></button>
    <button class="btn" title={kbd("Hide terminal (Ctrl+`)")} onclick={closeTerminal}><Icon name="close" size={13} /></button>
  </header>
  <div class="body" bind:this={body}>
    {#if term.pickFor !== null && term.pickFor === term.active && !term.agentAsk && !term.collapsed && installed}
      <div class="pick" role="group" aria-label="Start an agent in this terminal">
        {#if installed.length}
          <span>Start in this terminal:</span>
          {#each installed as command}
            <button class="choice" onclick={() => startInNewTab(command)}>{agentLabel(command)}</button>
          {/each}
        {:else}
          <span>No AI agent found on this computer.</span>
          <button class="link" onclick={() => (term.guideOpen = true)}>How to install one</button>
        {/if}
        <button class="link" onclick={() => startInNewTab("")}>Just the shell</button>
      </div>
    {/if}
    {#if term.resumeAsk && term.resumeAsk.id === term.active && !term.collapsed}
      {@const r = term.resumeAsk}
      <div class="pick" role="group" aria-label="Continue the last session?">
        <span>Start {r.name}:</span>
        <button class="choice" onclick={() => answerResume(true)} title="Continues your last session in this folder">
          Continue last session <code>{r.flag}</code>
        </button>
        <button class="choice plain" onclick={() => answerResume(false)}>New session</button>
        <button class="link" onclick={() => answerResume(null)}>Cancel</button>
      </div>
    {/if}
    {#if term.agentAsk && !term.collapsed}
      <div class="agent-card" role="dialog" aria-label="Choose an AI agent">
        <h3>{term.agent === null ? "Add an AI agent" : "Default AI agent"}</h3>
        <p>
          PhDF starts it in new terminals and whenever you <i>Ask AI</i>. Any AI that runs in a terminal works; you can
          change it later here or in Settings.
        </p>
        <AgentPicker current={term.agent} onpick={chooseAgent} />
        {#if term.agent !== null}<p class="next">This choice applies the next time a terminal opens; an agent that is already running keeps running.</p>{/if}
        <button class="not-now" onclick={dismissAgentAsk}>{term.agent === null ? "Not now" : "Cancel"}</button>
      </div>
    {/if}
  </div>
</section>

<style>
  .ai-panel {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    background: var(--surface);
  }

  header {
    flex: none;
    display: flex;
    align-items: center;
    gap: 6px;
    height: 30px;
    padding: 0 6px 0 8px;
    border-bottom: 0.5px solid var(--separator);
    background: var(--toolbar);
    color: var(--secondary);
    cursor: grab;
    user-select: none;
  }

  header:active {
    cursor: grabbing;
  }

  .chev {
    display: grid;
    transition: transform 0.15s;
  }

  .chev.closed {
    transform: rotate(-90deg);
  }

  .tabs {
    display: flex;
    align-items: center;
    gap: 2px;
    min-width: 0;
    overflow-x: auto;
    scrollbar-width: none;
  }

  .tab {
    flex: none;
    display: flex;
    align-items: center;
    height: 22px;
    border-radius: 6px;
    color: var(--secondary);
  }

  .tab > button:first-child {
    display: flex;
    align-items: center;
    gap: 5px;
    height: 100%;
    padding: 0 2px 0 8px;
    font-size: 12px;
    cursor: default;
  }

  .tab:hover {
    background: var(--hover);
  }

  .tab.on {
    background: var(--hover);
    color: var(--text);
    font-weight: 600;
  }

  .x {
    display: grid;
    place-items: center;
    width: 18px;
    height: 18px;
    margin-right: 2px;
    border-radius: 5px;
    opacity: 0;
    cursor: default;
  }

  .tab:hover .x,
  .tab.on .x {
    opacity: 0.7;
  }

  .x:hover {
    opacity: 1;
    background: var(--hover);
  }

  .ai-chip {
    padding: 0 6px;
    border-radius: 10px;
    font-size: 10px;
    font-weight: 600;
    background: var(--accent);
    color: var(--accent-text);
  }

  .grow {
    flex: 1;
  }

  .btn {
    display: grid;
    place-items: center;
    width: 24px;
    height: 22px;
    border-radius: 6px;
    color: var(--secondary);
    cursor: default;
  }

  .howto {
    display: flex;
    align-items: center;
    gap: 4px;
    height: 22px;
    padding: 0 8px;
    border-radius: 6px;
    font-size: 11px;
    color: var(--accent);
    cursor: default;
  }

  .btn:disabled {
    opacity: 0.35;
  }

  .btn.aa {
    font-size: 11px;
    font-weight: 600;
  }

  .btn.on {
    background: var(--hover);
    color: var(--text);
  }

  .font-wrap {
    position: relative;
  }

  .font-menu {
    position: absolute;
    top: calc(100% + 4px);
    right: 0;
    z-index: 41;
    min-width: 190px;
    padding: 5px;
    border-radius: 12px;
    background: var(--popover-solid);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 8px 28px rgb(0 0 0 / 0.22);
    cursor: default;
    color: var(--text);
  }

  .size {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 2px 4px 6px;
    margin-bottom: 4px;
    border-bottom: 0.5px solid var(--separator);
    font-size: 12px;
  }

  .size button {
    padding: 2px 10px;
    border-radius: 6px;
    background: var(--hover);
  }

  .size button:disabled {
    opacity: 0.4;
  }

  .font-menu button[role="menuitemradio"] {
    position: relative;
    display: block;
    width: 100%;
    padding: 3px 10px 3px 22px;
    border-radius: 6px;
    text-align: left;
    font-size: 12px;
  }

  .font-menu button[aria-checked="true"]::before {
    content: "✓";
    position: absolute;
    left: 7px;
  }

  .font-menu button[role="menuitemradio"]:hover {
    background: var(--accent);
    color: var(--accent-text);
  }

  .howto:hover {
    background: var(--hover);
  }

  .btn:hover {
    background: var(--hover);
    color: var(--text);
  }

  .body {
    position: relative;
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }

  .collapsed .body {
    display: none;
  }

  /* Asked in a tab opened with +; sits at the bottom, so the prompt above stays free to type. */
  .pick {
    position: absolute;
    bottom: 6px;
    left: 8px;
    right: 8px;
    z-index: 2;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    padding: 6px 8px;
    border-radius: 10px;
    background: var(--popover-solid);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 4px 14px rgb(0 0 0 / 0.15);
    font-size: 12px;
  }

  .pick .choice {
    padding: 2px 10px;
    border-radius: 8px;
    background: var(--accent);
    color: var(--accent-text);
    font-weight: 500;
  }

  .pick code {
    padding: 0 4px;
    border-radius: 5px;
    background: rgb(255 255 255 / 0.22);
    font-size: 11px;
  }

  .pick .choice.plain {
    background: var(--hover);
    color: var(--text);
  }

  .pick .link {
    margin-left: auto;
    color: var(--accent);
  }

  .pick .link:hover {
    text-decoration: underline;
  }

  .howto.agent {
    color: var(--secondary);
    max-width: 140px;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  /* Over the bottom of the terminal, so its prompt stays visible (the xterm hosts are added to
     .body by terminal.svelte.ts). */
  .agent-card {
    position: absolute;
    left: 8px;
    right: 8px;
    bottom: 8px;
    max-height: calc(100% - 16px);
    z-index: 2;
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-width: 440px;
    margin: 0 auto;
    padding: 12px 14px;
    overflow-y: auto;
    border-radius: 13px;
    background: var(--popover-solid);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 8px 24px rgb(0 0 0 / 0.18);
  }

  .agent-card h3 {
    margin: 0;
    font-size: 13px;
  }

  .agent-card p {
    margin: 0;
    font-size: 12px;
    color: var(--secondary);
  }

  .agent-card .next {
    margin: 0;
    font-size: 11px;
    color: var(--tertiary);
  }

  .not-now {
    align-self: flex-end;
    font-size: 12px;
    color: var(--secondary);
  }

  .not-now:hover {
    color: var(--text);
  }

  .body :global(.xterm) {
    height: 100%;
  }

  .body :global(.xterm-viewport) {
    background: transparent !important;
  }
</style>
