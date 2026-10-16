<script lang="ts">
  // Parking lot: jot down a stray thought (Enter) and get straight back to reading.
  import { onMount } from "svelte";
  import { api, type ParkedItem as Item } from "../api";
  import Icon from "../Icon.svelte";
  import { notify } from "../notify.svelte";

  interface Props {
    source: string | null; // e.g. "Film Art, p. 214"
    document: string | null; // the PDF / note being read; its list lives next to it
    onclose: () => void;
    onparked: () => void;
    onopen: () => void; // show the whole list (Parking tab beside the note, or as a tab)
  }

  let { source, document, onclose, onparked, onopen }: Props = $props();

  let input = $state<HTMLInputElement>();
  let text = $state("");
  let items = $state<Item[]>([]);
  let path = $state("");

  async function refresh() {
    const list = await (await api()).parking_list(document);
    path = list.path;
    items = list.items.filter((i) => !i.done).reverse();
  }

  async function park() {
    const thought = text.trim();
    if (!thought) return onclose();
    await (await api()).parking_add(thought, source, document);
    onparked();
    text = "";
    notify.show({ text: "Parked. Back to reading." }, 2000);
    onclose(); // straight back to the page
  }

  async function done(item: Item) {
    await (await api()).parking_done(item.line, item.text, true, document);
    await refresh();
    onparked();
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault();
      park();
    }
  }

  onMount(() => {
    input?.focus();
    refresh();
  });
</script>

<svelte:window onkeydown={(e) => e.key === "Escape" && onclose()} />

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={onclose}></div>
<div class="panel" role="dialog" aria-label="Parking lot">
  <div class="field">
    <Icon name="park" size={16} />
    <input
      bind:this={input}
      bind:value={text}
      onkeydown={onKey}
      placeholder="Park a thought… (Enter)"
      spellcheck="false"
    />
  </div>
  {#if source}<p class="source">Will note: {source}</p>{/if}

  {#if items.length}
    <ul>
      {#each items.slice(0, 8) as item (item.line)}
        <li>
          <button class="tick" title="Done" onclick={() => done(item)} aria-label="Mark done"></button>
          <span class="text">
            {item.thought}
            {#if item.meta}<small>{item.meta}</small>{/if}
          </span>
        </li>
      {/each}
    </ul>
  {/if}
  <div class="foot">
    <span class="where" title={path}>{path.split(/[\\/]/).pop()} · {document ? "next to the document" : "PhDF's folder"}</span>
    <button class="link" onclick={() => (onopen(), onclose())}>Show All</button>
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 44;
  }

  .panel {
    position: fixed;
    top: 70px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 45;
    width: min(460px, 92vw);
    padding: 10px;
    border-radius: 14px;
    background: var(--popover);
    backdrop-filter: saturate(180%) blur(30px);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 16px 44px rgb(0 0 0 / 0.28);
    animation: drop 0.14s ease-out;
  }

  @keyframes drop {
    from {
      opacity: 0;
      transform: translate(-50%, -6px);
    }
  }

  .field {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 0 10px;
    height: 38px;
    border-radius: 9px;
    background: var(--hover);
    color: var(--secondary);
  }

  .field input {
    flex: 1;
    border: none;
    outline: none;
    background: none;
    font: 15px var(--font);
    color: var(--text);
    user-select: text;
  }

  .source {
    margin: 6px 4px 0;
    font-size: 11px;
    color: var(--tertiary);
  }

  ul {
    list-style: none;
    margin: 8px 0 0;
    padding: 0;
    max-height: 260px;
    overflow: auto;
  }

  li {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 5px 4px;
    border-top: 0.5px solid var(--separator);
  }

  .tick {
    flex: none;
    width: 16px;
    height: 16px;
    margin-top: 2px;
    border-radius: 50%;
    box-shadow: inset 0 0 0 1.5px var(--tertiary);
  }

  .tick:hover {
    box-shadow: inset 0 0 0 1.5px var(--accent);
    background: rgb(0 122 255 / 0.12);
  }

  .text {
    display: flex;
    flex-direction: column;
    font-size: 13px;
    user-select: text;
  }

  small {
    font-size: 11px;
    color: var(--secondary);
  }

  .foot {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 8px;
    font-size: 11px;
    color: var(--secondary);
  }

  .link {
    color: var(--accent);
    font-size: 11px;
  }
</style>
