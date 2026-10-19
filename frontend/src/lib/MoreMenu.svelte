<script lang="ts">
  // The toolbar's ⋯ menu: document actions, the tools a narrow window folds away, Settings,
  // the beta note and the GitHub link.
  import type { FitMode } from "./api";
  import { grading } from "./grading/grading.svelte";
  import { ui } from "./notify.svelte";
  import { kbd } from "./platform";
  import type { MdTab, Tab } from "./tab.svelte";
  import { BETA_NOTE, openGithub } from "./updates";
  import type Viewer from "./viewer/Viewer.svelte";

  interface Props {
    active: Tab | null;
    note: MdTab | null;
    invert: boolean;
    viewer: () => Viewer | undefined;
    setFit: (mode: FitMode) => void;
    oninvert: () => void;
    onstopgrading: () => void;
    onexporthighlights: () => void;
    onexportmarkdown: (target: "file" | "vault") => void;
    oncopynote: () => void;
    onrecognize: () => void;
    onclose: () => void;
  }

  let {
    active, note, invert, viewer, setFit, oninvert, onstopgrading, onexporthighlights, onexportmarkdown, oncopynote,
    onrecognize, onclose,
  }: Props = $props(); // prettier-ignore

  /** Close the menu, then act. */
  const more = (run: () => void) => () => {
    onclose();
    run();
  };
</script>

  {#if active}
    {@const pdf = active}
    <div class="narrow-tools" class:book={pdf.isBook}>
      <button role="menuitemcheckbox" aria-checked={pdf.tool === "note"} onclick={() => (onclose(), (pdf.tool = pdf.tool === "note" ? "select" : "note"))}>Add Note</button>
      <button role="menuitemcheckbox" aria-checked={pdf.tool === "text"} onclick={() => (onclose(), (pdf.tool = pdf.tool === "text" ? "select" : "text"))}>Add Text</button>
      <button role="menuitemcheckbox" aria-checked={pdf.tool === "draw"} onclick={() => (onclose(), (pdf.tool = pdf.tool === "draw" ? "select" : "draw"))}>Draw</button>
      <button role="menuitemcheckbox" aria-checked={pdf.panelOpen} onclick={() => (onclose(), (pdf.panelOpen = !pdf.panelOpen))}>Annotations</button>
      <button role="menuitemcheckbox" aria-checked={pdf.mdOpen} onclick={() => (onclose(), pdf.toggleMd())}>Integrated .md Note</button>
      <div class="menu-sep"></div>
    </div>
    <div class="narrow-zoom">
      <button role="menuitem" onclick={() => viewer()?.zoomBy(1.2)}>Zoom In <span class="shortcut">{kbd("Ctrl++")}</span></button>
      <button role="menuitem" onclick={() => viewer()?.zoomBy(1 / 1.2)}>Zoom Out <span class="shortcut">{kbd("Ctrl+-")}</span></button>
      <button role="menuitemradio" aria-checked={pdf.fit === "width"} onclick={() => (onclose(), setFit("width"))}>Fit Width</button>
      <button role="menuitemradio" aria-checked={pdf.fit === "page"} onclick={() => (onclose(), setFit("page"))}>Fit Page</button>
      <button role="menuitemcheckbox" aria-checked={invert} onclick={() => (onclose(), oninvert())}>Dark Pages</button>
      <div class="menu-sep"></div>
    </div>
    {#if grading.session}
      {@const g = grading.session}
      <button role="menuitem" onclick={() => (onclose(), g.exportCsv())}>Export Grades as CSV…</button>
      <button role="menuitem" onclick={() => (onclose(), onstopgrading())}>Stop Grading</button>
      <div class="menu-sep"></div>
    {/if}
    <button role="menuitem" onclick={more(() => (ui.print = true))}>Print… <span class="shortcut">{kbd("Ctrl+P")}</span></button>
    <button role="menuitem" onclick={more(() => (ui.tools = { path: pdf.path }))}>PDF Tools… (rotate, reorder, split…)</button>
    <div class="menu-sep"></div>
    <button role="menuitem" onclick={more(onexporthighlights)}>Export Highlights to Note</button>
    <button role="menuitem" onclick={more(() => onexportmarkdown("file"))}>Export as Markdown…</button>
    <button role="menuitem" onclick={more(() => onexportmarkdown("vault"))}>Export to Obsidian Vault</button>
    <button role="menuitem" onclick={more(oncopynote)}>Copy Note to Obsidian</button>
    <div class="menu-sep"></div>
    <button role="menuitem" onclick={more(onrecognize)} disabled={!!active.ocrProgress}>Recognize Text (OCR)</button>
    <div class="menu-sep"></div>
  {:else if note}
    <button role="menuitem" onclick={more(oncopynote)}>Copy Note to Obsidian</button>
    <div class="menu-sep"></div>
  {/if}
  <button role="menuitem" onclick={() => (onclose(), (ui.settingsOpen = true))}>Settings…</button>
  <div class="menu-sep"></div>
  <div class="beta" role="note">
    <b>Beta version</b>
    <span>{BETA_NOTE.replace("Ctrl+S", kbd("Ctrl+S"))}</span>
  </div>
  <button role="menuitem" onclick={() => (onclose(), openGithub())}>PhDF on GitHub</button>

<style>
  /* Shown in the menu only when the toolbar is too narrow for those buttons. */
  .narrow-tools,
  .narrow-zoom {
    display: none;
  }

  /* E-books: no annotation tools (only the note stays). */
  .narrow-tools.book button:not(:nth-child(5)) {
    display: none;
  }

  @container toolbar (max-width: 1020px) {
    .narrow-tools {
      display: block;
    }
  }

  @container toolbar (max-width: 860px) {
    .narrow-zoom {
      display: block;
    }
  }

  .beta {
    display: flex;
    flex-direction: column;
    gap: 2px;
    max-width: 240px;
    margin: 2px 4px 4px;
    padding: 7px 9px;
    border-radius: 8px;
    font-size: 12px;
    line-height: 1.35;
    background: rgb(255 159 10 / 0.16);
    color: var(--text);
  }

  .beta b {
    color: rgb(201 112 0);
  }
</style>
