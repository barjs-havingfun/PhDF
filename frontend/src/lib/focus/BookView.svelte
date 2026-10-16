<script lang="ts">
  // Book view (Read → Read like a book): one spread of two pages filling the window, no
  // scrolling. Turn pages with the buttons at the bottom corners, ← / → / Space; a short slide
  // animation. Esc closes it and the normal view continues where you stopped.
  import { untrack } from "svelte";
  import { fly } from "svelte/transition";
  import Icon from "../Icon.svelte";
  import { read, rowStart } from "../reading.svelte";
  import type { Tab } from "../tab.svelte";
  import PageView from "../viewer/PageView.svelte";

  // `top`: the book view starts below the toolbar, so the main panel stays visible.
  let { tab, invert, top = 0, onclose }: { tab: Tab; invert: boolean; top?: number; onclose: () => void } = $props();

  // Two pages side by side; the cover alone if the Read menu says so.
  const layout = $derived(read.pages === "cover" ? "cover" : "spread");
  // Opens at the spread of the page being read.
  let start = $state(untrack(() => rowStart(tab.page, read.pages === "cover" ? "cover" : "spread")));
  let dir = $state(1); // 1: forward (pages leave to the left)

  const count = $derived(tab.pageCount);
  const pages = $derived(layout === "cover" && start === 0 ? [0] : [start, start + 1].filter((p) => p < count));

  let width = $state(0);
  let height = $state(0);
  const PAD = 28;
  const GAP = 6;
  const BAR = 64; // room for the buttons at the bottom
  const PT = 96 / 72;
  const scale = $derived.by(() => {
    const sizes = pages.map((p) => tab.doc.pageSizes[p]);
    const w = sizes.reduce((s, [pw]) => s + pw, 0) * PT;
    const h = Math.max(...sizes.map(([, ph]) => ph)) * PT;
    return Math.max(0.1, Math.min((width - PAD * 2 - GAP) / w, (height - PAD - BAR) / h)) * PT;
  });
  const renderScale = $derived(Math.min(Math.ceil(scale * devicePixelRatio * 4) / 4, 6));
  const spreadW = $derived(pages.reduce((s, p) => s + tab.doc.pageSizes[p][0] * scale, 0) + GAP * (pages.length - 1));

  function next() {
    const n = layout === "cover" && start === 0 ? 1 : start + 2;
    if (n < count) (dir = 1), (start = n);
  }

  function prev() {
    if (start === 0) return;
    dir = -1;
    start = layout === "cover" && start <= 1 ? 0 : Math.max(0, start - 2);
  }

  // The normal view follows the turned pages (no history entries), so closing from anywhere,
  // e.g. the Read menu, continues at the same page.
  $effect(() => {
    const page = start;
    untrack(() => (tab.pendingJump = { page }));
  });

  function close() {
    onclose();
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === "ArrowRight" || e.key === " " || e.key === "PageDown") next();
    else if (e.key === "ArrowLeft" || e.key === "PageUp") prev();
    else if (e.key === "Escape") close();
    else return;
    e.preventDefault();
    e.stopPropagation(); // the viewer behind must not move too
  }
</script>

<svelte:window onkeydowncapture={onKey} />

<div class="book" style="top:{top}px" bind:clientWidth={width} bind:clientHeight={height} role="dialog" aria-label="Book view">
  <button class="close" onclick={close} title="Back to the normal view (Esc)"><Icon name="close" size={14} /> Close</button>

  <div class="stage">
    {#key start}
      <div
        class="spread"
        style="width:{spreadW}px"
        in:fly={{ x: 70 * dir, duration: 260, opacity: 0 }}
        out:fly={{ x: -70 * dir, duration: 200, opacity: 0 }}
      >
        {#each pages as p, k}
          {@const [pw, ph] = tab.doc.pageSizes[p]}
          <div class="page" class:left={pages.length === 2 && k === 0} class:right={pages.length === 2 && k === 1} style="width:{pw * scale}px;height:{ph * scale}px">
            <PageView
              {tab}
              index={p}
              left={0}
              top={0}
              cssScale={scale}
              {renderScale}
              live={true}
              {invert}
              hits={[]}
              activeHit={-1}
              stroke={null}
              onlink={() => {}}
            />
          </div>
        {/each}
      </div>
    {/key}
  </div>

  <div class="bar">
    <button class="turn" onclick={prev} disabled={start === 0} aria-label="Previous pages"><Icon name="left" size={20} /></button>
    <span class="where">{pages.map((p) => p + 1).join("–")} / {count}</span>
    <button class="turn" onclick={next} disabled={pages[pages.length - 1] >= count - 1} aria-label="Next pages"><Icon name="right" size={20} /></button>
  </div>
</div>

<style>
  .book {
    position: fixed;
    inset: 0;
    z-index: 10; /* above pages and tabs, below the toolbar (11) and its menus */
    background: var(--canvas);
    overflow: hidden;
  }

  .stage {
    position: absolute;
    inset: 28px 0 64px;
    display: grid;
    place-items: center;
  }

  /* While turning, the old and the new spread overlap in the same cell. */
  .spread {
    grid-area: 1 / 1;
    display: flex;
    gap: 6px;
  }

  .page {
    position: relative;
    box-shadow: var(--page-shadow);
  }

  /* A soft fold in the middle of the spread. */
  .page.left::after,
  .page.right::after {
    content: "";
    position: absolute;
    top: 0;
    bottom: 0;
    width: 28px;
    pointer-events: none;
  }

  .page.left::after {
    right: 0;
    background: linear-gradient(to left, rgb(0 0 0 / 0.1), transparent);
  }

  .page.right::after {
    left: 0;
    background: linear-gradient(to right, rgb(0 0 0 / 0.1), transparent);
  }

  .bar {
    position: absolute;
    left: 16px;
    right: 16px;
    bottom: 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .turn {
    display: grid;
    place-items: center;
    width: 44px;
    height: 44px;
    border-radius: 50%;
    background: var(--popover);
    backdrop-filter: blur(16px);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 4px 14px rgb(0 0 0 / 0.15);
    color: var(--text);
    transition: transform 0.12s;
  }

  .turn:hover:not(:disabled) {
    transform: scale(1.08);
  }

  .turn:disabled {
    opacity: 0.3;
  }

  .where {
    font-size: 12px;
    font-variant-numeric: tabular-nums;
    color: var(--secondary);
  }

  .close {
    position: absolute;
    top: 12px;
    right: 14px;
    z-index: 2;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border-radius: 9px;
    font-weight: 600;
    color: var(--text);
    background: var(--popover);
    backdrop-filter: blur(16px);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 4px 14px rgb(0 0 0 / 0.15);
  }

  .close:hover {
    background: var(--accent);
    color: var(--accent-text);
  }
</style>
