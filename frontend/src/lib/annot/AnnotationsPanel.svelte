<script lang="ts">
  // Slide-in panel on the right of a PDF: every annotation, grouped by page; search, filter by
  // type and colour; click to jump there.
  import type { Annotation } from "../api";
  import Icon from "../Icon.svelte";
  import type { Tab } from "../tab.svelte";
  import { COLORS, KIND_LABEL } from "./colors";

  interface Props {
    tab: Tab;
    topInset: number;
  }

  let { tab, topInset }: Props = $props();

  type Filter = "all" | "marks" | "notes";
  let filter = $state<Filter>("all");
  let colorFilter = $state<string | null>(null);
  let query = $state("");

  $effect(() => {
    if (tab.panelOpen) tab.loadAnnotations();
  });

  const visible = $derived.by(() => {
    const q = query.trim().toLowerCase();
    return (tab.annotations ?? [])
      .filter((a) => a.kind !== "other")
      .filter((a) =>
        filter === "all" ? true : filter === "notes" ? a.kind === "note" || a.kind === "freetext" : a.kind !== "note" && a.kind !== "freetext",
      )
      .filter((a) => !colorFilter || a.color === colorFilter)
      .filter((a) => !q || a.quote.toLowerCase().includes(q) || a.contents.toLowerCase().includes(q))
      .sort((a, b) => a.page - b.page || a.rects[0][1] - b.rects[0][1]);
  });

  const groups = $derived.by(() => {
    const out: { page: number; items: Annotation[] }[] = [];
    for (const a of visible) {
      if (out.at(-1)?.page !== a.page) out.push({ page: a.page, items: [] });
      out.at(-1)!.items.push(a);
    }
    return out;
  });

  function open(a: Annotation) {
    tab.reveal(a.id);
    if (tab.mdOpen && tab.hasPin(a.id)) tab.mdReveal = { id: a.id, nonce: Date.now() };
  }
</script>

<aside class:open={tab.panelOpen} style="top:{topInset}px" aria-hidden={!tab.panelOpen}>
  <header>
    <div class="title">
      <span>Annotations</span>
      <span class="count">{visible.length}</span>
      <button class="close" onclick={() => (tab.panelOpen = false)} aria-label="Close panel">
        <Icon name="close" size={13} />
      </button>
    </div>
    <label class="search">
      <Icon name="search" size={13} />
      <input bind:value={query} placeholder="Search annotations" spellcheck="false" />
    </label>
    <div class="filters">
      <div class="segmented">
        {#each [["all", "All"], ["marks", "Marks"], ["notes", "Notes"]] as [value, label]}
          <button aria-pressed={filter === value} onclick={() => (filter = value as Filter)}>{label}</button>
        {/each}
      </div>
      <div class="colors">
        {#each COLORS as c}
          <button
            class="dot"
            class:on={colorFilter === c.value}
            style="--c:{c.value}"
            title={c.name}
            onclick={() => (colorFilter = colorFilter === c.value ? null : c.value)}
          ></button>
        {/each}
      </div>
    </div>
  </header>

  <div class="list">
    {#if tab.annotations === null}
      <p class="empty">Loading…</p>
    {:else if !groups.length}
      <p class="empty">
        {tab.annotations.length ? "No matches." : "No annotations yet. Select text to highlight it."}
      </p>
    {/if}
    {#each groups as group (group.page)}
      <h3>Page {group.page + 1}</h3>
      {#each group.items as a (a.id)}
        <div
          class="item"
          class:selected={tab.selectedAnnot === a.id}
          role="button"
          tabindex="0"
          onclick={() => open(a)}
          onkeydown={(e) => e.key === "Enter" && open(a)}
        >
          <span class="bar" style="--c:{a.color}"></span>
          <div class="body">
            <div class="meta">
              <span>{KIND_LABEL[a.kind]}</span>
              {#if tab.hasPin(a.id)}<span class="pinned" title="Has a note in the integrated MD">⎘ note</span>{/if}
            </div>
            {#if a.quote}<p class="quote">“{a.quote}”</p>{/if}
            {#if a.contents}<p class="contents">{a.contents}</p>{/if}
          </div>
          <button
            class="delete"
            title="Delete"
            onclick={(e) => {
              e.stopPropagation();
              tab.deleteAnnotation(a.id);
            }}
          >
            <Icon name="trash" size={14} />
          </button>
        </div>
      {/each}
    {/each}
  </div>
</aside>

<style>
  aside {
    position: absolute;
    right: 0;
    bottom: 0;
    z-index: 7;
    width: 300px;
    display: flex;
    flex-direction: column;
    background: var(--popover);
    backdrop-filter: saturate(180%) blur(24px);
    box-shadow:
      -0.5px 0 0 var(--separator),
      -8px 0 30px rgb(0 0 0 / 0.12);
    transform: translateX(105%);
    transition: transform 0.22s cubic-bezier(0.2, 0.8, 0.2, 1);
    visibility: hidden;
  }

  aside.open {
    transform: none;
    visibility: visible;
  }

  header {
    padding: 10px 12px 8px;
    border-bottom: 0.5px solid var(--separator);
  }

  .title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-weight: 600;
    margin-bottom: 8px;
  }

  .count {
    font-size: 11px;
    font-weight: 500;
    color: var(--secondary);
    background: var(--hover);
    border-radius: 10px;
    padding: 0 6px;
  }

  .close {
    margin-left: auto;
    display: grid;
    place-items: center;
    width: 22px;
    height: 22px;
    border-radius: 6px;
    color: var(--secondary);
  }

  .close:hover {
    background: var(--hover);
  }

  .search {
    display: flex;
    align-items: center;
    gap: 5px;
    height: 26px;
    padding: 0 8px;
    border-radius: 9px;
    background: var(--hover);
    color: var(--secondary);
  }

  .search:focus-within {
    box-shadow: 0 0 0 3px var(--focus-ring);
  }

  .search input {
    flex: 1;
    min-width: 0;
    border: none;
    outline: none;
    background: none;
    font: inherit;
    color: var(--text);
  }

  .filters {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 8px;
  }

  .segmented {
    display: flex;
    padding: 2px;
    border-radius: 9px;
    background: var(--hover);
  }

  .segmented button {
    padding: 0 8px;
    border-radius: 6px;
    font-size: 11px;
    color: var(--secondary);
  }

  .segmented button[aria-pressed="true"] {
    background: var(--surface);
    color: var(--text);
    box-shadow: 0 1px 2px rgb(0 0 0 / 0.12);
  }

  .colors {
    display: flex;
    gap: 5px;
  }

  .dot {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--c);
    box-shadow: inset 0 0 0 1px rgb(0 0 0 / 0.12);
  }

  .dot.on {
    box-shadow:
      0 0 0 2px var(--popover),
      0 0 0 3.5px var(--accent);
  }

  .list {
    flex: 1;
    overflow: auto;
    padding: 4px 8px 20px;
  }

  h3 {
    margin: 12px 6px 4px;
    font-size: 11px;
    font-weight: 600;
    color: var(--secondary);
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .item {
    position: relative;
    display: flex;
    gap: 8px;
    padding: 7px 8px;
    border-radius: 10px;
    cursor: default;
  }

  .item:hover {
    background: var(--hover);
  }

  .item.selected {
    background: var(--selection);
    box-shadow: inset 0 0 0 1px var(--accent);
  }

  .bar {
    flex: none;
    width: 4px;
    border-radius: 2px;
    background: var(--c);
  }

  .body {
    flex: 1;
    min-width: 0;
  }

  .meta {
    display: flex;
    gap: 8px;
    font-size: 11px;
    color: var(--secondary);
  }

  .pinned {
    color: var(--accent);
    font-weight: 500;
  }

  .quote,
  .contents {
    margin: 2px 0 0;
    font-size: 12px;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .quote {
    font-style: italic;
    color: var(--secondary);
  }

  .delete {
    position: absolute;
    top: 6px;
    right: 6px;
    display: grid;
    place-items: center;
    width: 24px;
    height: 22px;
    border-radius: 6px;
    color: var(--secondary);
    opacity: 0;
  }

  .item:hover .delete {
    opacity: 1;
  }

  .delete:hover {
    background: rgb(255 59 48 / 0.12);
    color: #ff3b30;
  }

  .empty {
    margin: 16px 8px;
    color: var(--secondary);
    font-size: 12px;
  }
</style>
