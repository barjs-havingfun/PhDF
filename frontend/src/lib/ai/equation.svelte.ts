// Page areas for the AI in the terminal. A rectangle drawn on the page is saved as a PNG in a
// temp folder where the terminal runs.
// - Equation → LaTeX: the AI writes the LaTeX to a file next to it, which is polled. Both files
//   are deleted as soon as the answer arrives (or on cancel).
// - Image → AI: the AI gets the image with the user's question and answers in the terminal. The
//   PNG is deleted IMAGE_KEEP_MS later (the AI may still be busy), or when the window closes.
import { api, type Rect } from "../api";
import { notify } from "../notify.svelte";
import type { Tab } from "../tab.svelte";
import { askAi, ensureTerminal, term, terminalFolder } from "./terminal.svelte";

export type SnipKind = "equation" | "image";

export interface EqJob {
  kind: SnipKind;
  page: number;
  rect: Rect;
  /** Where the preview box appears (screen coordinates). */
  at: { x: number; y: number };
  status: "confirm" | "preparing" | "waiting" | "done" | "error"; // confirm: shown, OK not pressed yet
  latex: string;
  error: string;
  png: string;
  tex: string;
}

const POLL_MS = 700;
const TIMEOUT_MS = 4 * 60_000;
const IMAGE_KEEP_MS = 15 * 60_000;

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

/** A rectangle was drawn: show it in the box and wait for OK (`confirmEquation`). */
export function startEquation(tab: Tab, page: number, rect: Rect, at: { x: number; y: number }, paneId: number, kind: SnipKind = "equation") {
  cancelEquation(tab);
  const job = $state<EqJob>({ kind, page, rect, at, status: "confirm", latex: "", error: "", png: "", tex: "" });
  tab.equation = job;
  confirmPane = paneId;
}

let confirmPane = 0;

/** OK pressed: render the region, ask the AI in the terminal and wait for its LaTeX. */
export async function confirmEquation(tab: Tab) {
  const job = tab.equation;
  if (!job || job.status !== "confirm") return;
  const { page, rect } = job;
  const paneId = confirmPane;
  job.status = "preparing";
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
      `Convert it to LaTeX and write ONLY the LaTeX source into the file "${files.tex}": no $ or \\[ \\] delimiters, no code fences, no explanation. Do nothing else.`;
    await askAi(prompt, true, folderOf(tab.path), paneId);
    await poll(tab, job);
  } catch (e) {
    job.status = "error";
    job.error = String(e);
  }
}

/** Image → AI: send the area with the question; the AI answers in the terminal. */
export async function sendImage(tab: Tab, question: string) {
  const job = tab.equation;
  if (!job || job.kind !== "image" || job.status !== "confirm") return;
  const paneId = confirmPane;
  job.status = "preparing";
  try {
    const py = await api();
    await ensureTerminal(folderOf(tab.path));
    const files = await py.equation_snip(tab.doc.docId, job.page, job.rect, terminalFolder(), "image");
    if (tab.equation !== job) return void py.equation_cleanup(files.png); // cancelled meanwhile
    const ask = question.trim() || "Explain what this shows.";
    const prompt =
      `Look at the image file "${files.png}". It is an area cropped from page ${job.page + 1} of the PDF “${tab.title}” (file: ${tab.path}). ` +
      `${ask} Answer here; don't change any files.`;
    await askAi(prompt, true, folderOf(tab.path), paneId);
    tab.equation = null;
    setTimeout(() => py.equation_cleanup(files.png), IMAGE_KEEP_MS);
    notify.show({ text: "Image sent to the AI in the terminal." }, 2500);
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
    job.error = term.ai ? "The AI did not answer in time." : "No AI answered. Start your AI agent in the terminal and try again.";
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
