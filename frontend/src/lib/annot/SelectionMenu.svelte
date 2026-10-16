<script lang="ts">
  // Appears over selected PDF text: highlight in a colour, underline, strike, note in MD, copy.
  import { kbd, copyText } from "../platform";
  import type { AnnotKind } from "../api";
  import Icon from "../Icon.svelte";
  import { api } from "../api";
  import { notify, ui } from "../notify.svelte";
  import { askAi } from "../ai/terminal.svelte";
  import { citation } from "../cite";
  import type { Tab } from "../tab.svelte";
  import type { TextSelection } from "../viewer/Viewer.svelte";
  import { COLORS, DEFAULT_COLOR } from "./colors";
  import Popover from "./Popover.svelte";

  interface Props {
    tab: Tab;
    sel: TextSelection;
    onclose: () => void;
  }

  let { tab, sel, onclose }: Props = $props();

  async function annotate(kind: AnnotKind, color: string) {
    const created = [];
    for (const [page, rects] of [...sel.byPage].sort((a, b) => a[0] - b[0])) {
      created.push(await tab.addAnnotation(page, kind, rects, color));
    }
    getSelection()?.removeAllRanges();
    onclose();
    return created;
  }

  async function noteInMd() {
    const [first] = await annotate("highlight", DEFAULT_COLOR);
    if (first) await tab.noteInMd(first);
  }

  async function toObsidian() {
    if (!(await (await api()).get_setting("obsidian.vault", null))) {
      onclose();
      notify.show({ text: "Choose your Obsidian vault first.", action: { label: "Settings", run: () => (ui.settingsOpen = true) } });
      return;
    }
    const [first] = await annotate("highlight", DEFAULT_COLOR);
    if (!first) return;
    try {
      const path = await tab.sendToObsidian(first);
      notify.show({
        text: `Sent to Obsidian · ${path.split(/[\\/]/).pop()}`,
        action: { label: "Open", run: async () => (await api()).open_in_obsidian(path) },
      });
    } catch (e) {
      notify.error(`Could not send to Obsidian: ${e}`);
    }
  }

  // Ask AI: presets are sent right away; "My own question…" only types the context.
  let aiMenu = $state(false);
  const PRESETS = [
    { label: "Explain", prompt: "Explain this passage clearly." },
    { label: "Summarize", prompt: "Summarize this passage in a few bullet points." },
    { label: "Translate to Turkish", prompt: "Translate this passage into Turkish." },
  ];

  function context() {
    const pages = [...sel.byPage.keys()].sort((a, b) => a - b).map((p) => p + 1);
    const where = pages.length > 1 ? `pages ${pages[0]}–${pages[pages.length - 1]}` : `page ${pages[0]}`;
    const quote = sel.text.trim().split("\n").map((l) => `> ${l}`).join("\n");
    return `From “${tab.title}” (${where}, file: ${tab.path}):\n${quote}\n\n`;
  }

  function ask(prompt: string | null) {
    const folder = tab.path.replace(/[\\/][^\\/]*$/, "");
    const text = context() + (prompt ?? "");
    getSelection()?.removeAllRanges();
    onclose();
    askAi(text, prompt !== null, folder, null);
  }

  async function copyCited() {
    await copyText(citation(tab, sel.text, [...sel.byPage.keys()]));
    notify.show({ text: "Copied with citation." }, 1800);
    onclose();
  }

  async function copy() {
    await copyText(sel.text);
    onclose();
  }
</script>

<Popover anchor={sel.box} width={422} {onclose}>
  <div class="row">
    {#if !tab.isBook}<!-- e-books keep no annotations: copy, cite and Ask AI only -->
    {#each COLORS as c}
      <button class="dot" style="--c:{c.value}" title="Highlight {c.name}" onclick={() => annotate("highlight", c.value)}
      ></button>
    {/each}
    <span class="sep"></span>
    <button class="icon" title="Underline" onclick={() => annotate("underline", "#ff375f")}>
      <Icon name="underline" size={16} />
    </button>
    <button class="icon" title="Strikethrough" onclick={() => annotate("strikeout", "#ff375f")}>
      <Icon name="strike" size={16} />
    </button>
    <span class="sep"></span>
    <button class="icon" title="Note in MD" onclick={noteInMd}><Icon name="mdnote" size={16} /></button>
    <button class="icon" title="Send to Obsidian" onclick={toObsidian}><Icon name="obsidian" size={16} /></button>
    {/if}
    <button class="icon" title="Copy" onclick={copy}><Icon name="copy" size={16} /></button>
    <button class="icon" title={kbd("Copy with citation (Ctrl+Shift+C)")} onclick={copyCited}><Icon name="quote" size={16} /></button>
    <button class="icon" class:on={aiMenu} title="Ask AI" onclick={() => (aiMenu = !aiMenu)}><Icon name="sparkle" size={16} /></button>
  </div>
  {#if aiMenu}
    <div class="ai-row">
      {#each PRESETS as p}
        <button class="ai-btn" onclick={() => ask(p.prompt)}>{p.label}</button>
      {/each}
      <button class="ai-btn own" onclick={() => ask(null)}>My own question…</button>
    </div>
  {/if}
</Popover>

<style>
  .row {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .dot {
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: var(--c);
    box-shadow: inset 0 0 0 1px rgb(0 0 0 / 0.12);
    transition: transform 0.1s;
  }

  .dot:hover {
    transform: scale(1.15);
  }

  .sep {
    width: 0.5px;
    height: 18px;
    margin: 0 3px;
    background: var(--separator);
  }

  .icon {
    display: grid;
    place-items: center;
    width: 28px;
    height: 26px;
    border-radius: 8px;
    color: var(--text);
  }

  .icon:hover,
  .icon.on {
    background: var(--hover);
  }

  .ai-row {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 6px;
    padding-top: 6px;
    border-top: 0.5px solid var(--separator);
  }

  .ai-btn {
    padding: 3px 9px;
    border-radius: 8px;
    font-size: 12px;
    background: var(--hover);
  }

  .ai-btn:hover {
    background: var(--accent);
    color: var(--accent-text);
  }

  .ai-btn.own {
    font-style: italic;
  }
</style>
