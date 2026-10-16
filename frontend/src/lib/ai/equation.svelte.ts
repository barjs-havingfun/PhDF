// Equation → LaTeX through the AI in the terminal. A rectangle drawn on the page is saved as a
// PNG in a temp folder where the terminal runs; the AI is asked to write the LaTeX to a file
// next to it, which is polled. Both files are deleted as soon as the answer arrives (or on cancel).
import { api, type Rect } from "../api";
import { notify } from "../notify.svelte";
import type { Tab } from "../tab.svelte";
import { askAi, ensureTerminal, term, terminalFolder } from "./terminal.svelte";

export interface EqJob {
  page: number;
  rect: Rect;
  /** Where the preview box appears (screen coordinates). */
  at: { x: number; y: number };
  status: "preparing" | "waiting" | "done" | "error";
  latex: string;
  error: string;
  png: string;
  tex: string;
}

const POLL_MS = 700;
const TIMEOUT_MS = 4 * 60_000;

const folderOf = (path: string) => path.replace(/[\\/][^\\/]*$/, "");

/** Strip what an AI may add around the LaTeX: code fences, $$ … $$, \[ … \], \( … \). */
export function cleanLatex(raw: string): string {
  let s = raw.trim().replace(/^```[a-z]*\s*\n?/i, "").replace(/\n?```\s*$/, "").trim();
  for (const [open, close] of [["$$", "$$"], ["\\[", "\\]"], ["\\(", "\\)"], ["$", "$"]]) {
    if (s.startsWith(open) && s.endsWith(close) && s.length > open.length + close.length) {
      s = s.slice(open.length, s.length - close.length).trim();
      break;
    }
  }
  return s;
}

export async function startEquation(tab: Tab, page: number, rect: Rect, at: { x: number; y: number }, paneId: number) {
  cancelEquation(tab);
  const job = $state<EqJob>({ page, rect, at, status: "preparing", latex: "", error: "", png: "", tex: "" });
  tab.equation = job;
  try {
    const py = await api();
    // The files go where the AI runs, so Claude Code / Codex may read and write them.
    await ensureTerminal(folderOf(tab.path));
    const files = await py.equation_snip(tab.doc.docId, page, rect, terminalFolder());
    job.png = files.png;
    job.tex = files.tex;
    if (tab.equation !== job) return void py.equation_cleanup(files.png); // cancelled meanwhile
    job.status = "waiting";
    const prompt =
      `Look at the image file "${files.png}". It shows a mathematical formula cropped from page ${page + 1} of the PDF “${tab.title}”. ` +
      `Convert it to LaTeX and write ONLY the LaTeX source into the file "${files.tex}" — no $ or \\[ \\] delimiters, no code fences, no explanation. Do nothing else.`;
    await askAi(prompt, true, folderOf(tab.path), paneId);
    await poll(tab, job);
  } catch (e) {
    job.status = "error";
    job.error = String(e);
  }
}

async function poll(tab: Tab, job: EqJob) {
  const py = await api();
  const started = Date.now();
  let last: string | null = null;
  while (tab.equation === job && Date.now() - started < TIMEOUT_MS) {
    await new Promise((r) => setTimeout(r, POLL_MS));
    const text = await py.equation_result(job.tex);
    // Take it once it stops changing (the file may be written in pieces).
    if (text && text === last) {
      job.latex = cleanLatex(text);
      job.status = "done";
      py.equation_cleanup(job.png); // no leftovers in the user's folder
      return;
    }
    last = text;
  }
  if (tab.equation === job) {
    job.status = "error";
    job.error = term.ai ? "The AI did not answer in time." : "No AI answered — start Claude or Codex in the terminal and try again.";
    py.equation_cleanup(job.png);
  }
}

/** Close the preview (and stop waiting); the temp files are removed. */
export function cancelEquation(tab: Tab) {
  const job = tab.equation;
  tab.equation = null;
  if (job?.png) api().then((py) => py.equation_cleanup(job.png));
}

/** Put the equation as a $$ block (with its page) at the cursor in the side note. */
export async function insertEquation(tab: Tab, latex: string) {
  const job = tab.equation;
  if (!job) return;
  const md = await tab.ensureMd();
  tab.mdView = "note";
  tab.mdOpen = true;
  md.insertBlock(`$$\n${latex.trim()}\n$$\n*p. ${job.page + 1}*`);
  cancelEquation(tab);
  notify.show({ text: "Equation added to the note." }, 1800);
}
