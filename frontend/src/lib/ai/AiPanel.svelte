<script lang="ts">
  // The terminal panel. Its header: click to collapse/expand like a drawer, drag to dock it at the
  // side or the bottom, buttons to move / restart / close.
  import { kbd } from "../platform";
  import { onMount } from "svelte";
  import { capture } from "../dnd.svelte";
  import Icon from "../Icon.svelte";
  import { attach, closeTerminal, refit, restart, runningAi, saveLayout, term, type Dock } from "./terminal.svelte";

  let { topInset = 0 }: { topInset?: number } = $props();

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
    <span class="title">Terminal</span>
    {#if term.ai}<span class="ai-chip">{term.ai}</span>{/if}
    <span class="grow"></span>
    <button class="howto" title="How to install and use Claude Code or Codex" onclick={() => (term.guideOpen = true)}>
      <Icon name="help" size={13} /> How to
    </button>
    {#if term.dock === "side"}
      <button class="btn" title="Dock at the bottom" onclick={() => moveTo("bottom")}><Icon name="dockBottom" size={14} /></button>
    {:else}
      <button class="btn" title="Dock at the side" onclick={() => moveTo("side")}><Icon name="dockSide" size={14} /></button>
    {/if}
    <button class="btn" title="Restart the shell" onclick={() => restart()}><Icon name="restart" size={14} /></button>
    <button class="btn" title={kbd("Hide terminal (Ctrl+`)")} onclick={closeTerminal}><Icon name="close" size={13} /></button>
  </header>
  <div class="body" bind:this={body}></div>
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

  .title {
    font-size: 12px;
    font-weight: 600;
    color: var(--text);
  }

  .ai-chip {
    padding: 0 6px;
    border-radius: 8px;
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
    border-radius: 5px;
    color: var(--secondary);
    cursor: default;
  }

  .howto {
    display: flex;
    align-items: center;
    gap: 4px;
    height: 22px;
    padding: 0 8px;
    border-radius: 5px;
    font-size: 11px;
    color: var(--accent);
    cursor: default;
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

  .body :global(.xterm) {
    height: 100%;
  }

  .body :global(.xterm-viewport) {
    background: transparent !important;
  }
</style>
