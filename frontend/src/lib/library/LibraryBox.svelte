<script lang="ts">
  // Library: every document PhDF has opened — cover, progress, time spent reading.
  import { onMount } from "svelte";
  import { api, type LibraryItem } from "../api";
  import { notify } from "../notify.svelte";
  import { docKind, KINDS, type DocKind } from "./kinds";

  let { onopenpath }: { onopenpath: (path: string) => void } = $props();

  let items = $state<LibraryItem[]>([]);
  let covers = $state<Record<string, string | null>>({});
  let filter = $state("");
  let showAll = $state(false);
  let kind = $state<DocKind | "all">("all"); // the type buttons; remembered

  const LIMIT = 12;

  onMount(async () => {
    const py = await api();
    items = await py.library();
    const saved = await py.get_setting<string>(KIND_KEY, "all");
    if (saved && (saved === "all" || saved in KINDS)) kind = saved as DocKind | "all";
    // Covers come a few at a time, first ones first (cached after the first time).
    const queue = items.slice(0, 40);
    const worker = async () => {
      for (let item = queue.shift(); item; item = queue.shift()) {
        covers[item.docId] = await py.library_cover(item.docId, item.path);
      }
    };
    await Promise.all(Array.from({ length: 4 }, worker));
  });

  const KIND_KEY = "library.kind";
  const ofKind = $derived(kind === "all" ? items : items.filter((i) => docKind(i.path) === kind));
  const shown = $derived.by(() => {
    const q = filter.trim().toLowerCase();
    const list = q ? ofKind.filter((i) => i.title.toLowerCase().includes(q) || i.path.toLowerCase().includes(q)) : ofKind;
    return showAll || q ? list : list.slice(0, LIMIT);
  });

  async function setKind(k: DocKind | "all") {
    kind = k;
    await (await api()).set_setting(KIND_KEY, k);
  }

  async function remove(item: LibraryItem) {
    await (await api()).library_remove(item.docId);
    items = items.filter((i) => i.docId !== item.docId);
    notify.show({ text: `“${item.title}” removed from the Library. The file was not touched.` }, 2500);
  }

  async function relink(item: LibraryItem) {
    const r = await (await api()).library_relink(item.docId);
    if (r.ok && r.path) {
      items = items.map((i) => (i.docId === item.docId ? { ...i, path: r.path!, exists: true } : i));
      covers[item.docId] = await (await api()).library_cover(item.docId, r.path);
    } else if (r.reason === "different") {
      notify.error("That is a different file. Choose the same PDF (moved or renamed), not an edited copy.");
    }
  }

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
      <div class="kinds" role="group" aria-label="Show">
        {#each [["all", "All"], ...Object.entries(KINDS)] as [k, label]}
          <button class:on={kind === k} aria-pressed={kind === k} onclick={() => setKind(k as DocKind | "all")}>{label}</button>
        {/each}
      </div>
      <input bind:value={filter} placeholder="Filter" spellcheck="false" />
    </header>
    <div class="grid">
      {#each shown as item (item.docId)}
        <div class="slot">
        <button class="book" class:missing={!item.exists} onclick={() => (item.exists ? onopenpath(item.path) : relink(item))} title={item.exists ? item.path : `${item.path}
Missing: click to find the file`}>
          <span class="cover">
            {#if covers[item.docId]}
              <img src={covers[item.docId]} alt="" />
            {:else}
              <span class="ph">{item.title.slice(0, 1)}</span>
            {/if}
            <span class="tag">{KINDS[docKind(item.path)]}</span>
            <span class="progress" style="width:{progress(item)}%"></span>
          </span>
          <span class="title">{item.title}</span>
          <span class="meta">{item.exists ? `${progress(item)}% · ${time(item.seconds)}` : "Missing: find file…"}</span>
        </button>
        <button class="remove" title="Remove from Library (the file stays)" aria-label="Remove from Library" onclick={() => remove(item)}>×</button>
        </div>
      {/each}
    </div>
    {#if !filter && ofKind.length > LIMIT}
      <button class="more" onclick={() => (showAll = !showAll)}>{showAll ? "Show fewer" : `Show all ${ofKind.length}`}</button>
    {/if}
    {#if !shown.length}
      <p class="none">No {kind === "all" ? "documents" : `${KINDS[kind]} files`} here.</p>
    {/if}
  </section>
{/if}

<style>
  .box {
    width: 100%;
    margin-top: 24px;
    padding: 12px 14px 14px;
    border-radius: 16px;
    background: var(--surface);
    box-shadow: var(--card-shadow);
  }

  header {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
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
    border-radius: 10px;
    background: var(--hover);
  }

  header input {
    width: 160px;
    height: 24px;
    padding: 0 8px;
    border: none;
    border-radius: 8px;
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
    border-radius: 10px;
    text-align: left;
  }

  .book:hover:not(:disabled) {
    background: var(--hover);
  }

  .book.missing {
    opacity: 0.55;
  }

  .slot {
    position: relative;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }

  .remove {
    position: absolute;
    top: 0;
    right: 0;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    font-size: 15px;
    line-height: 1;
    color: white;
    background: rgb(0 0 0 / 0.55);
    opacity: 0;
    transition: opacity 0.12s;
  }

  .slot:hover .remove,
  .remove:focus-visible {
    opacity: 1;
  }

  .cover {
    position: relative;
    display: block;
    aspect-ratio: 3 / 4;
    border-radius: 5px;
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

  .kinds {
    display: flex;
    gap: 2px;
    margin-left: auto;
    padding: 2px;
    border-radius: 8px;
    background: var(--hover);
  }

  .kinds button {
    padding: 1px 8px;
    border-radius: 6px;
    font-size: 11px;
    color: var(--secondary);
  }

  .kinds button.on {
    background: var(--surface);
    color: var(--text);
    box-shadow: 0 0 0 0.5px var(--separator);
  }

  .tag {
    position: absolute;
    right: 4px;
    bottom: 8px;
    padding: 0 4px;
    border-radius: 4px;
    background: rgb(0 0 0 / 0.62);
    color: white;
    font: 600 9px/14px var(--font);
    letter-spacing: 0.3px;
  }

  .none {
    margin: 4px 0 0;
    font-size: 12px;
    color: var(--secondary);
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
