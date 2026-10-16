<script lang="ts">
  // Equation → LaTeX, step 1: like a screenshot tool — the page dims and a rectangle is dragged
  // over the equation. The rectangle is turned into PDF coordinates of the page under it.
  import type { Rect } from "../api";
  import type { Tab } from "../tab.svelte";

  interface Props {
    tab: Tab;
    topInset: number;
    onpick: (page: number, rect: Rect, at: { x: number; y: number }) => void;
  }

  let { tab, topInset, onpick }: Props = $props();

  let layer: HTMLDivElement;
  let start = $state<{ x: number; y: number } | null>(null);
  let end = $state<{ x: number; y: number } | null>(null);

  const box = $derived.by(() => {
    if (!start || !end) return null;
    return {
      left: Math.min(start.x, end.x),
      top: Math.min(start.y, end.y),
      width: Math.abs(end.x - start.x),
      height: Math.abs(end.y - start.y),
    };
  });

  function local(e: PointerEvent) {
    const r = layer.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  }

  function down(e: PointerEvent) {
    if (e.button !== 0) return;
    e.preventDefault();
    layer.setPointerCapture(e.pointerId);
    start = end = local(e);
  }

  function move(e: PointerEvent) {
    if (start) end = local(e);
  }

  function up(e: PointerEvent) {
    if (!start || !box) return;
    const r = layer.getBoundingClientRect();
    const b = { ...box };
    start = end = null;
    if (b.width < 6 || b.height < 6) return; // a click, not a rectangle
    // The page under the rectangle's centre (the layer sits above the pages).
    const cx = r.left + b.left + b.width / 2;
    const cy = r.top + b.top + b.height / 2;
    const pageEl = document.elementsFromPoint(cx, cy).find((el) => el.matches(".page")) as HTMLElement | undefined;
    if (!pageEl) return;
    const page = Number(pageEl.dataset.page);
    const p = pageEl.getBoundingClientRect();
    const scale = p.width / tab.doc.pageSizes[page][0];
    const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), hi);
    const x0 = clamp(r.left + b.left, p.left, p.right);
    const y0 = clamp(r.top + b.top, p.top, p.bottom);
    const x1 = clamp(r.left + b.left + b.width, p.left, p.right);
    const y1 = clamp(r.top + b.top + b.height, p.top, p.bottom);
    if (x1 - x0 < 4 || y1 - y0 < 4) return;
    const rect: Rect = [(x0 - p.left) / scale, (y0 - p.top) / scale, (x1 - p.left) / scale, (y1 - p.top) / scale];
    onpick(page, rect, { x: x0, y: y1 });
  }

  // Scrolling still works while choosing.
  function wheel(e: WheelEvent) {
    layer.parentElement?.querySelector(".scroller")?.scrollBy({ top: e.deltaY, left: e.deltaX });
  }

  function key(e: KeyboardEvent) {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      tab.snipping = false;
    }
  }
</script>

<svelte:window onkeydowncapture={key} />

<div
  class="snip"
  class:dim={!box}
  style="top:{topInset}px"
  bind:this={layer}
  role="application"
  aria-label="Draw a rectangle around an equation"
  onpointerdown={down}
  onpointermove={move}
  onpointerup={up}
  onwheel={wheel}
>
  {#if box}
    <div class="sel" style="left:{box.left}px;top:{box.top}px;width:{box.width}px;height:{box.height}px"></div>
  {/if}
  <div class="hint">
    Drag a rectangle around an equation · <b>Esc</b> to cancel
    <button onpointerdown={(e) => e.stopPropagation()} onclick={() => (tab.snipping = false)}>Cancel</button>
  </div>
</div>

<style>
  .snip {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 7;
    cursor: crosshair;
    overflow: hidden;
  }

  .snip.dim {
    background: rgb(0 0 0 / 0.28);
  }

  .sel {
    position: absolute;
    border: 1.5px solid var(--accent);
    border-radius: 2px;
    /* Everything outside the rectangle is dimmed. */
    box-shadow: 0 0 0 9999px rgb(0 0 0 / 0.28);
  }

  .hint {
    position: absolute;
    top: 12px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 6px 6px 12px;
    border-radius: 13px;
    background: var(--popover-solid);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 6px 20px rgb(0 0 0 / 0.2);
    font-size: 12.5px;
    white-space: nowrap;
    cursor: default;
  }

  .hint button {
    padding: 2px 10px;
    border-radius: 8px;
    background: var(--hover);
  }
</style>
