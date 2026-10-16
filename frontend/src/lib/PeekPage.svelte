<script lang="ts">
  // One page inside the link preview: zoomable (buttons / Ctrl+wheel), dragged to pan, or — in
  // select mode — with selectable text (Ctrl+C to copy).
  import { onMount } from "svelte";
  import type { Rect } from "./api";
  import type { Tab } from "./tab.svelte";
  import PageView from "./viewer/PageView.svelte";
  import { mergeLines } from "./viewer/rects";
  import type { ContextTarget, TextSelection } from "./viewer/Viewer.svelte";

  interface Props {
    tab: Tab;
    page: number;
    startY: number; // PDF points to scroll to initially
    invert: boolean;
    selectMode: boolean;
    zoom?: number; // 1 = page fits the width
    /** Right-click: on selected text (`sel`) or on a spot of the page. */
    oncontext?: (target: { sel: TextSelection } | ContextTarget, event: MouseEvent) => void;
  }

  let { tab, page, startY, invert, selectMode, zoom = $bindable(1), oncontext }: Props = $props();

  function onContextMenu(e: MouseEvent) {
    e.preventDefault();
    const el = box.querySelector<HTMLElement>(".page");
    if (!el || !oncontext) return;
    const r = el.getBoundingClientRect();
    const sel = getSelection();
    const range = sel && !sel.isCollapsed && sel.rangeCount && box.contains(sel.anchorNode) ? sel.getRangeAt(0) : null;
    if (range) {
      const rects: Rect[] = [];
      for (const c of range.getClientRects()) {
        if (c.width < 1 || c.height < 1) continue;
        rects.push([(c.left - r.left) / cssScale, (c.top - r.top) / cssScale, (c.right - r.left) / cssScale, (c.bottom - r.top) / cssScale]);
      }
      if (rects.length) {
        const box = new DOMRect(e.clientX - 1, e.clientY - 1, 2, 2);
        return oncontext({ sel: { text: sel!.toString(), byPage: new Map([[page, mergeLines(rects)]]), box } }, e);
      }
    }
    oncontext({ kind: "page", page, x: (e.clientX - r.left) / cssScale, y: (e.clientY - r.top) / cssScale }, e);
  }


  const MIN = 0.5;
  const MAX = 5;
  let box: HTMLDivElement;
  let width = $state(0);

  const size = $derived(tab.doc.pageSizes[page]);
  const cssScale = $derived(((width || 400) / size[0]) * zoom);
  const renderScale = $derived(Math.min(Math.ceil(cssScale * devicePixelRatio * 4) / 4, 6));

  export function zoomBy(factor: number, anchor?: { x: number; y: number }) {
    const next = Math.min(Math.max(zoom * factor, MIN), MAX);
    if (next === zoom) return;
    const ax = anchor?.x ?? box.clientWidth / 2;
    const ay = anchor?.y ?? box.clientHeight / 2;
    // Keep the point under the cursor (or the centre) in place.
    const px = (box.scrollLeft + ax) / cssScale;
    const py = (box.scrollTop + ay) / cssScale;
    zoom = next;
    requestAnimationFrame(() => {
      box.scrollLeft = px * cssScale - ax;
      box.scrollTop = py * cssScale - ay;
    });
  }

  function onWheel(e: WheelEvent) {
    if (!e.ctrlKey) return;
    e.preventDefault();
    const r = box.getBoundingClientRect();
    zoomBy(e.deltaY < 0 ? 1.15 : 1 / 1.15, { x: e.clientX - r.left, y: e.clientY - r.top });
  }

  // Pan by dragging (when not selecting text).
  function onPointerDown(e: PointerEvent) {
    if (selectMode || e.button !== 0) return;
    e.preventDefault();
    const start = { x: e.clientX, y: e.clientY, left: box.scrollLeft, top: box.scrollTop };
    const move = (ev: PointerEvent) => {
      box.scrollLeft = start.left - (ev.clientX - start.x);
      box.scrollTop = start.top - (ev.clientY - start.y);
    };
    const up = () => {
      removeEventListener("pointermove", move);
      removeEventListener("pointerup", up);
    };
    addEventListener("pointermove", move);
    addEventListener("pointerup", up);
  }

  onMount(() => {
    width = box.clientWidth;
    box.addEventListener("wheel", onWheel, { passive: false });
    requestAnimationFrame(() => (box.scrollTop = Math.max(startY * cssScale - 16, 0)));
    return () => box.removeEventListener("wheel", onWheel);
  });
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="peek-page" class:pan={!selectMode} bind:this={box} onpointerdown={onPointerDown} oncontextmenu={onContextMenu}>
  <div class="canvas" style="width:{size[0] * cssScale}px;height:{size[1] * cssScale}px">
    <PageView
      {tab}
      index={page}
      left={0}
      top={0}
      {cssScale}
      {renderScale}
      live={true}
      {invert}
      hits={[]}
      activeHit={-1}
      stroke={null}
      onlink={() => {}}
    />
  </div>
</div>

<style>
  .peek-page {
    position: relative;
    overflow: auto;
    background: var(--canvas);
  }

  .canvas {
    position: relative;
  }

  .pan {
    cursor: grab;
  }

  .pan:active {
    cursor: grabbing;
  }

  /* Pan mode: the text layer and link hotspots don't take the pointer. */
  .pan :global(.text),
  .pan :global(.link) {
    pointer-events: none;
  }
</style>
