<script lang="ts">
  // "How to use PhDF": a short tour of every feature, opened from the ? button.
  import { fly } from "svelte/transition";
  import Icon from "./Icon.svelte";
  import { kbd } from "./platform";

  let { onclose }: { onclose: () => void } = $props();

  const sections = [
    {
      icon: "doc",
      title: "Reading",
      items: [
        "Open a PDF or a Markdown note with <b>Ctrl+O</b>. PhDF remembers the page, zoom and open tabs.",
        "Search with <b>Ctrl+F</b> (Enter / Shift+Enter for next / previous), go to a page with <b>Ctrl+G</b>.",
        "Links open small first: zoom the preview, use its <b>T</b> button to select text, or <i>Go to Page</i>.",
        "Drag a tab to reorder it, onto the left/right edge of a page to read side by side, or out of the window for a new window.",
      ],
    },
    {
      icon: "note",
      title: "Highlights & notes",
      items: [
        "Select text to <b>highlight</b>, underline, strike through, copy, or send it to a note or the AI.",
        "Toolbar: sticky <b>note</b>, free <b>text</b> and <b>draw</b> tools; the list button shows every annotation.",
        "Click an annotation to recolour, comment or delete it (<b>Delete</b> also works); <b>Ctrl+Z</b> undoes. Save into the PDF with <b>Ctrl+S</b>.",
        "<b>Drag</b> a sticky note or text box to move it; to move a drawing, click it first, then drag.",
        "Text boxes: pick <b>Sans / Serif / Mono</b>, the size and <b>B</b>old when you place one, or click a box later to change them.",
        "<b>Ctrl+B</b> bookmarks a page (list in the sidebar's <i>Marks</i>); ⋯ → <i>Export Highlights to Note</i> collects every highlight under a line at the end of the book's note.",
        "Scanned page? A bar offers <i>Recognize Text</i> (OCR) so you can select and search it.",
      ],
    },
    {
      icon: "mdnote",
      title: "The book's note",
      items: [
        "The note button opens <code>&lt;book&gt;.md</code> next to the PDF, beside the page.",
        "<i>Note in MD</i> on a selection adds a pin <code>⎘ phdf · p.12 · #id</code> with the quote: write under it.",
        "Click <i>Go to PDF ↗</i> on a pin to jump to the highlight; click a highlight to jump to its pin.",
        "<b>Aa</b> sets the note's font, size and spacing.",
      ],
    },
    {
      icon: "park",
      title: "Parking lot",
      items: [
        "Stray thought while reading? The 💡 <i>Park</i> button next to Read/Focus (or <b>Ctrl+Shift+Space</b>), type, Enter, and you're back on the page.",
        "Thoughts go to <code>&lt;book&gt;.parking.md</code> and show in the note's <i>Parking</i> tab.",
      ],
    },
    {
      icon: "book",
      title: "Read & Focus",
      items: [
        "<i>Read</i>: a reading ruler, zen mode (<b>Ctrl+.</b>), full screen (<b>F11</b>) and page tints, each on its own.",
        "<i>Focus</i>: a pomodoro timer and how long the chapter / book will take at your pace.",
      ],
    },
    {
      icon: "grade",
      title: "Grading exams",
      items: [
        "The <i>Grade</i> button (next to <b>?</b>) asks for a folder of exam PDFs, subfolders too, e.g. a Moodle download. They open one by one; mark them with any tool.",
        "<i>Done</i> saves and opens the next exam, <i>Prev</i> goes back; the sidebar's <i>Exams</i> list jumps anywhere. The originals are never changed: the marked copies go to <code>graded/</code>.",
        "Beside the exam: the folder's grades table <code>&lt;folder&gt;.grades.md</code> (<i>#, Name, Grade, Comment</i>, add your own columns).",
        "<i>Automated</i> on: a drawer asks who wrote each exam, and the grade typed next to Done (Enter = Done) goes into the table. Off: fill the table yourself. <i>CSV</i> exports it.",
      ],
    },
    {
      icon: "terminal",
      title: "AI terminal",
      items: [
        "<b>Ctrl+`</b> (or the terminal button) opens a shell in the PDF's folder. The first time it asks for your AI agent: Claude Code, Codex, Gemini CLI or <b>any other terminal AI</b>, which then starts by itself. New to this? <i>How to</i> in the terminal's header walks you through installing one.",
        "It sits above the note; drag the line between them to resize, click its header to fold it away, drag the header (or ⇩) to dock it at the bottom.",
        "<b>+</b> in its header opens another terminal as a tab, each with its own shell (e.g. Claude in one, Codex in another); × closes one, the others keep running. <i>Ask AI</i> goes to the tab shown, or to a tab where an AI already runs.",
        "Select text → ✦ <i>Ask AI</i>: <i>Explain / Summarize / Translate</i> send at once; <i>My own question…</i> lets you type first.",
        "✦ in the toolbar asks about the <b>whole document</b>, the current chapter or page (summaries, key ideas, study questions).",
        "▾ next to ✦ → <i>Equation → LaTeX</i>: drag a rectangle around an equation; the AI writes its LaTeX, you check it and <i>Insert into Note</i> (at your cursor, as <code>$$ … $$</code>). The note's Preview shows the math.",
      ],
    },
    {
      icon: "obsidian",
      title: "Obsidian & export",
      items: [
        "Pick your vault in ⋯ → <i>Settings</i>. <i>Send to Obsidian</i> adds quotes to the book's note in the vault.",
        "⋯ → <i>Export as Markdown</i> turns the PDF's text into Markdown (to a file or your vault).",
      ],
    },
    {
      icon: "doc",
      title: "PhDF Tools",
      items: [
        "The shiny <b>PhDF TOOLS</b> button on the start screen (or ⋯ → <i>PDF Tools…</i>) opens a page grid.",
        "Select pages (click, Shift-click, Ctrl-click), then rotate, duplicate, delete, add a blank page or insert another PDF. Drag pages to reorder. Ctrl+Z undoes.",
        "<i>Extract…</i> saves the selected pages as <code>Book_p_3-7_phdf.pdf</code>; <i>Split…</i> every N pages, at the selected pages or at chapters.",
        "<i>Save Copy</i> writes <code>Book_phdfE.pdf</code> next to the original: <b>your original is never changed</b>. If pages have annotations, PhDF asks whether to keep them.",
      ],
    },
  ];

  const shortcuts = [
    ["Find any command", "Ctrl+K"],
    ["Open", "Ctrl+O"],
    ["Undo / redo annotations", "Ctrl+Z / Ctrl+Y"],
    ["Bookmark page", "Ctrl+B"],
    ["Copy with citation", "Ctrl+Shift+C"],
    ["Save annotations", "Ctrl+S"],
    ["Search / go to page", "Ctrl+F / Ctrl+G"],
    ["New / close / next tab", "Ctrl+T / Ctrl+W / Ctrl+Tab"],
    ["Zoom", "Ctrl+ + / − / 0, Ctrl+wheel"],
    ["Back / forward", "Alt+← / Alt+→"],
    ["Sidebar", "Ctrl+\\"],
    ["Zen / full screen", "Ctrl+. / F11"],
    ["Parking lot", "Ctrl+Shift+Space"],
    ["Terminal", "Ctrl+`"],
  ];

  // One card at a time: the feature sections, then the shortcuts.
  const count = sections.length + 1;
  let card = $state(0);
  let dir = $state(1); // 1: forward (the card leaves to the left), -1: back
  function show(next: number) {
    next = Math.min(count - 1, Math.max(0, next));
    if (next === card) return;
    dir = next > card ? 1 : -1;
    card = next;
  }
  const go = (delta: number) => show(card + delta);

  function onKey(e: KeyboardEvent) {
    if (e.key === "Escape") onclose();
    else if (e.key === "ArrowRight") go(1);
    else if (e.key === "ArrowLeft") go(-1);
    else return;
    e.preventDefault();
    e.stopPropagation(); // the PDF behind must not turn its page
  }
</script>

<!-- Capture: handled before the app's own shortcuts, so ← / → don't also turn PDF pages. -->
<svelte:window onkeydowncapture={onKey} />

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={(e) => e.target === e.currentTarget && onclose()}>
  <div class="sheet" role="dialog" aria-label="How to use PhDF">
    <header>
      <div class="app-icon">Ph</div>
      <div>
        <h2>How to use PhDF</h2>
        <p class="sub">A two-minute tour of PhDF.</p>
      </div>
      <button class="close" onclick={onclose} aria-label="Close"><Icon name="close" size={14} /></button>
    </header>

    <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
    <div class="stage">
    {#key card}
    <div class="card" onclick={() => go(1)} in:fly={{ x: 320 * dir, duration: 320, opacity: 0 }} out:fly={{ x: -320 * dir, duration: 320, opacity: 0 }}>
      {#if card < sections.length}
        {@const s = sections[card]}
        <section>
          <h3><Icon name={s.icon as never} size={20} /> {s.title}</h3>
          <ul>
            {#each s.items as item}
              <!-- static, trusted strings written above -->
              <li>{@html kbd(item)}</li>
            {/each}
          </ul>
        </section>
      {:else}
        <section>
          <h3><Icon name="help" size={20} /> Shortcuts</h3>
          <table>
            <tbody>
              {#each shortcuts as [what, keys]}
                <tr><td>{what}</td><td class="keys">{kbd(keys)}</td></tr>
              {/each}
            </tbody>
          </table>
        </section>
      {/if}
    </div>
    {/key}
    </div>
    <footer>
      <button class="nav" onclick={() => go(-1)} disabled={card === 0}>← Back</button>
      <div class="dots">
        {#each { length: count } as _, i}
          <button class="dot" class:on={i === card} aria-label="Card {i + 1}" onclick={() => show(i)}></button>
        {/each}
      </div>
      {#if card < count - 1}
        <button class="nav primary" onclick={() => go(1)}>Next →</button>
      {:else}
        <button class="nav primary" onclick={onclose}>Done</button>
      {/if}
    </footer>
  </div>
</div>

<style>
  /* Cards overlap while one slides out to the left and the next slides in. */
  .stage {
    display: grid;
    overflow: hidden;
    border-radius: 16px;
  }

  .card {
    grid-area: 1 / 1;
    min-height: 420px;
    padding: 26px 30px;
    border-radius: 16px;
    background: color-mix(in srgb, var(--surface) 70%, transparent);
    box-shadow: var(--card-shadow);
    cursor: pointer;
  }

  .card section {
    padding: 0;
    background: none;
    box-shadow: none;
  }

  .card h3 {
    margin-bottom: 14px;
    font-size: 24px;
  }

  .card li {
    font-size: 16px;
    line-height: 1.6;
  }

  .card li + li {
    margin-top: 8px;
  }

  footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-top: 14px;
  }

  .nav {
    padding: 4px 14px;
    border-radius: 7px;
    background: var(--hover);
  }

  .nav.primary {
    background: var(--accent);
    color: var(--accent-text);
  }

  .nav:disabled {
    opacity: 0.4;
  }

  .dots {
    display: flex;
    gap: 6px;
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--separator);
  }

  .dot.on {
    background: var(--accent);
  }

  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 70;
    display: grid;
    place-items: center;
    padding: 24px;
    background: rgb(0 0 0 / 0.2);
    backdrop-filter: blur(3px);
  }

  /* Frosted glass: a little see-through, the app blurred behind it. */
  .sheet {
    width: min(860px, 100%);
    max-height: 100%;
    overflow: auto;
    padding: 22px 26px 24px;
    border-radius: 20px;
    background: color-mix(in srgb, var(--popover-solid) 72%, transparent);
    backdrop-filter: saturate(160%) blur(26px);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 24px 60px rgb(0 0 0 / 0.35);
  }

  header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 14px;
  }

  .app-icon {
    flex: none;
    width: 44px;
    height: 44px;
    border-radius: 11px;
    display: grid;
    place-items: center;
    font: 700 19px/1 var(--font);
    color: white;
    background: linear-gradient(160deg, #5e9bff, #3a55e8 55%, #6a3fd8);
  }

  h2 {
    margin: 0;
    font-size: 17px;
  }

  .sub {
    margin: 2px 0 0;
    font-size: 12px;
    color: var(--secondary);
  }

  .close {
    margin-left: auto;
    align-self: flex-start;
    display: grid;
    place-items: center;
    width: 26px;
    height: 26px;
    border-radius: 7px;
    color: var(--secondary);
  }

  .close:hover {
    background: var(--hover);
  }

  section {
    padding: 12px 14px;
    border-radius: 11px;
    background: var(--surface);
    box-shadow: var(--card-shadow);
  }

  h3 {
    display: flex;
    align-items: center;
    gap: 7px;
    margin: 0 0 6px;
    font-size: 13px;
    color: var(--accent);
  }

  ul {
    margin: 0;
    padding-left: 16px;
  }

  li {
    margin: 4px 0;
    font-size: 12.5px;
    line-height: 1.45;
    user-select: text;
  }

  li :global(code) {
    font-size: 11.5px;
    padding: 0 4px;
    border-radius: 4px;
    background: var(--hover);
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }

  td {
    padding: 3px 0;
    border-bottom: 0.5px solid var(--separator);
  }

  .keys {
    text-align: right;
    color: var(--secondary);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
</style>
