<script lang="ts">
  // Print: choose pages, then the system print dialog. Pages are printed as they look in PhDF
  // (with unsaved annotations), rendered at 150 DPI into a print-only layer (`#phdf-print`).
  // macOS's web view has no print dialog, so there the PDF opens in Preview instead.
  import { untrack } from "svelte";
  import { api, pageImageUrl } from "./api";
  import { notify } from "./notify.svelte";
  import { isMac } from "./platform";
  import type { Tab } from "./tab.svelte";

  let { tab, onclose }: { tab: Tab; onclose: () => void } = $props();

  let which = $state<"all" | "current" | "range">("all");
  // The sheet opens for one tab: start values only.
  let from = $state(untrack(() => tab.page + 1));
  let to = $state(untrack(() => tab.pageCount));
  let preparing = $state<{ done: number; total: number } | null>(null);

  const MAX_PAGES = 500; // all of them are decoded into memory before the dialog opens

  function pages(): number[] {
    if (which === "current") return [tab.page];
    const [a, b] = which === "all" ? [1, tab.pageCount] : [from, to];
    const first = Math.max(1, Math.min(a, b));
    const last = Math.min(tab.pageCount, Math.max(a, b));
    return Array.from({ length: last - first + 1 }, (_, i) => first - 1 + i);
  }

  async function print() {
    if (isMac) {
      if (tab.dirty) notify.show({ text: "Save first (⌘S): Preview prints the file as it is on disk." });
      (await api()).open_in_default_app(tab.path);
      onclose();
      return;
    }
    const list = pages();
    if (list.length > MAX_PAGES) {
      notify.error(`Print at most ${MAX_PAGES} pages at a time (choose a page range).`);
      return;
    }
    const layer = document.createElement("div");
    layer.id = "phdf-print";
    document.body.appendChild(layer);
    preparing = { done: 0, total: list.length };
    try {
      await Promise.all(
        list.map(async (page) => {
          const img = new Image();
          img.src = pageImageUrl(tab.doc.docId, page, 150 / 72, undefined, tab.revs[page] ?? 0);
          layer.appendChild(img);
          await img.decode().catch(() => {});
          preparing!.done++;
        }),
      );
      // Pages are appended as they were requested, so they stay in order.
      const cleanup = () => layer.remove();
      addEventListener("afterprint", cleanup, { once: true });
      preparing = null;
      onclose();
      setTimeout(() => window.print(), 50);
    } catch (e) {
      layer.remove();
      preparing = null;
      notify.error(`Could not print: ${e}`);
    }
  }
</script>

<svelte:window onkeydown={(e) => e.key === "Escape" && !preparing && (e.stopPropagation(), onclose())} />

<div class="sheet-backdrop">
  <div class="sheet" role="dialog" aria-labelledby="print-title">
    <h2 id="print-title">Print “{tab.title}”</h2>
    {#if preparing}
      <p>Preparing page {preparing.done} of {preparing.total}…</p>
    {:else}
      <label><input type="radio" bind:group={which} value="all" /> All pages ({tab.pageCount})</label>
      <label><input type="radio" bind:group={which} value="current" /> Current page ({tab.page + 1})</label>
      <label class="range">
        <input type="radio" bind:group={which} value="range" /> Pages
        <input type="number" min="1" max={tab.pageCount} bind:value={from} onfocus={() => (which = "range")} />
        to
        <input type="number" min="1" max={tab.pageCount} bind:value={to} onfocus={() => (which = "range")} />
      </label>
      {#if isMac}
        <p class="hint">The PDF opens in Preview; print it from there.</p>
      {:else}
        <p class="hint">Annotations print as you see them, saved or not.</p>
      {/if}
      <div class="actions">
        <button class="plain" onclick={onclose}>Cancel</button>
        <button class="default" onclick={print}>Print…</button>
      </div>
    {/if}
  </div>
</div>

<style>
  .sheet-backdrop {
    position: fixed;
    inset: 0;
    z-index: 60;
    display: grid;
    place-items: start center;
    padding-top: 12vh;
    background: rgb(0 0 0 / 0.2);
  }

  .sheet {
    width: 340px;
    padding: 18px 20px;
    border-radius: 14px;
    background: var(--popover);
    backdrop-filter: saturate(180%) blur(24px);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 16px 48px rgb(0 0 0 / 0.3);
  }

  h2 {
    margin: 0 0 12px;
    font-size: 14px;
  }

  label {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 6px 0;
  }

  .range input[type="number"] {
    width: 64px;
    padding: 3px 6px;
    border: 1px solid var(--separator);
    border-radius: 6px;
    background: var(--surface);
    color: var(--text);
    font: inherit;
  }

  .hint {
    margin: 10px 0 0;
    font-size: 12px;
    color: var(--secondary);
  }

  .actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 16px;
  }

  .actions button {
    padding: 5px 14px;
    border-radius: 8px;
  }

  .plain {
    background: var(--hover);
  }

  .default {
    background: var(--accent);
    color: var(--accent-text);
  }
</style>
