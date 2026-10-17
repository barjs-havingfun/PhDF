<script lang="ts">
  import logo from "../assets/logo.png";
  // "How to use PhDF": a short tour of what PhDF is good for, opened from the ? button.
  import { fly } from "svelte/transition";
  import Icon from "./Icon.svelte";
  import { ui } from "./notify.svelte";
  import { kbd } from "./platform";

  let { onclose }: { onclose: () => void } = $props();

  const sections = [
    {
      icon: "sparkle",
      title: "Welcome to PhDF",
      items: [
        "A reader built for <b>deep reading</b>: your books, your notes and an AI side by side, in one calm window.",
        "It remembers where you stopped in every book, so you just open and keep going.",
        "Lost? Press <b>Ctrl+K</b> and type what you want to do. Every action is in there.",
      ],
      details: [
        "<b>Open</b> a PDF, an EPUB book or a Markdown note with <b>Ctrl+O</b>, from the start screen's <i>Recents</i> or from the <i>Library</i> (every book you've opened, with progress).",
        "<b>Ctrl+K</b> opens the command palette: type a few letters of any action (“zoom”, “book”, “split”), a recent file, <i>Go to page 120</i> or <i>Search …</i>.",
        "PhDF reopens your tabs and the exact spot in each book. Reopening a book shows a short <i>Where was I?</i> card with your latest highlight.",
        "<b>Settings</b> (⋯ → Settings): app font, your Obsidian vault, OCR languages, your AI agent and the terminal's font.",
        "This tour is always one click away: the <b>?</b> button in the toolbar.",
      ],
    },
    {
      icon: "doc",
      title: "Read your way",
      items: [
        "PDFs and EPUB books, one page at a time, two side by side, or <b>like a real book</b> with page turns.",
        "Open several books in tabs or side by side, and compare them without losing your place.",
        "Tints, a reading ruler and zen mode keep your eyes and your focus on the text.",
      ],
      details: [
        "<b>Zoom</b>: Ctrl+wheel or a touchpad pinch; click the % in the toolbar for a slider, an exact % and Fit Width / Fit Page.",
        "<b>Move around</b>: ← / → page by page, Home / End, <b>Ctrl+G</b> to go to a page, <b>Alt+← / Alt+→</b> back and forward after jumps. <b>Ctrl+F</b> searches (Enter / Shift+Enter for next / previous).",
        "<b>Sidebar</b> (<b>Ctrl+\\</b>): the book's chapters, page thumbnails and your bookmarks (<b>Ctrl+B</b> bookmarks a page).",
        "<b>Read menu → Pages</b>: Single, Two pages, or Cover alone (first page alone, like a printed book). <b>Read like a book</b> fills the window with one spread; turn with ← / →, Space or the round buttons; Esc closes it.",
        "<b>Tabs</b>: Ctrl+T / Ctrl+W / Ctrl+Tab. Drag a tab onto the left or right edge of a page to read side by side, or out of the window for a new one.",
        "<b>Links</b> open a small preview first: drag it by its top bar, zoom it, <i>Go to Page</i> or <i>Open Beside</i>. Right-click inside it to copy or take a note.",
        "<b>Read menu</b>: reading ruler (S / M / L), zen mode (<b>Ctrl+.</b>), full screen (<b>F11</b>), page tints. The moon button inverts pages for night reading.",
        "<b>EPUB</b>: Read → <i>E-book text size</i> lays the book out again in bigger or smaller text, and you stay at about the same place.",
      ],
    },
    {
      icon: "note",
      title: "Mark what matters",
      items: [
        "Select text to highlight it, or write right on the page with notes, text and a pen.",
        "Everything stays in the PDF itself, so any other PDF app sees your marks too.",
        "Made a mistake? <b>Ctrl+Z</b>. Happy with it? <b>Ctrl+S</b>.",
      ],
      details: [
        "<b>Select text</b> and a small menu appears: 5 highlight colors, underline, strikethrough, copy, copy with citation (<b>Ctrl+Shift+C</b>), <i>Note in MD</i>, <i>Send to Obsidian</i> and <i>Ask AI</i>. Right-click a selection for the same menu.",
        "<b>Toolbar tools</b>: sticky note, text box (font, size, bold) and pen (color and width bar). Click on the page to place; <b>Esc</b> goes back to selecting.",
        "<b>Change an annotation</b>: click it to recolor, comment or delete, or right-click it. Drag notes and text boxes to move them; click a drawing first, then drag it.",
        "<b>Right-click an empty spot</b> to add a note or text there, bookmark the page, copy the page as an image or park a thought.",
        "The <b>Annotations</b> panel lists everything by page, with search and color filters; click one to jump to it.",
        "<b>Save</b> with <b>Ctrl+S</b>: the tab shows <i>- Edited</i> until you do, and closing asks before throwing changes away. <b>Ctrl+Z / Ctrl+Y</b> undo and redo.",
        "<b>Scanned pages</b>: a bar offers <i>Recognize Text</i> (OCR) so you can select, search and highlight; Ctrl+S keeps the text in the PDF.",
        "E-books (EPUB) can't store marks inside the file, so there you copy, cite and take notes instead.",
      ],
    },
    {
      icon: "mdnote",
      title: "Think in your notes",
      items: [
        "Every book gets its own Markdown note, open next to the page.",
        "Send a quote to the note and it stays <b>linked</b>: one click takes you back to the exact spot in the book.",
        "Write in <b>Live</b> mode and see headings, lists, tasks and equations formatted as you type.",
      ],
      details: [
        "The <b>note button</b> opens <code>&lt;book&gt;.md</code> next to the PDF, beside the page. It saves by itself (<i>Saved ✓</i> at the bottom).",
        "<b>Note in MD</b> on a selection highlights it and adds a <b>pin</b> with the quote; write your thoughts under it. <i>Go to PDF ↗</i> on a pin jumps to the highlight, and clicking a highlight jumps to its pin.",
        "<b>Edit / Live / Preview</b>: Live shows the note formatted and reveals the Markdown only on the line you edit. Equations (<code>$x^2$</code>, <code>$$ … $$</code>) are typeset; click one to edit it.",
        "<b>Format bar</b>: text style (headings, quote, lists), bold, italic, highlight, code, math, comment, link, insert a table, callout, footnote, code or math block. Drag its grip to put it on any side.",
        "<b>Shortcuts</b>: Ctrl+B bold, Ctrl+I italic, Ctrl+E code, Ctrl+Shift+K link, Ctrl+Shift+X strikethrough, Ctrl+Shift+H highlight. Right-click for cut / copy / paste and more.",
        "<b>Text size</b>: Ctrl+wheel or the % in the note's status line. <b>Aa</b> sets the note's font, spacing and width.",
        "Click the <b>file name</b> to rename the note; it stays linked to its book. ⋯ → <i>Export Highlights to Note</i> collects all your highlights at the end of the note.",
        "The <b>Parking</b> tab next to <i>Note</i> lists the thoughts you parked while reading this book.",
      ],
    },
    {
      icon: "terminal",
      title: "Ask the AI",
      items: [
        "Bring your own AI (Claude, Codex, Gemini or another) into a terminal beside your book.",
        "Ask about a passage, a page, a chapter or the whole book: explanations, summaries, study questions, related research.",
        "PhDF hands the AI the text for you, so you can stay in the flow of reading.",
      ],
      details: [
        "Open the terminal with the terminal button (or <b>Ctrl+`</b>). The first time, choose your AI agent; from then on it starts by itself, in the book's folder, and asks whether to <b>continue your last session</b>.",
        "New to this? <i>How to</i> in the terminal's header shows how to install Claude Code, Codex or Gemini CLI on your computer, step by step.",
        "<b>Select text → Ask AI</b>: Explain, Summarize and Translate are sent at once; <i>My own question…</i> lets you type first.",
        "<b>✦ in the toolbar</b>: summarize the book or the chapter, explain the page, key ideas, study questions, <b>find similar research</b>, or your own question. <i>Read as Markdown</i> gives the AI a fast text copy of the book (prepared in the background).",
        "<b>Equations</b>: ▾ next to ✦ → <i>Equation → LaTeX</i>, draw a box around a formula, press OK, and insert the AI's LaTeX into your note.",
        "In a <b>note</b>, right-click → <i>Ask AI</i> about the selection or the whole note.",
        "<b>Terminal tabs</b>: + opens another one (e.g. a second AI); ⇅ puts the terminal below or above the note; drag its header to dock it at the bottom; <b>Aa</b> sets its font and size.",
      ],
    },
    {
      icon: "park",
      title: "Stay focused",
      items: [
        "A random thought while reading? <b>Park it</b> in two seconds and get straight back to the page.",
        "A pomodoro timer and an estimate of how long the chapter will take at <b>your</b> pace.",
        "Your reading time adds up on the start screen, so you can see your streak grow.",
      ],
      details: [
        "<b>Park a thought</b>: the Park button or <b>Ctrl+Shift+Space</b>, type, Enter, and you're back on the page. Thoughts are saved next to the book and listed in the note's <i>Parking</i> tab, where you tick them off later.",
        "<b>Focus menu</b>: a pomodoro (15 / 25 / 45 / 50 minutes, with breaks and a soft chime). The clock shows in the toolbar while it runs.",
        "PhDF learns your <b>reading pace</b> from real reading only (not skimming) and shows how long the chapter and the book will take.",
        "<b>Reading stats</b> on the start screen: today, this week, your streak and a 14-day chart.",
        "<b>Zen mode</b> (<b>Ctrl+.</b>) hides everything but the page; Esc brings it back.",
      ],
    },
    {
      icon: "grade",
      title: "Tools for real work",
      items: [
        "<b>PhDF Tools</b> rotates, reorders, merges, splits and extracts pages, and never touches your original.",
        "Scanned pages become searchable with one click (OCR).",
        "Teachers: grade a whole folder of exams in a row, with a grades table that fills itself.",
        "Your notes and quotes can go straight to Obsidian.",
      ],
      details: [
        "<b>PhDF Tools</b>: the shiny button on the start screen, or ⋯ → <i>PDF Tools…</i>. Select pages with click, Shift-click and Ctrl-click; drag them to reorder; rotate, duplicate, delete, add a blank page or insert another PDF; Ctrl+Z undoes.",
        "<b>Save Copy</b> writes <code>Book_phdfE.pdf</code> next to the original. <b>Extract</b> and <b>Split</b> (every N pages, at chapters or at chosen pages) write <code>Book_p_3-7_phdf.pdf</code>. If pages have annotations, PhDF asks whether to keep them.",
        "<b>OCR</b>: ⋯ → <i>Recognize Text</i> for every scanned page; pick languages in Settings (downloaded once).",
        "<b>Export</b>: ⋯ → <i>Export as Markdown</i> turns the book's text into Markdown, to a file or your Obsidian vault.",
        "<b>Obsidian</b>: choose your vault in Settings; <i>Send to Obsidian</i> adds a quote to the book's note in the vault; ⋯ → <i>Copy Note to Obsidian</i> copies the whole note.",
        "<b>Grading</b>: the Grade button asks for a folder of exams (subfolders too). Mark each with any tool; <i>Done</i> saves a copy into <code>graded/</code> and opens the next. The grades table beside it fills itself, and <i>CSV</i> exports it for Excel.",
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
    details = false;
  }

  /** The card's "Details": the full how-to, opened inside the card. */
  let details = $state(false);
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
      <img class="app-icon" src={logo} alt="PhDF" draggable="false" />
      <div>
        <h2>How to use PhDF</h2>
        <p class="sub">Everything you need in one minute.</p>
      </div>
      <button class="close" onclick={onclose} aria-label="Close"><Icon name="close" size={14} /></button>
    </header>

    <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
    <div class="stage">
    {#key card}
    <div class="card" onclick={() => go(1)} in:fly={{ x: 320 * dir, duration: ui.reduceMotion ? 0 : 320, opacity: 0 }} out:fly={{ x: -320 * dir, duration: ui.reduceMotion ? 0 : 320, opacity: 0 }}>
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
          <button class="details-btn" onclick={(e) => (e.stopPropagation(), (details = !details))} aria-expanded={details}>
            {details ? "Hide details" : "Details: how to use it"} <Icon name={details ? "up" : "down"} size={13} />
          </button>
          {#if details}
            <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
            <div class="details" onclick={(e) => e.stopPropagation()}>
              <ul>
                {#each s.details as line}
                  <li>{@html kbd(line)}</li>
                {/each}
              </ul>
            </div>
          {/if}
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
    border-radius: 20px;
  }

  .card {
    grid-area: 1 / 1;
    min-height: 420px;
    padding: 26px 30px;
    border-radius: 20px;
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

  .details-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin-top: 14px;
    padding: 6px 12px;
    border-radius: 9px;
    font-weight: 600;
    color: var(--accent);
    background: color-mix(in srgb, var(--accent) 12%, transparent);
  }

  .details-btn:hover {
    background: color-mix(in srgb, var(--accent) 20%, transparent);
  }

  /* The full how-to: scrolls inside the card, clicks here don't turn the card. */
  .details {
    max-height: 300px;
    overflow-y: auto;
    margin-top: 12px;
    padding: 12px 16px;
    border-radius: 13px;
    background: color-mix(in srgb, var(--hover) 70%, transparent);
    cursor: auto;
  }

  .card .details li {
    font-size: 14px;
    line-height: 1.55;
  }

  .card .details li + li {
    margin-top: 10px;
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
    border-radius: 9px;
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
    border-radius: 24px;
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
    display: block;
    filter: drop-shadow(0 6px 16px rgb(122 77 255 / 0.35));
    flex: none;
    width: 44px;
    height: 44px;
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
    border-radius: 9px;
    color: var(--secondary);
  }

  .close:hover {
    background: var(--hover);
  }

  section {
    padding: 12px 14px;
    border-radius: 14px;
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
    border-radius: 5px;
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
