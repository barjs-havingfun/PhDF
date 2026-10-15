<script lang="ts">
  // ✦ AI pull-down: ask about the whole document, the current chapter or the current page. The
  // text is converted to Markdown first and the AI is pointed at that file.
  import { api } from "../api";
  import { notify } from "../notify.svelte";
  import { chapterAt } from "../reading.svelte";
  import type { Tab } from "../tab.svelte";
  import { askAi } from "./terminal.svelte";

  let { tab, paneId, onclose }: { tab: Tab; paneId: number; onclose: () => void } = $props();

  $effect(() => {
    tab.loadOutline();
  });

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
    const big = last - first > 40;
    if (big) notify.show({ text: `Preparing ${last - first + 1} pages for the AI…` }, 120000);
    try {
      const ctx = await (await api()).ai_context(tab.doc.docId, first, last);
      if (big) notify.clear();
      const pages = ctx.first === ctx.last ? `page ${ctx.first + 1}` : `pages ${ctx.first + 1}–${ctx.last + 1}`;
      const what = item.scope === "chapter" && chapter ? `the chapter “${chapter.title}”` : item.scope === "page" ? "this page" : "this document";
      const text =
        `Read the file "${ctx.path}". It is the text of ${what} — “${tab.title}”, ${pages} — converted to Markdown from the PDF "${tab.path}".\n\n` +
        (item.task ?? "");
      const folder = tab.path.replace(/[\\/][^\\/]*$/, "");
      await askAi(text, item.task !== null, folder, paneId);
    } catch (e) {
      notify.error(`Could not prepare the text: ${e}`);
    }
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="menu-backdrop" onclick={onclose}></div>
<div class="dropdown" role="menu">
  <div class="title">Ask the AI about…</div>
  {#each items as item}
    <button role="menuitem" class:own={item.task === null} onclick={() => run(item)}>
      {item.label}
      <small>{item.scope === "page" ? `p. ${tab.page + 1}` : item.scope === "chapter" && chapter ? chapter.title : `${tab.pageCount} pages`}</small>
    </button>
  {/each}
  <p class="hint">Runs in the terminal with Claude Code or Codex. The text is converted to Markdown so the AI can read it.</p>
</div>

<style>
  .menu-backdrop {
    position: fixed;
    inset: 0;
    z-index: 20;
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
