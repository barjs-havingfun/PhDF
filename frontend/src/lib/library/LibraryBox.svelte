<script lang="ts">
  // Library: every document PhDF has opened — cover, progress, time spent reading.
  import { onMount } from "svelte";
  import { api, type LibraryItem } from "../api";

  let { onopenpath }: { onopenpath: (path: string) => void } = $props();

  let items = $state<LibraryItem[]>([]);
  let covers = $state<Record<string, string | null>>({});
  let filter = $state("");
  let showAll = $state(false);

  const LIMIT = 12;

  onMount(async () => {
    const py = await api();
    items = await py.library();
    // Covers come one by one (cached after the first time).
    for (const item of items.slice(0, 40)) {
      covers[item.docId] = await py.library_cover(item.docId, item.path);
    }
  });

  const shown = $derived.by(() => {
    const q = filter.trim().toLowerCase();
    const list = q ? items.filter((i) => i.title.toLowerCase().includes(q) || i.path.toLowerCase().includes(q)) : items;
    return showAll || q ? list : list.slice(0, LIMIT);
  });

  function progress(i: LibraryItem) {
    return i.pageCount ? Math.round(((i.page + 1) / i.pageCount) * 100) : 0;
  }

  function time(seconds: number) {
    if (seconds < 60) return seconds ? "< 1 min read" : "not read yet";
    const min = Math.round(seconds / 60);
    return min < 60 ? `${min} min read` : `${Math.floor(min / 60)} h ${min % 60} min read`;
  }
</script>

{#if items.length}
  <section class="box">
    <header>
      <h2>Library <span class="count">{items.length}</span></h2>
      <input bind:value={filter} placeholder="Filter" spellcheck="false" />
    </header>
    <div class="grid">
      {#each shown as item (item.docId)}
        <button class="book" class:missing={!item.exists} disabled={!item.exists} onclick={() => onopenpath(item.path)} title={item.path}>
          <span class="cover">
            {#if covers[item.docId]}
              <img src={covers[item.docId]} alt="" />
            {:else}
              <span class="ph">{item.title.slice(0, 1)}</span>
            {/if}
            <span class="progress" style="width:{progress(item)}%"></span>
          </span>
          <span class="title">{item.title}</span>
          <span class="meta">{item.exists ? `${progress(item)}% · ${time(item.seconds)}` : "File missing"}</span>
        </button>
      {/each}
    </div>
    {#if !filter && items.length > LIMIT}
      <button class="more" onclick={() => (showAll = !showAll)}>{showAll ? "Show fewer" : `Show all ${items.length}`}</button>
    {/if}
  </section>
{/if}

<style>
  .box {
    width: 100%;
    margin-top: 24px;
    padding: 12px 14px 14px;
    border-radius: 12px;
    background: var(--surface);
    box-shadow: var(--card-shadow);
  }

  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 10px;
  }

  h2 {
    margin: 0;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    color: var(--secondary);
  }

  .count {
    margin-left: 4px;
    padding: 0 6px;
    border-radius: 8px;
    background: var(--hover);
  }

  header input {
    width: 160px;
    height: 24px;
    padding: 0 8px;
    border: none;
    border-radius: 6px;
    background: var(--hover);
    color: var(--text);
    font: 12px var(--font);
    outline: none;
    user-select: text;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(104px, 1fr));
    gap: 14px 12px;
  }

  .book {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: 4px;
    min-width: 0;
    padding: 4px;
    border-radius: 8px;
    text-align: left;
  }

  .book:hover:not(:disabled) {
    background: var(--hover);
  }

  .book.missing {
    opacity: 0.45;
  }

  .cover {
    position: relative;
    display: block;
    aspect-ratio: 3 / 4;
    border-radius: 4px;
    overflow: hidden;
    background: white;
    box-shadow: var(--page-shadow);
  }

  .cover img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: top;
  }

  .ph {
    display: grid;
    place-items: center;
    height: 100%;
    font: 700 28px var(--font);
    color: #3a55e8;
    background: linear-gradient(160deg, #e8eeff, #d5dcff);
  }

  .progress {
    position: absolute;
    left: 0;
    bottom: 0;
    height: 4px;
    border-radius: 0 2px 2px 0;
    background: var(--accent);
  }

  .title {
    font-size: 12px;
    font-weight: 500;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .meta {
    font-size: 10.5px;
    color: var(--secondary);
  }

  .more {
    margin-top: 10px;
    font-size: 12px;
    color: var(--accent);
  }
</style>
