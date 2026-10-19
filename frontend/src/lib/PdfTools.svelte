<script lang="ts">
  // PhDF Tools: rotate, delete, duplicate, blank pages, reorder (drag), insert a PDF, extract,
  // split. Edits happen on a copy in the backend (`tools_*`); results are always new files
  // ("<name>_phdfE.pdf", "<name>_p_3-7_phdf.pdf"), the original is never changed.
  import { onMount } from "svelte";
  import { api, pageImageUrl, type RecentDocument, type ToolsState } from "./api";
  import Icon from "./Icon.svelte";
  import { notify } from "./notify.svelte";
  import { kbd } from "./platform";

  let { path = null, onopenpath, onclose }: { path?: string | null; onopenpath: (path: string) => void; onclose: () => void } =
    $props();

  let s = $state<ToolsState | null>(null);
  let selected = $state<number[]>([]);
  let anchor = -1; // for Shift-click ranges
  let busy = $state(false);
  let saved = $state(true); // nothing to lose on close
  let recents = $state<RecentDocument[]>([]);
  let question = $state<{ text: string; buttons: { key: string; label: string; primary?: boolean }[]; answer: (key: string) => void } | null>(null);
  let splitOpen = $state(false);
  let splitMode = $state<"every" | "selected" | "chapters">("every");
  let splitEvery = $state(10);
  let menu = $state<{ x: number; y: number } | null>(null);
  let dropAt = $state<number | null>(null);

  const THUMB = 132; // px
  const count = $derived(s?.pages.length ?? 0);
  const sel = $derived([...selected].sort((a, b) => a - b));
  const after = $derived(sel.length ? sel[sel.length - 1] + 1 : count); // insert position

  onMount(async () => {
    const py = await api();
    if (path) await openFile(path);
    else recents = (await py.recent_documents(8)).filter((r) => /\.pdf$/i.test(r.path));
  });

  function ask(text: string, buttons: { key: string; label: string; primary?: boolean }[]): Promise<string> {
    return new Promise((resolve) => (question = { text, buttons, answer: (k) => ((question = null), resolve(k)) }));
  }

  async function run<T>(work: () => Promise<T>): Promise<T | undefined> {
    busy = true;
    try {
      return await work();
    } catch (e) {
      notify.error(String(e).replace(/^Error: /, ""));
    } finally {
      busy = false;
    }
  }

  async function openFile(p: string) {
    if (!(await settle())) return;
    await run(async () => {
      // Open the new file first: if that fails, the current one stays as it was.
      const next = await (await api()).tools_open(p);
      if (s) (await api()).tools_close(s.id);
      s = next;
      selected = [];
      saved = true;
    });
  }

  async function pick() {
    const p = await (await api()).pick_pdf();
    if (p) await openFile(p);
  }

  async function apply(op: Record<string, unknown>, keepSelection = false) {
    if (!s) return;
    const id = s.id;
    const next = await run(async () => (await api()).tools_apply(id, op));
    if (!next) return;
    s = next;
    saved = false;
    if (!keepSelection) selected = [];
  }

  async function undo() {
    if (!s?.canUndo) return;
    const id = s.id;
    const next = await run(async () => (await api()).tools_undo(id));
    if (next) (s = next), (saved = false); // differs from the saved copy again
  }

  // --- selection -----------------------------------------------------------------------------------

  function click(i: number, e: MouseEvent) {
    if (e.shiftKey && anchor >= 0) {
      const [a, b] = [Math.min(anchor, i), Math.max(anchor, i)];
      selected = [...new Set([...selected, ...Array.from({ length: b - a + 1 }, (_, k) => a + k)])];
    } else if (e.ctrlKey || e.metaKey) {
      selected = selected.includes(i) ? selected.filter((x) => x !== i) : [...selected, i];
      anchor = i;
    } else {
      selected = [i];
      anchor = i;
    }
  }

  function onContext(i: number, e: MouseEvent) {
    e.preventDefault();
    if (!selected.includes(i)) selected = [i];
    menu = { x: Math.min(e.clientX, innerWidth - 230), y: Math.min(e.clientY, innerHeight - 330) };
  }

  // --- drag to reorder -----------------------------------------------------------------------------

  function onDragStart(i: number, e: DragEvent) {
    if (!selected.includes(i)) selected = [i];
    e.dataTransfer?.setData("text/plain", "pages");
  }

  function onDragOver(i: number, e: DragEvent) {
    e.preventDefault();
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    dropAt = e.clientX < r.left + r.width / 2 ? i : i + 1;
  }

  async function onDrop(e: DragEvent) {
    e.preventDefault();
    const to = dropAt;
    dropAt = null;
    if (to === null || !sel.length) return;
    const moved = sel.length;
    const before = sel.filter((p) => p < to).length;
    await apply({ kind: "move", pages: sel, to });
    const start = to - before; // where the moved pages are now
    selected = Array.from({ length: moved }, (_, k) => start + k);
  }

  // --- tools ----------------------------------------------------------------------------------------

  const rotate = (by: number) => sel.length && apply({ kind: "rotate", pages: sel, by }, true);
  const remove = () => sel.length && apply({ kind: "delete", pages: sel });
  const duplicate = () => sel.length && apply({ kind: "duplicate", pages: sel });
  const blank = () => apply({ kind: "blank", at: after });

  async function insertPdf() {
    const p = await (await api()).pick_pdf();
    if (p) await apply({ kind: "insert_pdf", path: p, at: after });
  }

  /** If the pages to write have annotations: keep or remove them? null = cancelled. */
  async function keepAnnotations(pages: number[] | null): Promise<boolean | null> {
    if (!s || !(await (await api()).tools_has_annotations(s.id, pages))) return true;
    const k = await ask("These pages have annotations (highlights, notes, drawings). Keep them in the new file?", [
      { key: "cancel", label: "Cancel" },
      { key: "remove", label: "Remove Them" },
      { key: "keep", label: "Keep Them", primary: true },
    ]);
    return k === "cancel" ? null : k === "keep";
  }

  function done(paths: string[], text: string) {
    const first = paths[0];
    notify.show({ text, action: first ? { label: "Open", run: () => onopenpath(first) } : undefined }, 8000);
  }

  async function save() {
    if (!s) return;
    const keep = await keepAnnotations(null);
    if (keep === null) return;
    const id = s.id;
    const out = await run(async () => (await api()).tools_save(id, keep));
    if (out) {
      saved = true;
      done([out], `Saved as ${out.split(/[\\/]/).pop()} (the original is unchanged).`);
    }
  }

  async function extract() {
    if (!s || !sel.length) return;
    const keep = await keepAnnotations(sel);
    if (keep === null) return;
    const id = s.id;
    const pages = sel;
    const out = await run(async () => (await api()).tools_extract(id, pages, keep));
    if (out) done([out], `Extracted ${pages.length} page${pages.length === 1 ? "" : "s"} to ${out.split(/[\\/]/).pop()}.`);
  }

  async function split() {
    if (!s) return;
    let starts: number[];
    if (splitMode === "every") starts = Array.from({ length: Math.ceil(count / Math.max(1, splitEvery)) }, (_, k) => k * Math.max(1, splitEvery));
    else if (splitMode === "selected") starts = [0, ...sel.filter((p) => p > 0)];
    else starts = [0, ...(await (await api()).tools_chapters(s.id)).filter((p) => p > 0 && p < count)];
    starts = [...new Set(starts)].sort((a, b) => a - b);
    if (starts.length < 2) {
      notify.show({ text: splitMode === "chapters" ? "This PDF has no chapters to split at." : "That would be just one part: select where new parts start." });
      return;
    }
    const parts = starts.map((a, k) => Array.from({ length: (starts[k + 1] ?? count) - a }, (_, j) => a + j));
    const keep = await keepAnnotations(null);
    if (keep === null) return;
    splitOpen = false;
    const id = s.id;
    const out = await run(async () => (await api()).tools_split(id, parts, keep));
    if (out) done(out, `Split into ${out.length} files next to the original.`);
  }

  /** Unsaved changes: offer to save a copy first. False when the user cancels. Also used when
   *  the window closes. */
  export async function settle(): Promise<boolean> {
    if (!s || saved) return true;
    const k = await ask("Close without saving? Your changes are only in PhDF Tools until you save a copy.", [
      { key: "cancel", label: "Cancel" },
      { key: "close", label: "Close Without Saving" },
      { key: "save", label: "Save Copy", primary: true },
    ]);
    if (k === "cancel") return false;
    if (k === "save") await save();
    return k === "close" || saved;
  }

  async function close() {
    if (!(await settle())) return;
    if (s) (await api()).tools_close(s.id);
    onclose();
  }

  function onKey(e: KeyboardEvent) {
    if ((e.target as HTMLElement).closest("input")) return;
    const mod = e.ctrlKey || e.metaKey;
    if (e.key === "Escape") {
      if (question) return;
      if (menu || splitOpen) (menu = null), (splitOpen = false);
      else if (selected.length) selected = [];
      else close();
    } else if (!s) return;
    else if (mod && e.key.toLowerCase() === "z") undo();
    else if (mod && e.key.toLowerCase() === "a") selected = Array.from({ length: count }, (_, i) => i);
    else if (mod && e.key.toLowerCase() === "s") save();
    else if (e.key === "Delete" || e.key === "Backspace") remove();
    else return;
    e.preventDefault();
    e.stopPropagation();
  }
</script>

<svelte:window onkeydowncapture={onKey} />

<div class="tools" role="dialog" aria-label="PhDF Tools">
  <header>
    <span class="logo"><Icon name="doc" size={18} /></span>
    <div class="title">
      <h2>PhDF Tools</h2>
      <p>{s ? `${s.name} · ${count} pages${sel.length ? ` · ${sel.length} selected` : ""}` : "Choose a PDF to work on"}</p>
    </div>
    {#if s}
      <button class="ghost" onclick={pick} title="Work on another PDF">Change PDF…</button>
      <button class="ghost" onclick={undo} disabled={!s.canUndo || busy} title={kbd("Undo (Ctrl+Z)")}>Undo</button>
      <button class="save" onclick={save} disabled={busy} title={kbd("Save as a new file next to the original (Ctrl+S)")}>Save Copy</button>
    {/if}
    <button class="close" onclick={close} aria-label="Close"><Icon name="close" size={14} /></button>
  </header>

  {#if !s}
    <div class="start">
      <button class="big" onclick={pick}><Icon name="open" size={22} /> Choose a PDF…</button>
      {#if recents.length}
        <h3>Recent PDFs</h3>
        {#each recents as r}
          <button class="recent" onclick={() => openFile(r.path)} title={r.path}>{r.title || r.path.split(/[\\/]/).pop()}</button>
        {/each}
      {/if}
      <p class="note">Your original PDF is never changed: every result is saved as a new file next to it.</p>
    </div>
  {:else}
    <div class="bar" role="toolbar" aria-label="Page tools">
      <button onclick={() => rotate(-90)} disabled={!sel.length || busy} title="Rotate left"><span class="ico">⟲</span> Left</button>
      <button onclick={() => rotate(90)} disabled={!sel.length || busy} title="Rotate right"><span class="ico">⟳</span> Right</button>
      <span class="sep"></span>
      <button onclick={duplicate} disabled={!sel.length || busy}>Duplicate</button>
      <button onclick={remove} disabled={!sel.length || busy} class="danger" title="Delete (Del)">Delete</button>
      <span class="sep"></span>
      <button onclick={blank} disabled={busy} title="After the selection (or at the end)">Blank Page</button>
      <button onclick={insertPdf} disabled={busy} title="Insert another PDF after the selection (or at the end)">Insert PDF…</button>
      <span class="sep"></span>
      <button onclick={extract} disabled={!sel.length || busy} title="Save the selected pages as a new PDF">Extract…</button>
      <button onclick={() => (splitOpen = !splitOpen)} class:on={splitOpen} disabled={busy}>Split…</button>
      <span class="grow"></span>
      <span class="hint">Click, Shift-click or {kbd("Ctrl")}-click to select · drag to reorder · right-click for more</span>
    </div>

    {#if splitOpen}
      <div class="split">
        <label><input type="radio" bind:group={splitMode} value="every" /> Every <input class="num" type="number" min="1" bind:value={splitEvery} /> pages</label>
        <label><input type="radio" bind:group={splitMode} value="selected" /> At the selected pages (each starts a new part)</label>
        <label><input type="radio" bind:group={splitMode} value="chapters" /> At chapter starts</label>
        <button class="save" onclick={split} disabled={busy}>Split</button>
      </div>
    {/if}

    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="grid" ondragover={(e) => e.preventDefault()} ondrop={onDrop}>
      {#each s.pages as [w, h], i (i + ":" + (s.revs[i] ?? 0))}
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <div
          class="thumb"
          class:sel={selected.includes(i)}
          class:drop-before={dropAt === i}
          class:drop-after={dropAt === i + 1 && i === count - 1}
          draggable="true"
          role="option"
          aria-selected={selected.includes(i)}
          tabindex="-1"
          onclick={(e) => click(i, e)}
          oncontextmenu={(e) => onContext(i, e)}
          ondragstart={(e) => onDragStart(i, e)}
          ondragover={(e) => onDragOver(i, e)}
          ondragend={() => (dropAt = null)}
        >
          <div class="img" style="aspect-ratio:{w} / {h}">
            <img src={pageImageUrl(s.id, i, (THUMB * devicePixelRatio) / w, undefined, s.revs[i] ?? 0)} alt="Page {i + 1}" loading="lazy" draggable="false" />
          </div>
          <span class="num">{i + 1}{#if s.annotated[i]}<span class="dot" title="Has annotations"></span>{/if}</span>
        </div>
      {/each}
    </div>
  {/if}

  {#if busy}<div class="busy">Working…</div>{/if}
</div>

{#if menu}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="backdrop" onclick={() => (menu = null)} oncontextmenu={(e) => (e.preventDefault(), (menu = null))}></div>
  <div class="menu" role="menu" style="left:{menu.x}px;top:{menu.y}px">
    {#each [["Rotate Left", () => rotate(-90)], ["Rotate Right", () => rotate(90)], ["Duplicate", duplicate], ["Delete", remove], ["Blank Page After", blank], ["Insert PDF After…", insertPdf], ["Extract…", extract]] as [label, act]}
      <button role="menuitem" onclick={() => ((menu = null), (act as () => void)())}>{label}</button>
    {/each}
  </div>
{/if}

{#if question}
  {@const q = question}
  <div class="backdrop dim"></div>
  <div class="question" role="alertdialog">
    <p>{q.text}</p>
    <div class="answers">
      {#each q.buttons as b}
        <button class:primary={b.primary} onclick={() => q.answer(b.key)}>{b.label}</button>
      {/each}
    </div>
  </div>
{/if}

<style>
  .tools {
    position: fixed;
    inset: 0;
    z-index: 65;
    font-family: var(--font);
    display: flex;
    flex-direction: column;
    background: var(--canvas);
  }

  header {
    flex: none;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 16px;
    background: var(--toolbar);
    border-bottom: 0.5px solid var(--separator);
  }

  .logo {
    display: grid;
    place-items: center;
    width: 34px;
    height: 34px;
    border-radius: 12px;
    color: white;
    background: linear-gradient(135deg, #5e9bff, #7a4dff 55%, #ff5fa2);
  }

  .title {
    flex: 1;
    min-width: 0;
  }

  h2 {
    margin: 0;
    font-size: 17px;
    font-weight: 650;
    letter-spacing: -0.01em;
  }

  .title p {
    margin: 0;
    font-size: 12px;
    color: var(--secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .ghost,
  .bar button,
  .answers button {
    padding: 5px 11px;
    border-radius: 9px;
    background: var(--hover);
    font-size: 13px;
  }

  .ghost:disabled,
  .bar button:disabled {
    opacity: 0.4;
  }

  .save,
  .answers .primary {
    padding: 5px 14px;
    border-radius: 9px;
    background: var(--accent);
    color: var(--accent-text);
    font-weight: 600;
  }

  .close {
    display: grid;
    place-items: center;
    width: 28px;
    height: 28px;
    border-radius: 9px;
    color: var(--secondary);
  }

  .close:hover,
  .ghost:hover:not(:disabled),
  .bar button:hover:not(:disabled) {
    background: var(--pressed);
  }

  .start {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    margin: auto;
    width: min(420px, 90%);
  }

  .big {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 28px;
    border-radius: 18px;
    font-size: 16px;
    font-weight: 600;
    color: white;
    background: linear-gradient(135deg, #5e9bff, #7a4dff 55%, #ff5fa2);
    box-shadow: 0 8px 24px rgb(122 77 255 / 0.35);
  }

  .start h3 {
    margin: 14px 0 2px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    color: var(--secondary);
  }

  .recent {
    width: 100%;
    padding: 6px 12px;
    border-radius: 10px;
    background: var(--surface);
    box-shadow: var(--card-shadow);
    text-align: left;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .note {
    margin-top: 14px;
    font-size: 12px;
    color: var(--secondary);
    text-align: center;
  }

  .bar {
    flex: none;
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    padding: 8px 16px;
    border-bottom: 0.5px solid var(--separator);
    background: var(--surface);
  }

  .bar .danger {
    color: #ff3b30;
  }

  .bar button.on {
    background: var(--accent);
    color: var(--accent-text);
  }

  .ico {
    font-size: 15px;
  }

  .sep {
    width: 0.5px;
    height: 20px;
    background: var(--separator);
  }

  .grow {
    flex: 1;
  }

  .hint {
    font-size: 11px;
    color: var(--tertiary);
  }

  .split {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px 18px;
    padding: 10px 16px;
    background: var(--surface);
    border-bottom: 0.5px solid var(--separator);
    font-size: 13px;
  }

  .split .num {
    width: 54px;
    height: 24px;
    border: none;
    border-radius: 6px;
    background: var(--hover);
    color: var(--text);
    text-align: center;
  }

  .grid {
    flex: 1;
    overflow: auto;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 16px;
    padding: 18px;
    align-content: start;
  }

  .thumb {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 5px;
    padding: 8px;
    border-radius: 13px;
    cursor: pointer;
    /* Skip layout and painting of thumbnails out of view (big books). */
    content-visibility: auto;
    contain-intrinsic-size: auto 150px auto 210px;
  }

  .thumb:hover {
    background: var(--hover);
  }

  .thumb.sel {
    background: color-mix(in srgb, var(--accent) 18%, transparent);
    box-shadow: inset 0 0 0 2px var(--accent);
  }

  .thumb.drop-before,
  .thumb.drop-after {
    content-visibility: visible; /* else the marker outside the box is clipped */
  }

  .thumb.drop-before::before,
  .thumb.drop-after::after {
    content: "";
    position: absolute;
    top: 6px;
    bottom: 6px;
    width: 3px;
    border-radius: 2px;
    background: var(--accent);
  }

  .thumb.drop-before::before {
    left: -10px;
  }

  .thumb.drop-after::after {
    right: -10px;
  }

  .img {
    width: 132px;
    max-height: 190px;
    display: grid;
    place-items: center;
    background: white;
    box-shadow: var(--page-shadow);
    overflow: hidden;
  }

  .img img {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }

  .num {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    color: var(--secondary);
  }

  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #ffd60a;
    box-shadow: 0 0 0 1px rgb(0 0 0 / 0.15);
  }

  .busy {
    position: absolute;
    right: 16px;
    bottom: 14px;
    padding: 6px 12px;
    border-radius: 10px;
    background: var(--popover-solid);
    box-shadow: var(--card-shadow);
    font-size: 12px;
  }

  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 66;
  }

  .backdrop.dim {
    background: rgb(0 0 0 / 0.25);
  }

  .menu {
    position: fixed;
    z-index: 67;
    min-width: 200px;
    padding: 5px;
    border-radius: 12px;
    background: var(--popover-solid);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 8px 28px rgb(0 0 0 / 0.22);
  }

  .menu button {
    display: block;
    width: 100%;
    padding: 4px 12px;
    border-radius: 6px;
    text-align: left;
  }

  .menu button:hover {
    background: var(--accent);
    color: var(--accent-text);
  }

  .question {
    position: fixed;
    left: 50%;
    top: 30%;
    z-index: 67;
    transform: translateX(-50%);
    width: min(420px, 90vw);
    padding: 18px 20px 14px;
    border-radius: 18px;
    background: var(--popover-solid);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 20px 50px rgb(0 0 0 / 0.3);
  }

  .question p {
    margin: 0 0 14px;
    line-height: 1.45;
  }

  .answers {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
</style>
