<script lang="ts">
  // ✦ AI pull-down: ask about the whole document, the current chapter or the current page.
  // "Read as Markdown" on: the text is converted to Markdown (with PDF page markers; the whole
  // document once, in the background) and the AI reads that file. Off: the AI opens the PDF.
  import { api, type MarkdownStatus } from "../api";
  import { notify } from "../notify.svelte";
  import { chapterAt } from "../reading.svelte";
  import type { Tab } from "../tab.svelte";
  import { askAi } from "./terminal.svelte";

  let { tab, paneId, onclose }: { tab: Tab; paneId: number; onclose: () => void } = $props();

  $effect(() => {
    tab.loadOutline();
  });

  // Read as Markdown: on by default, off for big documents (converting takes minutes); the
  // user's choice is remembered per file.
  const BIG = 300;
  // By file path, not doc id: the id changes with every save.
  const key = $derived(`ai.markdown.${tab.path.toLowerCase()}`);
  let useMd = $state(false);
  let status = $state<MarkdownStatus | null>(null);

  $effect(() => {
    api()
      .then((py) => py.get_setting<boolean | null>(key, null))
      .then((saved) => (useMd = saved ?? tab.pageCount <= BIG));
  });

  // While on: prepare the whole document in the background and show the progress.
  $effect(() => {
    if (!useMd) return;
    let stop = false;
    (async () => {
      const py = await api();
      status = await py.ai_markdown_prepare(tab.doc.docId);
      while (!stop && status.state === "working") {
        await new Promise((r) => setTimeout(r, 800));
        if (!stop) status = await py.ai_markdown_status(tab.doc.docId);
      }
    })();
    return () => (stop = true);
  });

  async function toggleMd() {
    useMd = !useMd;
    (await api()).set_setting(key, useMd);
  }

  const chapter = $derived(chapterAt(tab.outline, tab.page, tab.pageCount));

  type Scope = "document" | "chapter" | "page";
  interface Item {
    label: string;
    scope: Scope;
    task: string | null; // null = the user types the question
  }

  const items = $derived<Item[]>([
    { label: "Summarize this document", scope: "document", task: "Summarize it: the main argument, then the key points section by section." },
    ...(chapter
      ? [{ label: `Summarize this chapter`, scope: "chapter" as Scope, task: "Summarize this chapter in clear bullet points." }]
      : []),
    { label: "Explain this page", scope: "page", task: "Explain this page in simple terms, including any difficult ideas or terms." },
    { label: "Key ideas & terms", scope: chapter ? "chapter" : "document", task: "List the key ideas and the important terms with short definitions." },
    { label: "Study questions", scope: chapter ? "chapter" : "document", task: "Write 8 study questions (with short answers) to check understanding." },
    { label: "Ask your own question…", scope: chapter ? "chapter" : "document", task: null },
  ]);

  function range(scope: Scope): [number, number] {
    if (scope === "page") return [tab.page, tab.page];
    if (scope === "chapter" && chapter) {
      const start = tab.outline!.filter((i) => i.page >= 0 && i.page <= tab.page).sort((a, b) => b.page - a.page)[0]?.page ?? 0;
      return [start, chapter.end - 1];
    }
    return [0, tab.pageCount - 1];
  }

  async function run(item: Item) {
    onclose();
    const [first, last] = range(item.scope);
    const pagesLabel = first === last ? `page ${first + 1}` : `pages ${first + 1}–${last + 1}`;
    const what = item.scope === "chapter" && chapter ? `the chapter “${chapter.title}”` : item.scope === "page" ? "this page" : "this document";
    const folder = tab.path.replace(/[\\/][^\\/]*$/, "");
    if (!useMd) {
      const text =
        `Open the PDF "${tab.path}" and read ${pagesLabel} (PDF page numbers, counting from 1; the book's printed ` +
        `page numbers can differ). That is ${what} of “${tab.title}”.\n\n` +
        (item.task ?? "");
      return askAi(text, item.task !== null, folder, paneId);
    }
    // Ranges are cut from the whole-document copy when it is ready; else converted now.
    const slow = status?.state !== "ready" && last - first > 40;
    if (slow) notify.show({ text: `Preparing ${last - first + 1} pages for the AI…` }, 120000);
    try {
      const ctx = await (await api()).ai_context(tab.doc.docId, first, last);
      if (slow) notify.clear();
      const text =
        `Read the file "${ctx.path}". It is the text of ${what} (“${tab.title}”, ${pagesLabel}), converted to Markdown from the PDF "${tab.path}". ` +
        `Lines like <!-- PDF page 12 --> mark where each PDF page starts: "page" means those numbers (the book's printed page numbers can differ). ` +
        `If you need a figure, a table or an equation exactly, open the PDF itself.\n\n` +
        (item.task ?? "");
      await askAi(text, item.task !== null, folder, paneId);
    } catch (e) {
      notify.error(`Could not prepare the text: ${e}`);
    }
  }
</script>

<div class="dropdown" role="menu">
  <div class="title">Ask the AI about…</div>
  {#each items as item}
    <button role="menuitem" class:own={item.task === null} onclick={() => run(item)}>
      {item.label}
      <small>{item.scope === "page" ? `p. ${tab.page + 1}` : item.scope === "chapter" && chapter ? chapter.title : `${tab.pageCount} pages`}</small>
    </button>
  {/each}
  <div class="md-switch">
    <label>
      <input type="checkbox" checked={useMd} onchange={toggleMd} />
      <span>Read as Markdown</span>
    </label>
    <small>
      {#if !useMd}
        {tab.pageCount > BIG
          ? `Off for big documents (${tab.pageCount} pages): converting takes a few minutes. Turn it on to prepare it in the background.`
          : "Off: the AI opens the PDF itself (slower, more tokens; sees figures)."}
      {:else if status?.state === "working"}
        Preparing the text: {status.done} / {status.total} pages…
      {:else if status?.state === "error"}
        Could not convert: {status.error}
      {:else}
        On: the AI reads a Markdown copy (fast, few tokens) and opens the PDF only for figures.
      {/if}
    </small>
  </div>
  <p class="hint">Runs in the terminal with your AI agent.</p>
</div>

<style>
  .md-switch {
    margin: 6px 4px 0;
    padding-top: 6px;
    border-top: 0.5px solid var(--separator);
  }

  .md-switch label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-weight: 600;
    font-size: 12px;
  }

  .md-switch small {
    display: block;
    margin: 2px 0 0 22px;
    font-size: 11px;
    color: var(--secondary);
  }

  .dropdown {
    position: absolute;
    top: calc(100% + 6px);
    right: 0;
    z-index: 21;
    width: 290px;
    padding: 6px;
    border-radius: 11px;
    background: var(--popover-solid);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 10px 32px rgb(0 0 0 / 0.24);
  }

  .title {
    padding: 4px 8px;
    font-size: 11px;
    font-weight: 600;
    color: var(--secondary);
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  button {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    width: 100%;
    padding: 5px 8px;
    border-radius: 6px;
    text-align: left;
  }

  button:hover {
    background: var(--accent);
    color: var(--accent-text);
  }

  button.own {
    font-style: italic;
  }

  small {
    max-width: 110px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 11px;
    color: var(--tertiary);
  }

  button:hover small {
    color: inherit;
  }

  .hint {
    margin: 6px 8px 2px;
    font-size: 11px;
    color: var(--tertiary);
  }
</style>
