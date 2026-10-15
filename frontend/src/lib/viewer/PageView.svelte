<script lang="ts">
  // One page: rendered image + search highlights + selectable text layer + link hotspots.
  // Layers are laid out in PDF points and scaled as a whole with a CSS transform.
  import { pageImageUrl, type PdfLink, type Rect, type TextLine } from "../api";
  import type { Tab } from "../tab.svelte";

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
    onlink: (link: PdfLink, event: MouseEvent) => void;
  }

  let { tab, index, left, top, cssScale, renderScale, live, invert, hits, activeHit, onlink }: Props =
    $props();

  const size = $derived(tab.doc.pageSizes[index]);
  let lines = $state<TextLine[]>([]);
  let links = $state<PdfLink[]>([]);
  // Keep showing the last image while a sharper one loads after zooming.
  let shownSrc = $state<string | null>(null);

  const src = $derived(live ? pageImageUrl(tab.doc.docId, index, renderScale) : null);

  $effect(() => {
    if (!src) return;
    const target = src;
    const img = new Image();
    img.onload = () => {
      if (target === src) shownSrc = target;
    };
    img.src = target;
  });

  $effect(() => {
    if (!live) return;
    tab.textLines(index).then((l) => (lines = l));
    tab.links(index).then((l) => (links = l));
  });

  // Fit each span's natural text width to its PDF bbox so selection matches the image.
  const measure = document.createElement("canvas").getContext("2d")!;
  measure.font = "100px sans-serif";

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

  {#if live}
    <div class="layer" style="width:{size[0]}px;height:{size[1]}px;transform:scale({cssScale})">
      {#each hits as rect, i}
        <div class="hit" class:active={i === activeHit} style={box(rect)}></div>
      {/each}

      <div class="text">
        {#each lines as line}
          {#each line.spans as span}<span style={spanStyle(span)}>{span.text}</span>{/each}<br />
        {/each}
      </div>

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
    user-select: text;
    cursor: text;
  }

  .text span {
    position: absolute;
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

  .link {
    position: absolute;
    cursor: pointer;
    border-radius: 2px;
  }

  .link:hover {
    background: rgb(0 122 255 / 0.12);
  }
</style>
