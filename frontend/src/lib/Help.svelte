<script lang="ts">
  // "How to use PhDF": a short tour of every feature, opened from the ? button.
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
        "Select text to <b>highlight</b>, underline, strike through, copy — or send it to a note or the AI.",
        "Toolbar: sticky <b>note</b>, free <b>text</b> and <b>draw</b> tools; the list button shows every annotation.",
        "Click an annotation to recolour, comment or delete it (<b>Delete</b> also works); <b>Ctrl+Z</b> undoes. Save into the PDF with <b>Ctrl+S</b>.",
        "<b>Drag</b> a sticky note or text box to move it; to move a drawing, click it first, then drag.",
        "Text boxes: pick <b>Sans / Serif / Mono</b>, the size and <b>B</b>old when you place one — or click a box later to change them.",
        "<b>Ctrl+B</b> bookmarks a page (list in the sidebar's <i>Marks</i>); ⋯ → <i>Export Highlights to Note</i> collects every highlight under a line at the end of the book's note.",
        "Scanned page? A bar offers <i>Recognize Text</i> (OCR) so you can select and search it.",
      ],
    },
    {
      icon: "mdnote",
      title: "The book's note",
      items: [
        "The note button opens <code>&lt;book&gt;.md</code> next to the PDF, beside the page.",
        "<i>Note in MD</i> on a selection adds a pin <code>⎘ phdf · p.12 · #id</code> with the quote — write under it.",
        "Click <i>Go to PDF ↗</i> on a pin to jump to the highlight; click a highlight to jump to its pin.",
        "<b>Aa</b> sets the note's font, size and spacing.",
      ],
    },
    {
      icon: "park",
      title: "Parking lot",
      items: [
        "Stray thought while reading? The 💡 <i>Park</i> button next to Read/Focus (or <b>Ctrl+Shift+Space</b>), type, Enter — and you're back on the page.",
        "Thoughts go to <code>&lt;book&gt;.parking.md</code> and show in the note's <i>Parking</i> tab.",
      ],
    },
    {
      icon: "book",
      title: "Read & Focus",
      items: [
        "<i>Read</i>: a reading ruler, zen mode (<b>Ctrl+.</b>), full screen (<b>F11</b>) and page tints — each on its own.",
        "<i>Focus</i>: a pomodoro timer and how long the chapter / book will take at your pace.",
      ],
    },
    {
      icon: "grade",
      title: "Grading exams",
      items: [
        "The <i>Grade</i> button (next to <b>?</b>) asks for a folder of exam PDFs — subfolders too, e.g. a Moodle download. They open one by one; mark them with any tool.",
        "<i>Done</i> saves and opens the next exam, <i>Prev</i> goes back; the sidebar's <i>Exams</i> list jumps anywhere. The originals are never changed: the marked copies go to <code>graded/</code>.",
        "Beside the exam: the folder's grades table <code>&lt;folder&gt;.grades.md</code> (<i>#, Name, Grade, Comment</i> — add your own columns).",
        "<i>Automated</i> on: a drawer asks who wrote each exam, and the grade typed next to Done (Enter = Done) goes into the table. Off: fill the table yourself. <i>CSV</i> exports it.",
      ],
    },
    {
      icon: "terminal",
      title: "AI terminal",
      items: [
        "<b>Ctrl+`</b> (or the terminal button) opens a shell in the PDF's folder. Type <code>claude</code> or <code>codex</code>. New to this? <i>How to</i> in the terminal's header walks you through installing them.",
        "It sits above the note; drag the line between them to resize, click its header to fold it away, drag the header (or ⇩) to dock it at the bottom.",
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
</script>

<svelte:window onkeydown={(e) => e.key === "Escape" && onclose()} />

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={(e) => e.target === e.currentTarget && onclose()}>
  <div class="sheet" role="dialog" aria-label="How to use PhDF">
    <header>
      <div class="app-icon">Ph</div>
      <div>
        <h2>How to use PhDF</h2>
        <p class="sub">A two-minute tour. Press Esc to close.</p>
      </div>
      <button class="close" onclick={onclose} aria-label="Close"><Icon name="close" size={14} /></button>
    </header>

    <div class="grid">
      {#each sections as s}
        <section>
          <h3><Icon name={s.icon as never} size={15} /> {s.title}</h3>
          <ul>
            {#each s.items as item}
              <!-- static, trusted strings written above -->
              <li>{@html kbd(item)}</li>
            {/each}
          </ul>
        </section>
      {/each}
      <section>
        <h3><Icon name="help" size={15} /> Shortcuts</h3>
        <table>
          <tbody>
            {#each shortcuts as [what, keys]}
              <tr><td>{what}</td><td class="keys">{kbd(keys)}</td></tr>
            {/each}
          </tbody>
        </table>
      </section>
    </div>
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 70;
    display: grid;
    place-items: center;
    padding: 24px;
    background: rgb(0 0 0 / 0.25);
  }

  .sheet {
    width: min(900px, 100%);
    max-height: 100%;
    overflow: auto;
    padding: 18px 22px 22px;
    border-radius: 16px;
    background: var(--popover-solid);
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

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 12px;
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
