<script lang="ts" module>
  export type MdSidebarMode = "contents" | "files";
</script>

<script lang="ts">
  // Left sidebar for a standalone Markdown note: its headings, or the other notes in its folder.
  import { api, type MdFile } from "../api";
  import Icon from "../Icon.svelte";
  import type { MdDoc } from "../md.svelte";

  interface Props {
    md: MdDoc;
    mode: MdSidebarMode;
    onmode: (mode: MdSidebarMode) => void;
    onopen: (path: string) => void;
  }

  let { md, mode, onmode, onopen }: Props = $props();

  /** Headings (ATX `#` style), skipping fenced code blocks. */
  const headings = $derived.by(() => {
    const out: { level: number; text: string; pos: number }[] = [];
    let pos = 0;
    let fence = false;
    for (const line of md.text.split("\n")) {
      if (/^\s*(```|~~~)/.test(line)) fence = !fence;
      const m = !fence && /^(#{1,6})\s+(.+?)\s*#*\s*$/.exec(line);
      if (m) out.push({ level: m[1].length, text: m[2].replace(/[*_`=]/g, ""), pos });
      pos += line.length + 1;
    }
    return out;
  });
  const top = $derived(Math.min(6, ...headings.map((h) => h.level)));

  const folder = $derived(md.path.replace(/[\\/][^\\/]*$/, ""));
  let files = $state<MdFile[] | null>(null);
  $effect(() => {
    if (mode !== "files") return;
    const dir = folder;
    files = null;
    api()
      .then((py) => py.md_files(dir))
      .then((list) => dir === folder && (files = list));
  });

  const same = (a: string, b: string) => a.replace(/\\/g, "/").toLowerCase() === b.replace(/\\/g, "/").toLowerCase();
</script>

<aside>
  <div class="segmented" role="tablist">
    <button role="tab" aria-selected={mode === "contents"} onclick={() => onmode("contents")}>Contents</button>
    <button role="tab" aria-selected={mode === "files"} onclick={() => onmode("files")}>Files</button>
  </div>

  <div class="list">
    {#if mode === "contents"}
      {#if !headings.length}
        <p class="empty">No headings yet. Start a line with <code>#</code> to add one.</p>
      {/if}
      {#each headings as h, i (i)}
        <button
          class="row"
          style="padding-left:{8 + (h.level - top) * 14}px"
          class:h1={h.level === top}
          title={h.text}
          onclick={() => (md.reveal = { pos: h.pos, nonce: Date.now(), heading: i })}
        >
          {h.text}
        </button>
      {/each}
    {:else}
      <p class="folder" title={folder}><Icon name="folder" size={14} /> {folder.split(/[\\/]/).pop()}</p>
      {#if files === null}
        <p class="empty">Loading…</p>
      {:else if !files.length}
        <p class="empty">No other notes in this folder.</p>
      {/if}
      {#each files ?? [] as f (f.path)}
        <button class="row file" class:current={same(f.path, md.path)} title={f.path} onclick={() => onopen(f.path)}>
          <Icon name="mdnote" size={14} />
          <span class="name">{f.name.replace(/\.md$/i, "")}</span>
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
    border-radius: 9px;
    background: var(--hover);
  }

  .segmented button {
    flex: 1;
    padding: 2px 0;
    border-radius: 6px;
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

  .empty {
    margin: 16px 8px;
    color: var(--secondary);
  }

  .folder {
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 6px 4px 8px;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .row {
    display: flex;
    align-items: center;
    gap: 7px;
    width: 100%;
    padding: 4px 8px;
    border-radius: var(--radius-s);
    text-align: left;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .row:hover {
    background: var(--hover);
  }

  .row.h1 {
    font-weight: 600;
  }

  .row.current {
    background: var(--selection);
  }

  .file :global(svg) {
    flex: none;
    color: var(--secondary);
  }

  .name {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
  }
</style>
