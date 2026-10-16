<script lang="ts">
  // Equation → LaTeX, step 2: shows the drawn area with OK, waits for the AI, then shows the typeset equation and its
  // editable LaTeX with Insert (at the cursor in the side note) and Copy.
  import "katex/dist/katex.min.css";
  import Icon from "../Icon.svelte";
  import { notify } from "../notify.svelte";
  import { copyText } from "../platform";
  import type { Tab } from "../tab.svelte";
  import { pageImageUrl } from "../api";
  import { cancelEquation, confirmEquation, insertEquation } from "./equation.svelte";
  import { agentLabel, term } from "./terminal.svelte";

  let { tab }: { tab: Tab } = $props();

  const job = $derived(tab.equation!);
  let latex = $state("");
  let katex = $state<typeof import("katex").default | null>(null);
  import("katex").then((m) => (katex = m.default));

  // Take the AI's answer once; after that the text is the user's.
  $effect(() => {
    if (job.status === "done" && !latex) latex = job.latex;
  });

  const rendered = $derived.by(() => {
    if (!katex || !latex.trim()) return "";
    try {
      return katex.renderToString(latex, { displayMode: true, throwOnError: true, output: "html" });
    } catch (e) {
      return `<span class="err">${String((e as Error).message).replace(/[<&]/g, "")}</span>`;
    }
  });

  async function copy() {
    await copyText(latex);
    notify.show({ text: "LaTeX copied." }, 1500);
  }
</script>

<svelte:window onkeydown={(e) => e.key === "Escape" && cancelEquation(tab)} />

<div class="box" role="dialog" aria-label="Equation to LaTeX">
  <div class="head">
    <Icon name="sparkle" size={14} />
    <span class="title">Equation → LaTeX</span>
    <span class="page">p. {job.page + 1}</span>
    <button class="x" onclick={() => cancelEquation(tab)} aria-label="Close"><Icon name="close" size={12} /></button>
  </div>

  {#if job.status === "confirm"}
    <img class="clip" src={pageImageUrl(tab.doc.docId, job.page, 3, job.rect, tab.revs[job.page] ?? 0)} alt="The selected area" />
    <p class="ask">Send this area to the AI in the terminal?</p>
    <div class="actions">
      <span class="grow"></span>
      <button onclick={() => cancelEquation(tab)}>Cancel</button>
      <button class="primary" onclick={() => confirmEquation(tab)}>OK</button>
    </div>
  {:else if job.status === "preparing" || job.status === "waiting"}
    <div class="wait">
      <span class="spinner"></span>
      {job.status === "preparing" ? "Preparing the image…" : `Waiting for ${term.ai ? agentLabel(term.ai) : "the AI"} in the terminal…`}
    </div>
    <p class="hint">If it asks for permission to write the file, allow it in the terminal.</p>
    <div class="actions"><span class="grow"></span><button onclick={() => cancelEquation(tab)}>Cancel</button></div>
  {:else if job.status === "error"}
    <p class="error">{job.error}</p>
    <div class="actions"><span class="grow"></span><button onclick={() => cancelEquation(tab)}>Close</button></div>
  {:else}
    <div class="math">{@html rendered}</div>
    <textarea bind:value={latex} rows="3" spellcheck="false" aria-label="LaTeX"></textarea>
    <div class="actions">
      <button onclick={copy}><Icon name="copy" size={13} /> Copy</button>
      <span class="grow"></span>
      <button onclick={() => cancelEquation(tab)}>Close</button>
      <button class="primary" onclick={() => insertEquation(tab, latex)} disabled={!latex.trim()}>Insert into Note</button>
    </div>
  {/if}
</div>

<style>
  .clip {
    display: block;
    max-width: 100%;
    max-height: 160px;
    margin: 4px auto 6px;
    border-radius: 5px;
    background: white;
    box-shadow: 0 0 0 0.5px var(--separator);
  }

  .ask {
    margin: 0 0 6px;
    font-size: 12px;
    color: var(--secondary);
  }

  .box {
    position: fixed;
    z-index: 30;
    top: 12vh;
    left: 50%;
    transform: translateX(-50%);
    width: min(760px, calc(100vw - 32px));
    max-height: 76vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    padding: 10px 12px 12px;
    border-radius: 16px;
    background: var(--popover-solid);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 12px 36px rgb(0 0 0 / 0.28);
    font-size: 12.5px;
  }

  .head {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 8px;
    color: var(--accent);
  }

  .title {
    font-weight: 600;
    color: var(--text);
  }

  .page {
    color: var(--secondary);
    font-size: 11px;
  }

  .x {
    margin-left: auto;
    display: grid;
    place-items: center;
    width: 22px;
    height: 22px;
    border-radius: 8px;
    color: var(--secondary);
  }

  .x:hover {
    background: var(--hover);
  }

  .wait {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 0 4px;
  }

  .spinner {
    width: 13px;
    height: 13px;
    border-radius: 50%;
    border: 2px solid var(--separator);
    border-top-color: var(--accent);
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .hint {
    margin: 4px 0 0;
    font-size: 11.5px;
    color: var(--secondary);
  }

  .error {
    margin: 6px 0;
    color: #ff3b30;
  }

  .math {
    flex: 1 1 auto;
    min-height: 90px;
    overflow: auto;
    display: grid;
    place-items: center;
    padding: 18px 16px;
    border-radius: 13px;
    background: var(--surface);
    color: var(--text);
    font-size: 22px;
  }

  /* KaTeX centres display math itself; let wide equations scroll instead of being cut. */
  .math :global(.katex-display) {
    margin: 0;
    max-width: 100%;
    overflow-x: auto;
    overflow-y: hidden;
    padding: 4px 0;
  }

  .math :global(.err) {
    font-size: 11.5px;
    color: #ff3b30;
  }

  textarea {
    flex: none;
    display: block;
    width: 100%;
    margin-top: 10px;
    padding: 6px 8px;
    border: none;
    border-radius: 9px;
    background: var(--hover);
    color: var(--text);
    font: 12px/1.4 ui-monospace, SFMono-Regular, Consolas, "DejaVu Sans Mono", monospace;
    resize: vertical;
    outline: none;
    user-select: text;
  }

  textarea:focus {
    box-shadow: 0 0 0 3px var(--focus-ring);
  }

  .actions {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 10px;
  }

  .grow {
    flex: 1;
  }

  .actions button {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 3px 10px;
    border-radius: 8px;
    background: var(--hover);
  }

  .actions .primary {
    background: var(--accent);
    color: var(--accent-text);
    font-weight: 500;
  }

  .actions button:disabled {
    opacity: 0.5;
  }
</style>
