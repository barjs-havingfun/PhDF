<script lang="ts">
  // Book view (Read → Read like a book): one spread of two pages filling the window, no
  // scrolling. Turn pages with the buttons at the bottom corners, ← / → / Space; a short slide
  // animation. Esc closes it and the normal view continues where you stopped.
  import { onDestroy, tick, untrack } from "svelte";
  import { fly } from "svelte/transition";
  import Icon from "../Icon.svelte";
  import { api, pageImageUrl, type PdfLink } from "../api";
  import { ui } from "../notify.svelte";
  import { inTextField } from "../shortcuts";
  import { arrowStep, onScreen, read, rowStart } from "../reading.svelte";
  import type { Tab } from "../tab.svelte";
  import PageView from "../viewer/PageView.svelte";
  import PageControls from "./PageControls.svelte";
  import { preloaded } from "../viewer/preload";

  // `top`: the book view starts below the toolbar, so the main panel stays visible.
  let { tab, invert, top = 0, onclose }: { tab: Tab; invert: boolean; top?: number; onclose: () => void } = $props();

  // Two pages side by side; the cover alone if the Read menu says so.
  const layout = $derived(read.pages === "cover" ? "cover" : "spread");
  // Opens at the spread of the page being read.
  let start = $state(untrack(() => rowStart(tab.page, read.pages === "cover" ? "cover" : "spread")));
  let dir = $state(1); // 1: forward
  // Pages leave to the left going forward, or to the right when they run right to left.
  const slide = $derived(tab.rtl ? -dir : dir);

  const count = $derived(tab.pageCount);
  /** The pages of the spread starting at `s`, and where the next / previous spread starts. */
  const spreadAt = (s: number) => (layout === "cover" && s === 0 ? [0] : [s, s + 1].filter((p) => p < count));
  const nextStart = (s: number) => (layout === "cover" && s === 0 ? 1 : s + 2);
  const prevStart = (s: number) => (layout === "cover" && s <= 1 ? 0 : Math.max(0, s - 2));
  const pages = $derived(spreadAt(start));
  const shown = $derived(onScreen(pages, tab.rtl));

  let width = $state(0);
  let height = $state(0);
  const PAD = 28;
  const GAP = 6;
  const BAR = 64; // room for the buttons at the bottom
  const PT = 96 / 72;
  // The zoom slider (bottom right): 1 = the spread fits; bigger scrolls the stage.
  let zoom = $state(1);
  const MIN_ZOOM = 0.5;
  const MAX_ZOOM = 4;
  function scaleOf(spread: number[]) {
    const sizes = spread.map((p) => tab.doc.pageSizes[p]);
    const w = sizes.reduce((s, [pw]) => s + pw, 0) * PT;
    const h = Math.max(...sizes.map(([, ph]) => ph)) * PT;
    return Math.max(0.1, Math.min((width - PAD * 2 - GAP) / w, (height - PAD - BAR) / h)) * PT * zoom;
  }
  const renderScaleOf = (s: number) => Math.min(Math.ceil(s * devicePixelRatio * 4) / 4, 6);
  const scale = $derived(scaleOf(pages));
  // While zooming, sharper images only once it settles (as in the normal view; CSS scales the
  // old ones). Page turns and window sizes take effect at once.
  let renderScale = $state(untrack(() => renderScaleOf(scale)));
  let zooming = $state(false);
  let settledZoom = untrack(() => zoom);
  $effect(() => {
    const target = renderScaleOf(scale);
    if (!width || !height) return;
    if (zoom === settledZoom || target === untrack(() => renderScale)) {
      settledZoom = zoom;
      renderScale = target;
      zooming = false;
      return;
    }
    zooming = true;
    const t = setTimeout(() => {
      renderScale = target;
      zooming = false;
      settledZoom = zoom;
    }, 180);
    return () => clearTimeout(t);
  });

  // The next and the previous spread are loaded and decoded ahead (the server tells the web view
  // not to keep page images), so a page turn shows ready pictures instead of waiting for them.
  let ahead = new Map<string, HTMLImageElement>();
  $effect(() => {
    if (!width || !height || zooming) return;
    const urls = [nextStart(start), prevStart(start)]
      .filter((s) => s !== start && s < count)
      .flatMap((s) => {
        const spread = spreadAt(s);
        const r = renderScaleOf(scaleOf(spread));
        return spread.map((p) => pageImageUrl(tab.doc.docId, p, r, undefined, tab.revs[p] ?? 0));
      });
    const kept = new Map<string, HTMLImageElement>();
    for (const url of urls) {
      let img = untrack(() => ahead.get(url));
      if (!img) {
        img = new Image();
        img.src = url;
        img.decode().catch(() => {}); // cancelled or failed: the page loads it again itself
      }
      kept.set(url, img);
    }
    for (const url of ahead.keys()) if (!kept.has(url)) preloaded.delete(url);
    for (const [url, img] of kept) preloaded.set(url, img);
    ahead = kept; // the others can be dropped
  });
  onDestroy(() => {
    for (const url of ahead.keys()) preloaded.delete(url);
  });
  const spreadW = $derived(pages.reduce((s, p) => s + tab.doc.pageSizes[p][0] * scale, 0) + GAP * (pages.length - 1));

  // Hide the next page (Read menu): the page read second is blurred until clicked; "next" first
  // shows it, the next press turns. A page once seen stays clear.
  let seen = $state(new Set<number>());
  const hidden = (p: number) => read.spoiler && pages.length === 2 && p === pages[1] && !seen.has(p);
  function reveal(p: number) {
    if (!seen.has(p)) seen = new Set([...seen, p]);
  }

  function next() {
    const blurred = pages.find(hidden);
    if (blurred !== undefined) return reveal(blurred);
    const n = nextStart(start);
    if (n < count) {
      pages.forEach(reveal);
      (dir = 1), (start = n);
    }
  }

  const back = $derived({ label: "Previous pages", disabled: start === 0, go: prev });
  const forward = $derived({ label: "Next pages", disabled: pages[pages.length - 1] >= count - 1 && !pages.some(hidden), go: next });

  /** A link on a page: its spread (in book view), or the web page in the browser. */
  function followLink(link: PdfLink) {
    if (link.kind === "goto" && link.page >= 0 && link.page < count) {
      const target = rowStart(link.page, layout);
      if (target !== start) (dir = target > start ? 1 : -1), (start = target);
    } else if (link.kind === "uri" && link.uri) {
      api().then((py) => py.open_external(link.uri!));
    }
  }

  function prev() {
    if (start === 0) return;
    dir = -1;
    start = prevStart(start);
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

  // --- zoom (slider, Ctrl+wheel, Ctrl+= / Ctrl+- / Ctrl+0) and right-drag to move around ------

  let stage = $state<HTMLDivElement>();
  let book = $state<HTMLDivElement>();

  /** Zoom keeping the point under `at` (the pointer; else the middle) in place. */
  async function zoomTo(z: number, at?: { x: number; y: number }) {
    const target = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z));
    if (!stage || target === zoom) return;
    const ratio = target / zoom;
    const box = stage.getBoundingClientRect();
    const x = at ? at.x - box.left : box.width / 2;
    const y = at ? at.y - box.top : box.height / 2;
    const { scrollLeft, scrollTop } = stage;
    zoom = target;
    await tick();
    stage.scrollLeft = (scrollLeft + x) * ratio - x;
    stage.scrollTop = (scrollTop + y) * ratio - y;
  }

  $effect(() => {
    const el = book;
    if (!el) return;
    // Not passive: Ctrl+wheel must not zoom the whole web view.
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      // In proportion to the scroll: a touchpad pinch zooms smoothly, a wheel notch about 10%.
      zoomTo(zoom * Math.min(1.25, Math.max(0.8, Math.exp(-e.deltaY * 0.001))), { x: e.clientX, y: e.clientY });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  });

  let grab = $state<{ x: number; y: number } | null>(null);

  function onPointerDown(e: PointerEvent) {
    if (e.button !== 2 || !stage) return;
    grab = { x: e.clientX, y: e.clientY };
    stage.setPointerCapture(e.pointerId);
    e.preventDefault();
  }

  function onPointerMove(e: PointerEvent) {
    if (!grab || !stage) return;
    stage.scrollBy(grab.x - e.clientX, grab.y - e.clientY);
    grab = { x: e.clientX, y: e.clientY };
  }

  function onKey(e: KeyboardEvent) {
    // Typing (search box, note, terminal) keeps its keys; so does a dialog that handled them.
    if (e.defaultPrevented || inTextField(e)) return;
    if (e.ctrlKey || e.metaKey) {
      if (e.key === "=" || e.key === "+") zoomTo(zoom * 1.2);
      else if (e.key === "-") zoomTo(zoom / 1.2);
      else if (e.key === "0") zoomTo(1);
      else return; // other shortcuts (Ctrl+W, Ctrl+Shift+Space…) work as usual
      e.preventDefault();
      e.stopPropagation();
      return;
    }
    const step = arrowStep(e.key.toLowerCase(), tab.rtl);
    if (step === 1 || e.key === " " || e.key === "PageDown") next();
    else if (step === -1 || e.key === "PageUp") prev();
    else if (e.key === "Escape") close();
    else return;
    e.preventDefault();
    e.stopPropagation(); // the viewer behind must not move too
  }
</script>

<svelte:window onkeydowncapture={onKey} />

<!-- svelte-ignore a11y_no_static_element_interactions, a11y_interactive_supports_focus -->
<div class="book" bind:this={book} oncontextmenu={(e) => e.preventDefault()} style="top:{top}px" bind:clientWidth={width} bind:clientHeight={height} role="dialog" aria-label="Book view">
  <button class="close" onclick={close} title="Back to the normal view (Esc)"><Icon name="close" size={14} /> Close</button>

  <div
    class="stage"
    class:grabbing={!!grab}
    bind:this={stage}
    onpointerdown={onPointerDown}
    onpointermove={onPointerMove}
    onpointerup={() => (grab = null)}
    onlostpointercapture={() => (grab = null)}
  >
    {#key start}
      <div
        class="spread"
        style="width:{spreadW}px"
        in:fly={{ x: 70 * slide, duration: ui.reduceMotion ? 0 : 260, opacity: 0 }}
        out:fly={{ x: -70 * slide, duration: ui.reduceMotion ? 0 : 200, opacity: 0 }}
      >
        {#each shown as p, k}
          {@const [pw, ph] = tab.doc.pageSizes[p]}
          <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
          <div
            class="page"
            class:left={shown.length === 2 && k === 0}
            class:right={shown.length === 2 && k === 1}
            class:hidden={hidden(p)}
            style="width:{pw * scale}px;height:{ph * scale}px"
            title={hidden(p) ? "Click to show this page" : undefined}
            onclick={() => hidden(p) && reveal(p)}
          >
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
              onlink={followLink}
            />
          </div>
        {/each}
      </div>
    {/key}
  </div>

  <div class="bar">
    <span class="where">{pages.map((p) => p + 1).join("–")} / {count}</span>
  </div>

  <!-- right to left: "next" is the left button -->
  <PageControls {zoom} min={MIN_ZOOM} max={MAX_ZOOM} onzoom={(z) => zoomTo(z)} left={tab.rtl ? forward : back} right={tab.rtl ? back : forward} />
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
    overflow: auto; /* zoomed in */
  }

  .stage.grabbing {
    cursor: grabbing;
  }

  /* While turning, the old and the new spread overlap in the same cell. Auto margins center
     it, and when zoomed in it starts at the edge instead of being cut off on the left. */
  .spread {
    grid-area: 1 / 1;
    margin: auto;
    display: flex;
    gap: 6px;
  }

  .page {
    position: relative;
    box-shadow: var(--page-shadow);
  }

  .page > :global(*) {
    transition: filter 0.3s;
  }

  /* Hide the next page: blurred inside its own frame until revealed. */
  .page.hidden {
    overflow: hidden;
    cursor: pointer;
  }

  .page.hidden > :global(*) {
    filter: blur(22px);
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
    bottom: 22px;
    display: flex;
    justify-content: center;
    pointer-events: none;
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
