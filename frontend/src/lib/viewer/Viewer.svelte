<script lang="ts">
  // Continuous, virtualized page view. Only pages near the viewport load images/text/links.
  // Owns scrolling, zoom/fit and position tracking for one tab.
  import { onMount, tick } from "svelte";
  import { api, type FitMode, type PdfLink } from "../api";
  import type { Jump, Tab } from "../tab.svelte";
  import PageView from "./PageView.svelte";

  interface Props {
    tab: Tab;
    topInset: number; // height of the translucent header overlapping the top
    invert: boolean;
    onlink: (link: PdfLink, event: MouseEvent) => void;
  }

  let { tab, topInset, invert, onlink }: Props = $props();

  const PT_TO_PX = 96 / 72;
  const GAP = 14;
  const PAD_X = 24;
  const PAD_BOTTOM = 48;
  const MIN_ZOOM = 0.1;
  const MAX_ZOOM = 8;
  const MAX_RENDER_SCALE = 6;

  let scroller: HTMLDivElement;
  let viewWidth = $state(0);
  let viewHeight = $state(0);
  let scrollTop = $state(0);
  let ready = $state(false);

  const cssScale = $derived(tab.zoom * PT_TO_PX);
  const sizes = $derived(tab.doc.pageSizes);
  const maxW = $derived(Math.max(...sizes.map((s) => s[0])));
  const maxH = $derived(Math.max(...sizes.map((s) => s[1])));

  // Page tops in CSS px, relative to the scroll content.
  const tops = $derived.by(() => {
    const out: number[] = [];
    let y = topInset + 20;
    for (const [, h] of sizes) {
      out.push(y);
      y += h * cssScale + GAP;
    }
    return out;
  });
  const contentHeight = $derived(
    tops.length ? tops[tops.length - 1] + sizes[sizes.length - 1][1] * cssScale + PAD_BOTTOM : 0,
  );
  const contentWidth = $derived(Math.max(viewWidth, maxW * cssScale + PAD_X * 2));

  // Re-render sharper images only once zooming settles; CSS scales the old ones meanwhile.
  let renderScale = $state(1);
  $effect(() => {
    const target = Math.min(Math.ceil(cssScale * devicePixelRatio * 4) / 4, MAX_RENDER_SCALE);
    const t = setTimeout(() => (renderScale = target), renderScale === 1 ? 0 : 180);
    return () => clearTimeout(t);
  });

  // Pages within one viewport above and two below are "live".
  const liveRange = $derived.by(() => {
    const lo = scrollTop - viewHeight;
    const hi = scrollTop + viewHeight * 2;
    return [pageAt(lo), pageAt(hi)] as const;
  });

  const hitsByPage = $derived.by(() => {
    const map = new Map<number, { rects: [number, number, number, number][]; active: number }>();
    tab.searchHits.forEach((h, i) => {
      let entry = map.get(h.page);
      if (!entry) map.set(h.page, (entry = { rects: [], active: -1 }));
      if (i === tab.searchIndex) entry.active = entry.rects.length;
      entry.rects.push(h.rect);
    });
    return map;
  });

  /** Index of the page at content offset y (binary search over tops). */
  function pageAt(y: number): number {
    let lo = 0;
    let hi = tops.length - 1;
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1;
      if (tops[mid] <= y) lo = mid;
      else hi = mid - 1;
    }
    return lo;
  }

  function currentLocation() {
    const y = scroller.scrollTop + topInset + 1;
    const page = pageAt(y);
    const h = sizes[page][1] * cssScale;
    return { page, scroll: Math.min(Math.max((y - tops[page]) / h, 0), 1) };
  }

  function scrollToJump(j: Jump, behavior: ScrollBehavior = "instant") {
    const page = Math.max(0, Math.min(tab.pageCount - 1, j.page));
    const h = sizes[page][1];
    const frac = j.y != null ? j.y / h : (j.scroll ?? 0);
    const y = tops[page] + frac * h * cssScale - topInset - (j.y != null ? 8 : 0);
    scroller.scrollTo({ top: Math.max(y, 0), behavior });
  }

  function fitZoom(mode: FitMode): number {
    const byWidth = (viewWidth - PAD_X * 2) / (maxW * PT_TO_PX);
    if (mode === "width") return byWidth;
    const byHeight = (viewHeight - topInset - 2 * GAP) / (maxH * PT_TO_PX);
    return Math.min(byWidth, byHeight);
  }

  /** Change zoom while keeping the same spot of the document at the top of the view. */
  async function applyZoom(zoom: number, fit: FitMode) {
    const loc = currentLocation();
    tab.zoom = Math.min(Math.max(zoom, MIN_ZOOM), MAX_ZOOM);
    tab.fit = fit;
    await tick();
    scrollToJump(loc);
    savePosition();
  }

  export function setZoom(zoom: number) {
    applyZoom(zoom, "none");
  }

  export function zoomBy(factor: number) {
    applyZoom(tab.zoom * factor, "none");
  }

  export function setFit(mode: FitMode) {
    applyZoom(mode === "none" ? 1 : fitZoom(mode), mode);
  }

  // --- position tracking & persistence ------------------------------------------------------

  let saveTimer: ReturnType<typeof setTimeout> | undefined;
  function savePosition() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(async () => {
      (await api()).save_position(tab.doc.docId, tab.page, tab.scroll, tab.zoom, tab.fit);
    }, 400);
  }

  let frame = 0;
  function onScroll() {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => {
      scrollTop = scroller.scrollTop;
      if (!ready) return;
      const loc = currentLocation();
      tab.page = loc.page;
      tab.scroll = loc.scroll;
      savePosition();
    });
  }

  function onWheel(e: WheelEvent) {
    if (!e.ctrlKey) return;
    e.preventDefault();
    zoomBy(e.deltaY < 0 ? 1.1 : 1 / 1.1);
  }

  // Perform jumps requested through the tab (links, outline, search, history, restore).
  $effect(() => {
    const jump = tab.pendingJump;
    if (!jump || !ready) return;
    tab.pendingJump = null;
    scrollToJump(jump);
  });

  onMount(() => {
    scroller.addEventListener("wheel", onWheel, { passive: false });
    const observer = new ResizeObserver(() => {
      viewWidth = scroller.clientWidth;
      viewHeight = scroller.clientHeight;
      if (ready && tab.fit !== "none") applyZoom(fitZoom(tab.fit), tab.fit);
    });
    observer.observe(scroller);
    viewWidth = scroller.clientWidth;
    viewHeight = scroller.clientHeight;
    if (tab.fit !== "none") tab.zoom = fitZoom(tab.fit);

    tick().then(() => {
      scrollToJump(tab.pendingJump ?? { page: tab.page, scroll: tab.scroll });
      tab.pendingJump = null;
      scrollTop = scroller.scrollTop;
      ready = true;
    });

    return () => {
      observer.disconnect();
      scroller.removeEventListener("wheel", onWheel);
      clearTimeout(saveTimer);
      cancelAnimationFrame(frame);
    };
  });
</script>

<div class="scroller" bind:this={scroller} onscroll={onScroll}>
  <div class="content" style="height:{contentHeight}px;width:{contentWidth}px">
    {#each sizes as size, i (i)}
      {@const hits = hitsByPage.get(i)}
      <PageView
        {tab}
        index={i}
        left={(contentWidth - size[0] * cssScale) / 2}
        top={tops[i]}
        {cssScale}
        {renderScale}
        live={ready && i >= liveRange[0] && i <= liveRange[1]}
        {invert}
        hits={hits?.rects ?? []}
        activeHit={hits?.active ?? -1}
        {onlink}
      />
    {/each}
  </div>
</div>

<style>
  .scroller {
    position: absolute;
    inset: 0;
    overflow: auto;
    background: var(--canvas);
  }

  .content {
    position: relative;
  }
</style>
