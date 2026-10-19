// The command palette's commands (Ctrl+K). App hands over what they act on; this file only
// says which commands exist when, and what they do.
import type { RecentDocument } from "./api";
import { newTab as newTerminalTab, openTerminal, term } from "./ai/terminal.svelte";
import type { Command } from "./CommandPalette.svelte";
import { grading } from "./grading/grading.svelte";
import { ui } from "./notify.svelte";
import { pausePomodoro, pomodoro, read, saveReadSettings, startPomodoro, TINTS, type Tint } from "./reading.svelte";
import type { Tab } from "./tab.svelte";
import type Viewer from "./viewer/Viewer.svelte";
import type { FitMode } from "./api";

export interface CommandContext {
  active: Tab | null; // focused PDF
  invert: boolean;
  recents: RecentDocument[];
  docFolder: string | null; // the focused document's folder (terminal)
  paneId: number;
  viewer: () => Viewer | undefined;
  saveCurrent: () => void;
  undo: () => void;
  redo: () => void;
  toggleBookmark: () => void;
  showBookmarks: () => void;
  exportHighlights: () => void;
  exportMarkdown: (target: "file" | "vault") => void;
  copyNoteToVault: () => void;
  recognizeAll: () => void;
  setFit: (mode: FitMode) => void;
  toggleInvert: () => void;
  toggleSidebar: () => void;
  startGrading: () => void;
  stopGrading: () => void;
  toggleZen: () => void;
  toggleFullscreen: () => void;
  park: () => void;
  toggleTerminal: () => void;
  openAiMenu: () => void;
  startSnip: (kind?: "equation" | "image") => void;
  pickAndOpen: () => void;
  newNote: () => void;
  newTab: () => void;
  openPath: (path: string) => void;
}

function setTint(tint: Tint) {
  read.tint = tint;
  saveReadSettings();
}

export function appCommands(x: CommandContext): Command[] {
  const c: Command[] = [];
  const add = (group: string, title: string, run: () => void, keys?: string) =>
    c.push({ id: `${group}:${title}`, group, title, run, keys });
  const pdf = x.active;
  if (pdf) {
    add("Document", "Save annotations", x.saveCurrent, "Ctrl+S");
    add("Document", "Undo", x.undo, "Ctrl+Z");
    add("Document", "Redo", x.redo, "Ctrl+Y");
    add("Document", pdf.isBookmarked(pdf.page) ? "Remove bookmark" : "Bookmark this page", x.toggleBookmark, "Ctrl+B");
    add("Document", "Show bookmarks", x.showBookmarks);
    add("Document", "Print…", () => (ui.print = true), "Ctrl+P");
    for (const b of pdf.bookmarks) {
      add("Bookmarks", `${b.label || "Bookmark"} (p. ${b.page + 1})`, () => pdf.navigate({ page: b.page }));
    }
    add("Document", "Export highlights to note", x.exportHighlights);
    add("Document", "Export as Markdown…", () => x.exportMarkdown("file"));
    add("Document", "Export to Obsidian vault", () => x.exportMarkdown("vault"));
    add("Document", "Copy note to Obsidian", x.copyNoteToVault);
    add("Document", "Recognize text (OCR)", x.recognizeAll);
    add("Document", "Go to first page", () => pdf.navigate({ page: 0 }), "Home");
    add("Document", "Go to last page", () => pdf.navigate({ page: pdf.pageCount - 1 }), "End");
    add("Annotate", "Add note", () => (pdf.tool = "note"));
    add("Annotate", "Add text", () => (pdf.tool = "text"));
    add("Annotate", "Draw", () => (pdf.tool = "draw"));
    add("View", "Toggle annotations panel", () => (pdf.panelOpen = !pdf.panelOpen));
    add("View", "Toggle integrated note", () => pdf.toggleMd());
    add("View", "Show parking lot", () => pdf.showParking());
    add("View", "Zoom in", () => x.viewer()?.zoomBy(1.2), "Ctrl++");
    add("View", "Zoom out", () => x.viewer()?.zoomBy(1 / 1.2), "Ctrl+-");
    add("View", "Fit width", () => x.setFit("width"));
    add("View", "Fit page", () => x.setFit("page"));
    add("View", "Actual size", () => x.setFit("none"), "Ctrl+0");
    add("View", x.invert ? "Light pages" : "Dark pages", x.toggleInvert);
  }
  add("View", "Toggle sidebar", x.toggleSidebar, "Ctrl+\\");
  const g = grading.session;
  if (g) {
    add("Grading", "Done, next exam", () => g.next());
    add("Grading", "Previous exam", () => g.prev());
    add("Grading", "Export grades as CSV", () => g.exportCsv());
    add("Grading", "Stop grading", x.stopGrading);
  } else add("Grading", "Grade a folder of exams…", x.startGrading);
  add("Read & Focus", read.ruler ? "Hide reading ruler" : "Show reading ruler", () => ((read.ruler = !read.ruler), saveReadSettings()));
  if (pdf) add("Read & Focus", "Read like a book (two pages)", () => (read.book = true));
  add("Read & Focus", "Zen mode", x.toggleZen, "Ctrl+.");
  add("Read & Focus", "Full screen", x.toggleFullscreen, "F11");
  for (const [key, t] of Object.entries(TINTS)) add("Read & Focus", `Page tint: ${t.label}`, () => setTint(key as Tint));
  add("Read & Focus", pomodoro.running ? "Pause pomodoro" : "Start pomodoro", () => (pomodoro.running ? pausePomodoro() : startPomodoro()));
  add("Read & Focus", "Park a thought", x.park, "Ctrl+Shift+Space");
  add("AI", term.open ? "Hide terminal" : "Open terminal", x.toggleTerminal, "Ctrl+`");
  add("AI", "New terminal tab", async () => {
    if (!term.tabs.length) return openTerminal(x.docFolder, x.paneId);
    await newTerminalTab(x.docFolder);
    await openTerminal(x.docFolder, x.paneId);
  });
  add("AI", "How to set up an AI agent (Claude Code, Codex, Gemini…)", () => (term.guideOpen = true));
  if (pdf) add("AI", "Ask the AI about this document…", x.openAiMenu);
  if (pdf) add("AI", "Image → AI: send an area of the page", () => x.startSnip("image"));
  if (pdf) add("AI", "Equation → LaTeX (AI)", () => x.startSnip("equation"));
  add("App", "Open…", x.pickAndOpen, "Ctrl+O");
  add("App", "New note…", x.newNote);
  add("App", "PhDF Tools: rotate, reorder, merge, split, extract pages…", () => (ui.tools = { path: pdf?.path ?? null }));
  add("App", "New tab", x.newTab, "Ctrl+T");
  add("App", "Settings", () => (ui.settingsOpen = true));
  add("App", "How to use PhDF", () => (ui.helpOpen = true));
  for (const r of x.recents) add("Recent", r.title ?? r.path, () => x.openPath(r.path));
  return c;
}

/** Commands made from what was typed: a page number, or text to search for. */
export function typedCommands(q: string, pdf: Tab | null): Command[] {
  const out: Command[] = [];
  if (pdf && /^\d+$/.test(q)) {
    const n = Math.min(Math.max(Number(q), 1), pdf.pageCount);
    out.push({ id: "goto", group: "Go to", title: `Go to page ${n}`, run: () => pdf.navigate({ page: n - 1 }) });
  }
  if (pdf && q.length >= 2 && !/^\d+$/.test(q)) {
    out.push({ id: "search", group: "Search", title: `Search “${q}” in this document`, run: () => void pdf.search(q) });
  }
  return out;
}
