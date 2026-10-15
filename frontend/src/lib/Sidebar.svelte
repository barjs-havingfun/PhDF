<script lang="ts">
  // Left sidebar: document outline or page thumbnails.
  import { pageImageUrl } from "./api";
  import OutlineNode from "./OutlineNode.svelte";
  import type { Tab } from "./tab.svelte";

  interface Props {
    tab: Tab;
    mode: "outline" | "pages";
    invert: boolean;
    onmode: (mode: "outline" | "pages") => void;
  }

  let { tab, mode, invert, onmode }: Props = $props();

  const THUMB_WIDTH = 120;
  let list = $state<HTMLElement>();

  $effect(() => {
    if (mode === "outline") tab.loadOutline();
  });

  // Keep the current page's thumbnail in view.
  $effect(() => {
    if (mode !== "pages" || !list) return;
    list.querySelector(`[data-thumb="${tab.page}"]`)?.scrollIntoView({ block: "nearest" });
  });

  function go(page: number) {
    tab.navigate({ page });
  }

  function thumbScale(width: number) {
    return Math.min((THUMB_WIDTH / width) * devicePixelRatio, 2);
  }
</script>

<aside>
  <div class="segmented" role="tablist">
    <button role="tab" aria-selected={mode === "outline"} onclick={() => onmode("outline")}>
      Contents
    </button>
    <button role="tab" aria-selected={mode === "pages"} onclick={() => onmode("pages")}>
      Pages
    </button>
  </div>

  <div class="list" bind:this={list}>
    {#if mode === "outline"}
      {#if tab.outline === null}
        <p class="empty">Loading…</p>
      {:else if tab.outline.length === 0}
        <p class="empty">This document has no table of contents.</p>
      {:else}
        <ul>
          {#each tab.outline as item}
            <OutlineNode {item} current={tab.page} onnavigate={go} />
          {/each}
        </ul>
      {/if}
    {:else}
      {#each tab.doc.pageSizes as [w, h], i (i)}
        <button class="thumb" class:current={i === tab.page} data-thumb={i} onclick={() => go(i)}>
          <span class="frame" style="aspect-ratio:{w} / {h}">
            <img
              class:invert
              loading="lazy"
              src={pageImageUrl(tab.doc.docId, i, thumbScale(w), undefined, tab.revs[i] ?? 0)}
              alt="Page {i + 1}"
              draggable="false"
            />
          </span>
          <span class="num">{i + 1}</span>
        </button>
      {/each}
    {/if}
  </div>
</aside>

<style>
  aside {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    background: var(--sidebar);
    border-right: 0.5px solid var(--separator);
  }

  .segmented {
    display: flex;
    margin: 10px 10px 6px;
    padding: 2px;
    border-radius: 7px;
    background: var(--hover);
  }

  .segmented button {
    flex: 1;
    padding: 2px 0;
    border-radius: 5px;
    font-size: 12px;
    color: var(--secondary);
  }

  .segmented button[aria-selected="true"] {
    background: var(--surface);
    color: var(--text);
    box-shadow: 0 1px 2px rgb(0 0 0 / 0.12);
  }

  .list {
    flex: 1;
    overflow: auto;
    padding: 4px 8px 16px;
  }

  ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .empty {
    margin: 16px 8px;
    color: var(--secondary);
  }

  .thumb {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    width: 100%;
    padding: 8px 0;
  }

  .frame {
    display: block;
    width: 120px;
    background: white;
    box-shadow: var(--page-shadow);
    border-radius: 2px;
    overflow: hidden;
    outline: 3px solid transparent;
    outline-offset: 2px;
  }

  .thumb.current .frame {
    outline-color: var(--accent);
  }

  .frame img {
    display: block;
    width: 100%;
    height: 100%;
  }

  img.invert {
    filter: invert(0.9) hue-rotate(180deg);
  }

  .num {
    font-size: 11px;
    color: var(--secondary);
    padding: 0 6px;
    border-radius: 4px;
  }

  .thumb.current .num {
    background: var(--accent);
    color: var(--accent-text);
  }
</style>
