<script lang="ts" module>
  export interface Command {
    id: string;
    title: string;
    group: string;
    keys?: string;
    run: () => void;
  }
</script>

<script lang="ts">
  // Ctrl+K: type to find any action, recent document or page.
  import { onMount } from "svelte";
  import Icon from "./Icon.svelte";

  interface Props {
    commands: Command[];
    /** Extra entries computed from the query (e.g. "Go to page 12", "Search for …"). */
    dynamic: (query: string) => Command[];
    onclose: () => void;
  }

  let { commands, dynamic, onclose }: Props = $props();

  let query = $state("");
  let index = $state(0);
  let input: HTMLInputElement;
  let list = $state<HTMLElement>();

  function score(c: Command, words: string[]): number {
    const title = c.title.toLowerCase();
    const hay = `${title} ${c.group.toLowerCase()}`;
    if (!words.every((w) => hay.includes(w))) return -1;
    return (title.startsWith(words[0] ?? "") ? 10 : 0) + (title.includes(words.join(" ")) ? 5 : 0) - title.length / 100;
  }

  const results = $derived.by(() => {
    const words = query.toLowerCase().split(/\s+/).filter(Boolean);
    // "Go to page N" leads; a matching command beats "Search for …", which comes last.
    const extra = dynamic(query.trim());
    const first = extra.filter((c) => c.group !== "Search");
    const last = extra.filter((c) => c.group === "Search");
    if (!words.length) return [...first, ...commands].slice(0, 60);
    const ranked = commands
      .map((c) => ({ c, s: score(c, words) }))
      .filter((r) => r.s >= 0)
      .sort((a, b) => b.s - a.s)
      .map((r) => r.c);
    return [...first, ...ranked, ...last].slice(0, 60);
  });

  $effect(() => {
    void query;
    index = 0;
  });

  $effect(() => {
    list?.querySelector(`[data-i="${index}"]`)?.scrollIntoView({ block: "nearest" });
  });

  function run(c: Command | undefined) {
    if (!c) return;
    onclose();
    queueMicrotask(c.run);
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      index = Math.min(index + 1, results.length - 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      index = Math.max(index - 1, 0);
    } else if (e.key === "Enter") {
      e.preventDefault();
      run(results[index]);
    } else if (e.key === "Escape") {
      e.preventDefault();
      onclose();
    }
  }

  onMount(() => input.focus());
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={(e) => e.target === e.currentTarget && onclose()}>
  <div class="palette" role="dialog" aria-label="Command palette">
    <div class="field">
      <Icon name="search" size={16} />
      <input
        bind:this={input}
        bind:value={query}
        onkeydown={onKey}
        placeholder="Type a command, a document, or a page number…"
        spellcheck="false"
      />
      <span class="esc">Esc</span>
    </div>
    <ul bind:this={list} role="listbox">
      {#each results as c, i (c.id)}
        {#if i === 0 || results[i - 1].group !== c.group}
          <li class="group" role="presentation">{c.group}</li>
        {/if}
        <li
          data-i={i}
          role="option"
          aria-selected={i === index}
          class:on={i === index}
          onclick={() => run(c)}
          onmousemove={() => (index = i)}
        >
          <span class="t">{c.title}</span>
          {#if c.keys}<span class="keys">{c.keys}</span>{/if}
        </li>
      {:else}
        <li class="empty">Nothing found.</li>
      {/each}
    </ul>
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 80;
    display: grid;
    place-items: start center;
    padding-top: 12vh;
    background: rgb(0 0 0 / 0.18);
  }

  .palette {
    width: min(620px, 92vw);
    border-radius: 14px;
    background: var(--popover-solid);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 24px 60px rgb(0 0 0 / 0.35);
    overflow: hidden;
  }

  .field {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 14px;
    border-bottom: 0.5px solid var(--separator);
    color: var(--secondary);
  }

  input {
    flex: 1;
    border: none;
    outline: none;
    background: none;
    color: var(--text);
    font: 16px var(--font);
    user-select: text;
  }

  .esc {
    font-size: 11px;
    color: var(--tertiary);
  }

  ul {
    list-style: none;
    margin: 0;
    padding: 6px;
    max-height: 50vh;
    overflow: auto;
  }

  li {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    padding: 6px 10px;
    border-radius: 7px;
  }

  li.on {
    background: var(--accent);
    color: var(--accent-text);
  }

  li.group {
    padding: 8px 10px 2px;
    font-size: 10.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    color: var(--secondary);
  }

  .t {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .keys {
    flex: none;
    font-size: 11px;
    color: var(--tertiary);
  }

  li.on .keys {
    color: inherit;
    opacity: 0.8;
  }

  .empty {
    color: var(--secondary);
  }
</style>
