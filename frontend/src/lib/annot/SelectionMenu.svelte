<script lang="ts">
  // Appears over selected PDF text: highlight in a colour, underline, strike, note in MD, copy.
  import type { AnnotKind } from "../api";
  import Icon from "../Icon.svelte";
  import { api } from "../api";
  import { notify, ui } from "../notify.svelte";
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

  async function copy() {
    await navigator.clipboard.writeText(sel.text);
    onclose();
  }
</script>

<Popover anchor={sel.box} width={358} {onclose}>
  <div class="row">
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
    <button class="icon" title="Copy" onclick={copy}><Icon name="copy" size={16} /></button>
  </div>
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
    border-radius: 6px;
    color: var(--text);
  }

  .icon:hover {
    background: var(--hover);
  }
</style>
