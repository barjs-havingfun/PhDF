<script lang="ts" module>
  import type { Rect as PdfRect } from "../api";

  export interface TextSelection {
    text: string;
    byPage: Map<number, PdfRect[]>; // PDF-space rects per page, one per line
    box: DOMRect; // on screen, for placing the menu
  }
</script>

<script lang="ts">
  // Continuous, virtualized page view. Only pages near the viewport load images/text/links.
  // Owns scrolling, zoom/fit and position tracking for one tab.
  import { onMount, tick } from "svelte";
  import { api, type Annotation, type FitMode, type PdfLink, type Rect } from "../api";
  import { ink, type Jump, type Tab } from "../tab.svelte";
  import type { Point } from "../api";
  import PageView from "./PageView.svelte";
  import { noteScroll, read, RULER_SIZES } from "../reading.svelte";

  interface Props {
    tab: Tab;
    topInset: number; // height of the translucent header overlapping the top
    invert: boolean;
    onlink: (link: PdfLink, event: MouseEvent) => void;
    onselection: (sel: TextSelection | null) => void;
    onannot: (annot: Annotation, event: MouseEvent) => void;
    /** Click on a page while the note/text tool is active. */
    onplace: (page: number, x: number, y: number, event: MouseEvent) => void;
  }

  let { tab, topInset, invert, onlink, onselection, onannot, onplace }: Props = $props();

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

  // Pages within half a viewport above and one below are "live" (each live page holds a
  // full-resolution image, ~20 MB decoded for a scanned book page).
  const liveRange = $derived.by(() => {
    const lo = scrollTop - viewHeight * 0.5;
    const hi = scrollTop + viewHeight * 1.5;
    return [pageAt(lo), pageAt(hi)] as const;
  });

  // Only pages around the viewport exist in the DOM at all (a book can have thousands).
  const MOUNT_MARGIN = 1;
  const mounted = $derived.by(() => {
    const from = Math.max(0, liveRange[0] - MOUNT_MARGIN);
    const to = Math.min(sizes.length - 1, liveRange[1] + MOUNT_MARGIN);
    return Array.from({ length: Math.max(to - from + 1, 0) }, (_, k) => from + k);
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
      noteScroll(tab.id, loc.page + loc.scroll);
      savePosition();
    });
  }

  // --- selection, annotation clicks, placing notes ------------------------------------------

  /** PDF-space point under a screen point, with its page. */
  function pdfPoint(clientX: number, clientY: number) {
    const el = document.elementsFromPoint(clientX, clientY).find((e) => e.matches(".page")) as
      | HTMLElement
      | undefined;
    if (!el || !scroller.contains(el)) return null;
    const r = el.getBoundingClientRect();
    return {
      page: Number(el.dataset.page),
      x: (clientX - r.left) / cssScale,
      y: (clientY - r.top) / cssScale,
    };
  }

  /** Turn the browser selection into per-page, per-line rects in PDF space. */
  function readSelection(): TextSelection | null {
    const sel = getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount || !scroller.contains(sel.anchorNode)) return null;
    const range = sel.getRangeAt(0);
    const pages = [...scroller.querySelectorAll<HTMLElement>(".page")].map((el) => ({
      page: Number(el.dataset.page),
      box: el.getBoundingClientRect(),
    }));
    const byPage = new Map<number, Rect[]>();
    for (const r of range.getClientRects()) {
      if (r.width < 1 || r.height < 1) continue;
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      const hit = pages.find((p) => cx >= p.box.left && cx <= p.box.right && cy >= p.box.top && cy <= p.box.bottom);
      if (!hit) continue;
      const rect: Rect = [
        (r.left - hit.box.left) / cssScale,
        (r.top - hit.box.top) / cssScale,
        (r.right - hit.box.left) / cssScale,
        (r.bottom - hit.box.top) / cssScale,
      ];
      const list = byPage.get(hit.page) ?? [];
      list.push(rect);
      byPage.set(hit.page, list);
    }
    for (const [page, rects] of byPage) byPage.set(page, mergeLines(rects));
    if (!byPage.size) return null;
    return { text: sel.toString(), byPage, box: range.getBoundingClientRect() };
  }

  /** Union rects that sit on the same text line. */
  function mergeLines(rects: Rect[]): Rect[] {
    const sorted = [...rects].sort((a, b) => a[1] - b[1] || a[0] - b[0]);
    const lines: Rect[] = [];
    for (const r of sorted) {
      const last = lines[lines.length - 1];
      const overlap = last ? Math.min(last[3], r[3]) - Math.max(last[1], r[1]) : 0;
      if (last && overlap > 0.5 * Math.min(last[3] - last[1], r[3] - r[1])) {
        lines[lines.length - 1] = [Math.min(last[0], r[0]), Math.min(last[1], r[1]), Math.max(last[2], r[2]), Math.max(last[3], r[3])];
      } else lines.push(r);
    }
    return lines;
  }

  // Freehand ink (draw tool): one stroke per press, added as an ink annotation on release.
  let drawing = $state<{ page: number; points: Point[] } | null>(null);

  function startStroke(e: PointerEvent) {
    const pt = pdfPoint(e.clientX, e.clientY);
    if (!pt) return false;
    e.preventDefault(); // no text selection while drawing
    try {
      scroller.setPointerCapture(e.pointerId);
    } catch {
      // synthetic event
    }
    drawing = { page: pt.page, points: [[pt.x, pt.y]] };
    return true;
  }

  function onPointerMove(e: PointerEvent) {
    if (!drawing) return;
    const el = scroller.querySelector<HTMLElement>(`.page[data-page="${drawing.page}"]`);
    if (!el) return;
    const r = el.getBoundingClientRect();
    const x = (e.clientX - r.left) / cssScale;
    const y = (e.clientY - r.top) / cssScale;
    const [lx, ly] = drawing.points[drawing.points.length - 1];
    if (Math.hypot(x - lx, y - ly) >= 1) drawing.points.push([x, y]);
  }

  async function endStroke() {
    const stroke = drawing;
    drawing = null;
    if (!stroke || stroke.points.length < 2) return;
    await tab.addAnnotation(stroke.page, "ink", [], ink.color, "", [stroke.points], ink.width);
  }

  // Reading ruler: a band that follows the pointer; everything else is dimmed.
  let rulerY = $state<number | null>(null);
  function onRulerMove(e: PointerEvent) {
    if (!read.ruler) return;
    rulerY = e.clientY - scroller.getBoundingClientRect().top;
  }

  // Dragging a note, text box or (selected) drawing to a new spot on its page.
  let dragging: { annot: Annotation; page: number; x: number; y: number } | null = null;
  const MOVABLE = ["note", "freetext", "ink"];

  function startMove(e: PointerEvent) {
    const pt = pdfPoint(e.clientX, e.clientY);
    const hit = pt && annotationAt(pt.page, pt.x, pt.y);
    if (!pt || !hit || !MOVABLE.includes(hit.kind)) return false;
    if (hit.kind === "ink" && tab.selectedAnnot !== hit.id) return false; // click a drawing first
    e.preventDefault(); // no text selection
    try {
      scroller.setPointerCapture(e.pointerId);
    } catch {
      // synthetic event
    }
    dragging = { annot: hit, page: pt.page, x: pt.x, y: pt.y };
    return true;
  }

  let overMovable = $state(false);
  let hoverFrame = 0;

  function onMove(e: PointerEvent) {
    if (!dragging) {
      // A move cursor over things that can be dragged (checked at most once per frame).
      if (hoverFrame || !tab.annotations?.some((a) => MOVABLE.includes(a.kind))) return;
      const { clientX, clientY, buttons } = e;
      hoverFrame = requestAnimationFrame(() => {
        hoverFrame = 0;
        const pt = tab.tool === "draw" || buttons ? null : pdfPoint(clientX, clientY);
        const hit = pt && annotationAt(pt.page, pt.x, pt.y);
        overMovable = !!hit && MOVABLE.includes(hit.kind) && (hit.kind !== "ink" || tab.selectedAnnot === hit.id);
      });
      return;
    }
    if (Math.hypot(e.clientX - downAt.x, e.clientY - downAt.y) <= 3 && !tab.moving) return;
    const el = scroller.querySelector<HTMLElement>(`.page[data-page="${dragging.page}"]`);
    if (!el) return;
    const r = el.getBoundingClientRect();
    const [w, h] = sizes[dragging.page];
    // Keep the annotation on its page.
    const box = dragging.annot.rects.reduce((b, q) => [Math.min(b[0], q[0]), Math.min(b[1], q[1]), Math.max(b[2], q[2]), Math.max(b[3], q[3])]);
    const dx = Math.min(Math.max((e.clientX - r.left) / cssScale - dragging.x, -box[0]), w - box[2]);
    const dy = Math.min(Math.max((e.clientY - r.top) / cssScale - dragging.y, -box[1]), h - box[3]);
    tab.moving = { id: dragging.annot.id, dx, dy };
  }

  /** Finish a drag; true when the annotation was moved (so the click is not handled). */
  function endMove(): boolean {
    const d = dragging;
    const moved = tab.moving;
    dragging = null;
    if (!d || !moved || (Math.abs(moved.dx) < 0.5 && Math.abs(moved.dy) < 0.5)) {
      tab.moving = null;
      return false;
    }
    tab.selectedAnnot = d.annot.id;
    tab.moveAnnotation(d.annot.id, moved.dx, moved.dy).finally(() => (tab.moving = null));
    return true;
  }

  let downAt = { x: 0, y: 0 };
  function onPointerDown(e: PointerEvent) {
    downAt = { x: e.clientX, y: e.clientY };
    if (e.button !== 0) return;
    if (tab.tool === "draw") startStroke(e);
    else startMove(e);
  }

  function onPointerUp(e: PointerEvent) {
    if (e.button !== 0) return;
    if (drawing) {
      endStroke();
      return;
    }
    if (dragging && endMove()) return;
    const moved = Math.hypot(e.clientX - downAt.x, e.clientY - downAt.y) > 3;
    requestAnimationFrame(() => {
      const sel = readSelection();
      onselection(sel);
      if (sel || moved) return;
      if ((e.target as HTMLElement).closest(".link")) return;
      const pt = pdfPoint(e.clientX, e.clientY);
      if (!pt) {
        tab.selectedAnnot = null;
        return;
      }
      const hit = annotationAt(pt.page, pt.x, pt.y);
      if (hit) onannot(hit, e);
      else if (tab.tool !== "select") onplace(pt.page, pt.x, pt.y, e);
      else tab.selectedAnnot = null;
    });
  }

  function annotationAt(page: number, x: number, y: number): Annotation | undefined {
    const pad = 2;
    // Last drawn wins, like in the PDF itself.
    return tab.annotations
      ?.filter((a) => a.page === page && a.kind !== "other")
      .findLast((a) => a.rects.some(([x0, y0, x1, y1]) => x >= x0 - pad && x <= x1 + pad && y >= y0 - pad && y <= y1 + pad));
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
    tab.loadAnnotations();
    scroller.addEventListener("wheel", onWheel, { passive: false });
    // Only a window resize re-fits the page. When a pane divider or the sidebar changes this
    // view's width, the zoom stays and the page is cropped on the side that moved.
    let windowSize = `${innerWidth}x${innerHeight}`;
    let left = scroller.getBoundingClientRect().left;
    const observer = new ResizeObserver(() => {
      viewWidth = scroller.clientWidth;
      viewHeight = scroller.clientHeight;
      const newLeft = scroller.getBoundingClientRect().left;
      const newWindowSize = `${innerWidth}x${innerHeight}`;
      if (!ready) return;
      if (newWindowSize !== windowSize && tab.fit !== "none") applyZoom(fitZoom(tab.fit), tab.fit);
      else if (newLeft !== left) scroller.scrollLeft += newLeft - left; // keep the page in place
      windowSize = newWindowSize;
      left = newLeft;
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

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="scroller"
  class:placing={tab.tool !== "select"}
  class:movable={overMovable || !!tab.moving}
  bind:this={scroller}
  onscroll={onScroll}
  onpointerdown={onPointerDown}
  onpointermove={(e) => (onPointerMove(e), onMove(e), onRulerMove(e))}
  onpointerup={onPointerUp}
>
  <div class="content" style="height:{contentHeight}px;width:{contentWidth}px">
    {#each mounted as i (i)}
      {@const size = sizes[i]}
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
        stroke={drawing?.page === i ? drawing.points : null}
        {onlink}
      />
    {/each}
  </div>
</div>

{#if read.ruler}
  {@const band = RULER_SIZES[read.rulerSize]}
  {@const y = rulerY ?? topInset + (viewHeight - topInset) * 0.35}
  <div class="ruler-shade" style="top:{topInset}px;height:{Math.max(y - band / 2 - topInset, 0)}px"></div>
  <div class="ruler-line" style="top:{y - band / 2}px;height:{band}px"></div>
  <div class="ruler-shade" style="top:{y + band / 2}px;bottom:0"></div>
{/if}

<style>
  .ruler-shade {
    position: absolute;
    left: 0;
    right: 0;
    z-index: 5;
    background: rgb(0 0 0 / 0.42);
    pointer-events: none;
  }

  .ruler-line {
    position: absolute;
    left: 0;
    right: 0;
    z-index: 5;
    box-shadow:
      inset 0 1px 0 rgb(255 214 10 / 0.7),
      inset 0 -1px 0 rgb(255 214 10 / 0.7);
    pointer-events: none;
  }

  .scroller {
    position: absolute;
    inset: 0;
    overflow: auto;
    background: var(--canvas);
  }

  .content {
    position: relative;
  }

  .movable :global(.page),
  .movable :global(.page .text) {
    cursor: move !important;
  }

  .placing :global(.page),
  .placing :global(.page .text) {
    cursor: crosshair;
  }
</style>
