<script lang="ts" module>
  // Fit each span's natural text width to its PDF bbox so selection matches the image.
  // One canvas shared by every page (a document can have thousands of pages).
  const measure = document.createElement("canvas").getContext("2d")!;
  measure.font = "100px sans-serif";

  // Text selection. The text layer is absolutely placed spans with gaps between them; over a gap
  // the browser puts the selection's end at the end of the layer, so a slow drag selects the rest
  // of the page. Like PDF.js, an "end of content" box covers the gaps while selecting and is moved
  // right next to the selection's moving end, so a gap resolves to where the pointer is.
  const layers = new Map<HTMLElement, HTMLElement>(); // text layer -> its end-of-content box
  let prevRange: Range | null = null;
  let pointerDown = false;

  function reset(end: HTMLElement, layer: HTMLElement) {
    layer.append(end);
    layer.classList.remove("selecting");
  }

  function resetAll() {
    for (const [layer, end] of layers) reset(end, layer);
    prevRange = null;
  }

  function onSelectionChange() {
    const sel = getSelection();
    if (!sel?.rangeCount) return resetAll();
    const range = sel.getRangeAt(0);
    for (const [layer, end] of layers) {
      if (range.intersectsNode(layer)) layer.classList.add("selecting");
      else reset(end, layer);
    }
    // The end that moved: the start when the end stayed put (dragging backwards).
    const modifyStart =
      !!prevRange &&
      (range.compareBoundaryPoints(Range.END_TO_END, prevRange) === 0 ||
        range.compareBoundaryPoints(Range.START_TO_END, prevRange) === 0);
    prevRange = range.cloneRange();
    let anchor: Node | null = modifyStart ? range.startContainer : range.endContainer;
    if (anchor.nodeType === Node.TEXT_NODE) anchor = anchor.parentNode;
    if (!(anchor instanceof HTMLElement) || !anchor.parentElement) return;
    const layer = anchor.parentElement;
    const end = layers.get(layer);
    if (!end) return; // not a span of a text layer
    if (!modifyStart && range.endOffset === 0) {
      // The end sits before a span's first letter: put the box after the previous span instead,
      // or it would land inside the selection.
      let prev = anchor.previousElementSibling;
      while (prev && prev.tagName !== "SPAN") prev = prev.previousElementSibling;
      if (prev) anchor = prev;
    }
    layer.insertBefore(end, modifyStart ? anchor : (anchor as Element).nextSibling);
  }

  document.addEventListener("selectionchange", onSelectionChange);
  document.addEventListener("pointerdown", () => (pointerDown = true));
  document.addEventListener("pointerup", () => {
    pointerDown = false;
    resetAll();
  });
  document.addEventListener("keyup", () => {
    if (!pointerDown) resetAll();
  });
  window.addEventListener("blur", () => {
    pointerDown = false;
    resetAll();
  });
</script>

<script lang="ts">
  // One page: rendered image + search highlights + selectable text layer + link hotspots.
  // Layers are laid out in PDF points and scaled as a whole with a CSS transform.
  import { pageImageUrl, type PdfLink, type Point, type Rect, type TextLine } from "../api";
  import { read, TINTS } from "../reading.svelte";
  import { ink, type Tab } from "../tab.svelte";

  interface Props {
    tab: Tab;
    index: number;
    left: number;
    top: number;
    cssScale: number; // CSS px per PDF point
    renderScale: number; // device px per PDF point
    live: boolean; // near the viewport → load image, text and links
    invert: boolean;
    hits: Rect[];
    activeHit: number; // index into `hits`, or -1
    stroke: Point[] | null; // ink being drawn on this page
    onlink: (link: PdfLink, event: MouseEvent) => void;
  }

  let { tab, index, left, top, cssScale, renderScale, live, invert, hits, activeHit, stroke, onlink }: Props =
    $props();

  const size = $derived(tab.doc.pageSizes[index]);
  const pending = $derived(tab.pendingInk.filter((s) => s.page === index)); // saved strokes not yet in the image
  let lines = $state<TextLine[]>([]);
  let links = $state<PdfLink[]>([]);
  // Keep showing the last image while a sharper one loads after zooming.
  let shownSrc = $state<string | null>(null);

  const src = $derived(
    live ? pageImageUrl(tab.doc.docId, index, renderScale, undefined, tab.revs[index] ?? 0) : null,
  );
  const selected = $derived(
    tab.selectedAnnot ? tab.annotations?.find((a) => a.id === tab.selectedAnnot && a.page === index) : undefined,
  );

  $effect(() => {
    if (!src) return;
    const target = src;
    const rev = tab.revs[index] ?? 0;
    const img = new Image();
    img.onload = () => {
      if (target !== src) return;
      shownSrc = target;
      // Strokes drawn on this page are now part of the image: stop drawing them on top.
      if (tab.pendingInk.some((s) => s.page === index && s.rev !== null && s.rev <= rev)) {
        tab.pendingInk = tab.pendingInk.filter((s) => !(s.page === index && s.rev !== null && s.rev <= rev));
      }
    };
    img.src = target;
  });

  $effect(() => {
    if (!live) return;
    void tab.revs[index]; // reload after OCR added a text layer
    tab.textLines(index).then((l) => (lines = l));
    tab.links(index).then((l) => (links = l));
  });

  let textEl = $state<HTMLElement>();
  $effect(() => {
    const layer = textEl;
    if (!layer) return;
    const end = document.createElement("div");
    end.className = "end-of-content";
    layer.append(end);
    layers.set(layer, end);
    const down = () => layer.classList.add("selecting");
    layer.addEventListener("pointerdown", down);
    return () => {
      layers.delete(layer);
      layer.removeEventListener("pointerdown", down);
      end.remove();
    };
  });

  function spanStyle(span: TextLine["spans"][number]) {
    const [x0, y0, x1, y1] = span.bbox;
    const natural = (measure.measureText(span.text).width * span.size) / 100;
    const sx = natural > 0 ? (x1 - x0) / natural : 1;
    return `left:${x0}px;top:${y0}px;height:${y1 - y0}px;font-size:${span.size}px;line-height:${y1 - y0}px;transform:scaleX(${sx})`;
  }

  function box([x0, y0, x1, y1]: Rect) {
    return `left:${x0}px;top:${y0}px;width:${x1 - x0}px;height:${y1 - y0}px`;
  }
</script>

<div
  class="page"
  data-page={index}
  style="left:{left}px;top:{top}px;width:{size[0] * cssScale}px;height:{size[1] * cssScale}px"
>
  {#if shownSrc && live}
    <img class:invert src={shownSrc} alt="" draggable="false" />
  {/if}

  {#if tab.isBookmarked(index)}
    <span class="ribbon" title="Bookmarked page"></span>
  {/if}

  {#if read.tint !== "none"}
    <div class="tint" style="background:{TINTS[read.tint].color}"></div>
  {/if}

  {#if live}
    <div class="layer" style="width:{size[0]}px;height:{size[1]}px;transform:scale({cssScale})">
      {#if selected}
        {#each selected.rects as rect}
          <div class="selected" style={box(rect)}></div>
        {/each}
      {/if}

      {#if tab.moving}
        {@const m = tab.moving}
        {#each tab.annotations?.find((a) => a.id === m.id && a.page === index)?.rects ?? [] as [x0, y0, x1, y1]}
          <div class="moving" style={box([x0 + m.dx, y0 + m.dy, x1 + m.dx, y1 + m.dy])}></div>
        {/each}
      {/if}

      {#each hits as rect, i}
        <div class="hit" class:active={i === activeHit} style={box(rect)}></div>
      {/each}

      <div class="text" bind:this={textEl}>
        {#each lines as line}
          {#each line.spans as span}<span style={spanStyle(span)}>{span.text}</span>{/each}<br />
        {/each}
      </div>

      {#if stroke || pending.length}
        <svg class="ink" viewBox="0 0 {size[0]} {size[1]}" width={size[0]} height={size[1]}>
          {#each pending as s}
            <polyline points={s.points.map((p) => p.join(",")).join(" ")} style="stroke:{s.color};stroke-width:{s.width}" />
          {/each}
          {#if stroke}
            <polyline points={stroke.map((p) => p.join(",")).join(" ")} style="stroke:{ink.color};stroke-width:{ink.width}" />
          {/if}
        </svg>
      {/if}

      {#each links as link}
        {#if link.kind !== "other"}
          <button
            class="link"
            style={box(link.rect)}
            title={link.kind === "uri" ? link.uri : `Page ${link.page + 1}`}
            onclick={(e) => onlink(link, e)}
            aria-label={link.kind === "uri" ? `Link to ${link.uri}` : `Link to page ${link.page + 1}`}
          ></button>
        {/if}
      {/each}
    </div>
  {/if}
</div>

<style>
  .page {
    position: absolute;
    background: white;
    box-shadow: var(--page-shadow);
    border-radius: 2px;
    overflow: hidden;
  }

  img {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
  }

  .ribbon {
    position: absolute;
    top: 0;
    right: 18px;
    z-index: 3;
    width: 14px;
    height: 22px;
    background: #ff375f;
    clip-path: polygon(0 0, 100% 0, 100% 100%, 50% 72%, 0 100%);
    pointer-events: none;
  }

  .tint {
    position: absolute;
    inset: 0;
    mix-blend-mode: multiply;
    pointer-events: none;
  }

  img.invert {
    filter: invert(0.9) hue-rotate(180deg);
  }

  .layer {
    position: absolute;
    left: 0;
    top: 0;
    transform-origin: 0 0;
  }

  .text {
    position: absolute;
    inset: 0;
    z-index: 0;
    user-select: text;
    cursor: text;
  }

  .text span {
    position: absolute;
    z-index: 1;
    white-space: pre;
    color: transparent;
    font-family: sans-serif;
    transform-origin: 0 0;
  }

  .text ::selection {
    background: rgb(0 122 255 / 0.3);
    color: transparent;
  }

  .text br::selection {
    background: transparent;
  }

  /* Covers the gaps between spans only while selecting (see the module script). */
  .text :global(.end-of-content) {
    position: absolute;
    inset: 100% 0 0;
    z-index: 0;
    cursor: inherit;
    user-select: none;
  }

  .text:global(.selecting) :global(.end-of-content) {
    top: 0;
  }

  .hit {
    position: absolute;
    background: rgb(255 204 0 / 0.45);
    border-radius: 1px;
    mix-blend-mode: multiply;
  }

  .hit.active {
    background: rgb(255 149 0 / 0.7);
    outline: 1px solid rgb(255 149 0);
  }

  .ink {
    position: absolute;
    inset: 0;
    pointer-events: none;
  }

  .ink polyline {
    fill: none;
    stroke: #0a84ff;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  .selected {
    position: absolute;
    outline: 2px solid var(--accent);
    outline-offset: 1px;
    border-radius: 2px;
    pointer-events: none;
  }

  .moving {
    position: absolute;
    z-index: 2;
    border: 1.5px dashed var(--accent);
    border-radius: 3px;
    background: rgb(0 122 255 / 0.12);
    pointer-events: none;
  }

  .link {
    position: absolute;
    cursor: pointer;
    border-radius: 2px;
  }

  .link:hover {
    background: rgb(0 122 255 / 0.12);
  }
</style>
