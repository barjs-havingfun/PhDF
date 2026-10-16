<script lang="ts">
  // "Where was I?": shown once when a document is reopened — where you are, when you were last
  // here, your latest highlight and an open parked thought.
  import { onMount } from "svelte";
  import { api, type Annotation } from "./api";
  import Icon from "./Icon.svelte";
  import type { Tab } from "./tab.svelte";

  let { tab, topInset }: { tab: Tab; topInset: number } = $props();

  let lastMark = $state<Annotation | null>(null);
  let parked = $state<string | null>(null);

  function ago(unix: number) {
    const days = Math.floor((Date.now() / 1000 - unix) / 86400);
    if (days <= 0) return "earlier today";
    if (days === 1) return "yesterday";
    if (days < 30) return `${days} days ago`;
    const months = Math.round(days / 30);
    return `${months} month${months > 1 ? "s" : ""} ago`;
  }

  onMount(() => {
    (async () => {
      await tab.loadAnnotations();
      const marks = (tab.annotations ?? []).filter((a) => a.kind !== "other");
      // PDF dates sort as strings ("D:YYYYMMDDHHmmSS…"); fall back to the last one in the list.
      lastMark = [...marks].sort((a, b) => (a.modified ?? "").localeCompare(b.modified ?? "")).at(-1) ?? null;
      const list = await (await api()).parking_list(tab.path);
      parked = list.items.filter((i) => !i.done).at(-1)?.thought ?? null;
    })();
    const timer = setTimeout(() => (tab.welcomeBack = false), 6000);
    return () => clearTimeout(timer);
  });

  function goToMark() {
    if (lastMark) tab.reveal(lastMark.id);
    tab.welcomeBack = false;
  }
</script>

<aside class="card" style="top:{topInset + 12}px" aria-label="Where was I?">
  <header>
    <span class="title">Welcome back</span>
    <button class="x" onclick={() => (tab.welcomeBack = false)} aria-label="Dismiss"><Icon name="close" size={12} /></button>
  </header>
  <p>
    You're on <b>page {tab.page + 1}</b> of {tab.pageCount}{#if tab.doc.lastOpened}
      · last read {ago(tab.doc.lastOpened)}{/if}.
  </p>
  {#if lastMark}
    <button class="row" onclick={goToMark} title="Go to it">
      <span class="bar" style="--c:{lastMark.color}"></span>
      <span class="what">
        <small>Latest highlight · p. {lastMark.page + 1}</small>
        {lastMark.quote || lastMark.contents || "Drawing"}
      </span>
    </button>
  {/if}
  {#if parked}
    <p class="parked"><Icon name="park" size={13} /> Parked: {parked}</p>
  {/if}
</aside>

<style>
  .card {
    position: absolute;
    left: 16px;
    z-index: 7;
    width: 290px;
    padding: 10px 12px;
    border-radius: 16px;
    background: var(--popover-solid);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 10px 30px rgb(0 0 0 / 0.22);
    animation: slide 0.25s ease-out;
    font-size: 12.5px;
  }

  @keyframes slide {
    from {
      opacity: 0;
      transform: translateY(-6px);
    }
  }

  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .title {
    font-weight: 600;
    color: var(--accent);
  }

  .x {
    display: grid;
    place-items: center;
    width: 20px;
    height: 20px;
    border-radius: 6px;
    color: var(--secondary);
  }

  .x:hover {
    background: var(--hover);
  }

  p {
    margin: 4px 0;
  }

  .row {
    display: flex;
    gap: 8px;
    width: 100%;
    margin-top: 6px;
    padding: 6px;
    border-radius: 10px;
    text-align: left;
    background: var(--hover);
  }

  .row:hover {
    box-shadow: inset 0 0 0 1px var(--accent);
  }

  .bar {
    flex: none;
    width: 4px;
    border-radius: 2px;
    background: var(--c);
  }

  .what {
    display: -webkit-box;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
    font-style: italic;
  }

  small {
    display: block;
    font-style: normal;
    color: var(--secondary);
    font-size: 11px;
  }

  .parked {
    display: flex;
    gap: 6px;
    align-items: center;
    color: var(--secondary);
    font-size: 12px;
  }
</style>
