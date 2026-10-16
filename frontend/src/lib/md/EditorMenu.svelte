<script lang="ts" module>
  import type { EditorView } from "@codemirror/view";
  import { askAi } from "../ai/terminal.svelte";

  export const AI_PRESETS = [
    { label: "Explain", prompt: "Explain this passage clearly." },
    { label: "Summarize", prompt: "Summarize this passage in a few bullet points." },
    { label: "Translate to Turkish", prompt: "Translate this passage into Turkish." },
  ];

  /** Ask AI about a note, like on PDF text: the selection as a quote, or the whole note file.
   *  `prompt` null = "My own question…" (typed, not sent). */
  export function askAboutNote(view: EditorView, path: string, prompt: string | null) {
    const { from, to } = view.state.selection.main;
    const name = path.split(/[\\/]/).pop();
    const selected = view.state.sliceDoc(from, to).trim();
    const context = selected
      ? `From the note “${name}” (file: ${path}):\n${selected.split("\n").map((l) => `> ${l}`).join("\n")}\n\n`
      : `Read the note file "${path}".\n\n`;
    const text = context + (prompt ?? "");
    askAi(text, prompt !== null, path.replace(/[\\/][^\\/]*$/, ""), null);
  }
</script>

<script lang="ts">
  // Right-click menu of the note editor: clipboard, format, link, paragraph style, insert, Ask AI.
  import { kbd } from "../platform";
  import * as f from "./format";
  import { BLOCKS, INLINE, INSERTS, type Block, type Inline, type Insert } from "./format";

  interface Props {
    view: EditorView;
    path: string;
    block: Block;
    x: number;
    y: number;
    onclose: () => void;
  }

  let { view, path, block, x, y, onclose }: Props = $props();

  let menu = $state<HTMLDivElement>();
  const pos = $derived.by(() => {
    const w = menu?.offsetWidth ?? 220;
    const h = menu?.offsetHeight ?? 300;
    return `left:${Math.min(x, innerWidth - w - 8)}px;top:${Math.min(y, innerHeight - h - 8)}px`;
  });
  // Submenus open to the left near the right edge of the window.
  const flip = $derived(x > innerWidth - 440);
  const hasSelection = $derived(!view.state.selection.main.empty);

  function act(run: (v: EditorView) => unknown) {
    onclose();
    run(view);
  }
</script>

<svelte:window onkeydown={(e) => e.key === "Escape" && onclose()} />

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={onclose} oncontextmenu={(e) => (e.preventDefault(), onclose())}></div>
<div class="menu" class:flip role="menu" tabindex="-1" bind:this={menu} style={pos} onmousedown={(e) => e.preventDefault()}>
  <button role="menuitem" disabled={!hasSelection} onclick={() => act(f.cut)}>Cut <span class="key">{kbd("Ctrl+X")}</span></button>
  <button role="menuitem" disabled={!hasSelection} onclick={() => act(f.copy)}>Copy <span class="key">{kbd("Ctrl+C")}</span></button>
  <button role="menuitem" onclick={() => act((v) => f.paste(v))}>Paste <span class="key">{kbd("Ctrl+V")}</span></button>
  <button role="menuitem" onclick={() => act((v) => f.paste(v, true))}>Paste as Plain Text</button>
  <div class="sep"></div>
  <div class="sub">
    <button role="menuitem" aria-haspopup="menu">Format <span class="key">›</span></button>
    <div class="menu inner" role="menu">
      {#each Object.entries(INLINE) as [kind, m]}
        <button role="menuitem" onclick={() => act((v) => f.toggleInline(v, kind as Inline))}>
          {m.label}{#if m.key}<span class="key">{kbd(m.key)}</span>{/if}
        </button>
      {/each}
      <div class="sep"></div>
      <button role="menuitem" onclick={() => act(f.clearFormatting)}>Clear Formatting</button>
    </div>
  </div>
  <button role="menuitem" onclick={() => act(f.insertLink)}>Link</button>
  <div class="sub">
    <button role="menuitem" aria-haspopup="menu">Paragraph <span class="key">›</span></button>
    <div class="menu inner" role="menu">
      {#each Object.entries(BLOCKS) as [kind, label]}
        <button role="menuitemradio" aria-checked={block === kind} onclick={() => act((v) => f.setBlock(v, kind as Block))}>{label}</button>
      {/each}
    </div>
  </div>
  <div class="sub">
    <button role="menuitem" aria-haspopup="menu">Insert <span class="key">›</span></button>
    <div class="menu inner" role="menu">
      {#each Object.entries(INSERTS) as [kind, label]}
        <button role="menuitem" onclick={() => act((v) => f.insertBlock(v, kind as Insert))}>{label}</button>
      {/each}
    </div>
  </div>
  <div class="sep"></div>
  <div class="sub">
    <button role="menuitem" aria-haspopup="menu">Ask AI {hasSelection ? "(selection)" : "(whole note)"} <span class="key">›</span></button>
    <div class="menu inner" role="menu">
      {#each AI_PRESETS as p}
        <button role="menuitem" onclick={() => act((v) => askAboutNote(v, path, p.prompt))}>{p.label}</button>
      {/each}
      <button role="menuitem" onclick={() => act((v) => askAboutNote(v, path, null))}>My Own Question…</button>
    </div>
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 40;
  }

  .menu {
    position: fixed;
    z-index: 41;
    min-width: 200px;
    padding: 5px;
    border-radius: 9px;
    background: var(--popover-solid);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 8px 28px rgb(0 0 0 / 0.22);
  }

  .sub {
    position: relative;
  }

  .menu.inner {
    position: absolute;
    top: -5px;
    left: calc(100% + 2px);
    display: none;
  }

  .flip .menu.inner {
    left: auto;
    right: calc(100% + 2px);
  }

  .sub:hover > .menu.inner,
  .sub:focus-within > .menu.inner {
    display: block;
  }

  button {
    position: relative;
    display: flex;
    justify-content: space-between;
    gap: 14px;
    width: 100%;
    padding: 3px 10px 3px 22px;
    border-radius: 5px;
    text-align: left;
    white-space: nowrap;
  }

  button[aria-checked="true"]::before {
    content: "✓";
    position: absolute;
    left: 7px;
  }

  button:hover:not(:disabled),
  .sub:hover > button {
    background: var(--accent);
    color: var(--accent-text);
  }

  button:disabled {
    opacity: 0.4;
  }

  .key {
    color: var(--tertiary);
  }

  button:hover .key,
  .sub:hover > button .key {
    color: inherit;
  }

  .sep {
    height: 0.5px;
    margin: 4px 6px;
    background: var(--separator);
  }
</style>
