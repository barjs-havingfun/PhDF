<script lang="ts" module>
  export type SidebarMode = "outline" | "pages" | "bookmarks" | "files";
</script>

<script lang="ts">
  // Left sidebar: document outline, page thumbnails or bookmarks — in grading mode, the exams
  // of the folder instead of the outline.
  import { kbd } from "./platform";
  import { pageImageUrl } from "./api";
  import { grading } from "./grading/grading.svelte";
  import Icon from "./Icon.svelte";
  import OutlineNode from "./OutlineNode.svelte";
  import type { Tab } from "./tab.svelte";

  interface Props {
    tab: Tab;
    mode: SidebarMode;
    invert: boolean;
    onmode: (mode: SidebarMode) => void;
  }

  let { tab, mode, invert, onmode }: Props = $props();

  const THUMB_WIDTH = 120;
  let list = $state<HTMLElement>();

  $effect(() => {
    if (mode === "outline") tab.loadOutline();
    if (mode === "bookmarks") tab.loadBookmarks();
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
    {#if grading.session}
      <button role="tab" aria-selected={mode === "files"} onclick={() => onmode("files")}>
        Exams
      </button>
    {:else}
      <button role="tab" aria-selected={mode === "outline"} onclick={() => onmode("outline")}>
        Contents
      </button>
    {/if}
    <button role="tab" aria-selected={mode === "pages"} onclick={() => onmode("pages")}>
      Pages
    </button>
    <button role="tab" aria-selected={mode === "bookmarks"} onclick={() => onmode("bookmarks")}>
      Marks
    </button>
  </div>

  <div class="list" bind:this={list}>
    {#if mode === "files" && grading.session}
      {@const g = grading.session}
      <p class="folder" title={g.folder}><Icon name="folder" size={14} /> {g.title}</p>
      <p class="progress">{g.done.length} of {g.exams.length} done</p>
      {#each g.exams as exam, i (exam.rel)}
        <button class="exam" class:current={i === g.index} onclick={() => g.show(i)} title={exam.rel} disabled={g.busy}>
          <span class="n">{exam.num}</span>
          <span class="ename">{exam.name}</span>
          {#if g.isDone(exam)}<span class="tick"><Icon name="check" size={11} /></span>{/if}
        </button>
      {/each}
    {:else if mode === "outline"}
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
    {:else if mode === "bookmarks"}
      <button class="add-mark" onclick={() => tab.toggleBookmark()}>
        {tab.isBookmarked(tab.page) ? "Remove bookmark from" : "Bookmark"} page {tab.page + 1} <span class="key">{kbd("Ctrl+B")}</span>
      </button>
      {#if !tab.bookmarks.length}
        <p class="empty">No bookmarks yet.</p>
      {/if}
      {#each tab.bookmarks as b (b.page)}
        <div class="mark" class:current={b.page === tab.page}>
          <button class="go" onclick={() => go(b.page)}><span class="pg">{b.page + 1}</span></button>
          <input
            value={b.label}
            placeholder="Page {b.page + 1}"
            onchange={(e) => tab.renameBookmark(b.page, (e.currentTarget as HTMLInputElement).value)}
            onkeydown={(e) => e.key === "Enter" && (e.currentTarget as HTMLInputElement).blur()}
            spellcheck="false"
          />
          <button class="del" title="Remove" onclick={() => tab.toggleBookmark(b.page)}>×</button>
        </div>
      {/each}
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

  .folder {
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 6px 4px 0;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .progress {
    margin: 2px 4px 8px;
    font-size: 11.5px;
    color: var(--secondary);
  }

  .exam {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 5px 6px;
    border-radius: 7px;
    text-align: left;
  }

  .exam:hover {
    background: var(--hover);
  }

  .exam.current {
    background: var(--accent);
    color: var(--accent-text);
  }

  .exam .n {
    min-width: 20px;
    font-size: 11px;
    color: var(--secondary);
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  .exam.current .n {
    color: inherit;
  }

  .ename {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .tick {
    display: grid;
    place-items: center;
    width: 15px;
    height: 15px;
    border-radius: 50%;
    background: #34c759;
    color: white;
  }

  .add-mark {
    width: 100%;
    margin: 4px 0 8px;
    padding: 5px 8px;
    border-radius: 7px;
    background: var(--hover);
    font-size: 12px;
    text-align: left;
  }

  .add-mark:hover {
    box-shadow: inset 0 0 0 1px var(--accent);
  }

  .key {
    float: right;
    color: var(--tertiary);
    font-size: 11px;
  }

  .mark {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 3px 4px;
    border-radius: 7px;
  }

  .mark.current,
  .mark:hover {
    background: var(--hover);
  }

  .pg {
    display: inline-block;
    min-width: 30px;
    padding: 1px 6px;
    border-radius: 5px;
    background: #ff375f;
    color: white;
    font-size: 11px;
    text-align: center;
    font-variant-numeric: tabular-nums;
  }

  .mark input {
    flex: 1;
    min-width: 0;
    border: none;
    background: none;
    color: var(--text);
    font: 12.5px var(--font);
    outline: none;
    user-select: text;
  }

  .mark input:focus {
    box-shadow: 0 1px 0 var(--accent);
  }

  .del {
    width: 20px;
    color: var(--tertiary);
    opacity: 0;
  }

  .mark:hover .del {
    opacity: 1;
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
