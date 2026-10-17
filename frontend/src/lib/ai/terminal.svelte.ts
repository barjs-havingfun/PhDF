// The AI terminal: one or more terminal tabs per window, each its own xterm + shell. Panels (side /
// bottom dock) adopt their DOM elements, so moving or collapsing the panel never restarts a shell
// or loses its scrollback. Only the active tab is shown; the others keep running.
import type { FitAddon } from "@xterm/addon-fit";
import type { Terminal } from "@xterm/xterm";
import { api } from "../api";
import { notify } from "../notify.svelte";
import { isWindows } from "../platform";

export type Dock = "side" | "bottom";

/** What the header shows for a terminal tab. */
export interface TermTab {
  id: number;
  name: string; // "Shell 2"
  ai: string | null; // "claude" / "codex" when running
}

export const term = $state({
  open: false,
  dock: "side" as Dock,
  collapsed: false,
  sideFraction: 0.45, // terminal's share of the side column when the note is shown with it
  below: false, // side dock: the terminal below the note instead of above it
  sideWidth: 0.4, // side column width (fraction of the pane) when no note is shown
  bottomHeight: 260, // px
  paneId: null as number | null, // pane whose side column hosts the terminal
  dragging: false,
  dropTarget: null as Dock | null,
  tabs: [] as TermTab[],
  active: null as number | null, // id of the shown tab
  ai: null as string | null, // AI running in the active tab
  ready: false, // a terminal exists (panels attach it once this is true)
  guideOpen: false, // the "How to set up an AI" sheet
  /** Default AI agent: a command ("claude", "codex", the user's own), "" for a plain shell,
   *  null until the user has chosen. New terminals start it by themselves. */
  agent: null as string | null,
  agentAsk: false, // the "Add an AI agent" card is shown in the panel
  pickFor: null as number | null, // a tab opened with + that asks which agent to start
  /** Asking before an agent starts: continue its last session (`flag`) or a new one. */
  resumeAsk: null as { id: number; name: string; flag: string } | null,
  font: { name: "Default", size: 13 }, // terminal font (TERM_FONTS name) and size, remembered
  docFolder: null as string | null, // folder of the focused document (set by App)
});

const AGENT_NAMES: Record<string, string> = { claude: "Claude Code", codex: "Codex", gemini: "Gemini CLI" };

/** "Claude Code" for "claude", else the command itself. */
export function agentLabel(command: string | null): string {
  if (!command) return "Shell only";
  return AGENT_NAMES[command.trim()] ?? command.trim();
}

export const HEADER_HEIGHT = 30;

/** The parts of a terminal tab that are not reactive state. */
interface Shell {
  xterm: Terminal;
  fit: FitAddon;
  host: HTMLDivElement;
  session: string | null;
  cwd: string | null;
  output: boolean; // the shell has printed something (its prompt is up)
  agentStart: Promise<boolean> | null; // the default agent is being started in it
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

const shells = new Map<number, Shell>();
let nextId = 1;
let container: HTMLElement | null = null; // the panel body currently showing the terminals
let starting: Promise<void> | null = null;

const activeShell = () => (term.active !== null ? shells.get(term.active) : undefined);
const tabOf = (id: number) => term.tabs.find((t) => t.id === id);

// --- layout persistence -------------------------------------------------------------------------

let saveTimer: ReturnType<typeof setTimeout> | undefined;
export function saveLayout() {
  clearTimeout(saveTimer);
  const { dock, collapsed, sideFraction, sideWidth, bottomHeight, below } = term;
  saveTimer = setTimeout(
    () => api().then((py) => py.set_setting("terminal.layout", { dock, collapsed, sideFraction, sideWidth, bottomHeight, below })),
    400,
  );
}

export async function loadLayout() {
  const saved = await (await api()).get_setting<Partial<typeof term> | null>("terminal.layout", null);
  if (saved) {
    const { dock, collapsed, sideFraction, sideWidth, bottomHeight, below = false } = saved;
    Object.assign(term, { dock, collapsed, sideFraction, sideWidth, bottomHeight, below });
  }
  const font = await (await api()).get_setting<typeof term.font | null>("terminal.font", null);
  if (font) await setFont(font, false);
}

// --- font ---------------------------------------------------------------------------------------------

const FALLBACK = '"Cascadia Mono", "Cascadia Code", Consolas, "SF Mono", Menlo, "DejaVu Sans Mono", "Ubuntu Mono", "Liberation Mono", monospace';

/** Font choices; one that is not installed falls back to the default list. */
export const TERM_FONTS = [
  { name: "Default", family: FALLBACK },
  { name: "Cascadia Mono", family: `"Cascadia Mono", ${FALLBACK}` },
  { name: "Consolas", family: `Consolas, ${FALLBACK}` },
  { name: "JetBrains Mono", family: `"JetBrains Mono", ${FALLBACK}` }, // bundled
  { name: "Courier New", family: `"Courier New", ${FALLBACK}` },
  { name: "SF Mono / Menlo", family: `"SF Mono", Menlo, ${FALLBACK}` },
  { name: "DejaVu Sans Mono", family: `"DejaVu Sans Mono", ${FALLBACK}` },
];
export const TERM_SIZES = { min: 9, max: 28 };

/** Change the terminals' font and / or size (all tabs), remembered. */
export async function setFont(change: Partial<typeof term.font>, save = true) {
  const next = { ...term.font, ...change };
  next.size = Math.min(TERM_SIZES.max, Math.max(TERM_SIZES.min, Math.round(next.size)));
  if (!TERM_FONTS.some((f) => f.name === next.name)) next.name = "Default";
  if (next.name === "JetBrains Mono") {
    await import("@fontsource/jetbrains-mono/400.css");
    await document.fonts.load(`${next.size}px "JetBrains Mono"`).catch(() => {});
  }
  term.font = next;
  const family = TERM_FONTS.find((f) => f.name === next.name)!.family;
  for (const s of shells.values()) {
    s.xterm.options.fontFamily = family;
    s.xterm.options.fontSize = next.size;
  }
  refit();
  if (save) (await api()).set_setting("terminal.font", next);
}

// --- folder ---------------------------------------------------------------------------------------------

/** Move the terminal to `folder` (the open PDF's): `cd` in the shown shell, or, when an AI runs
 *  there (it would read the command as a prompt), a new terminal tab in that folder. */
export async function goToFolder(folder: string) {
  const shell = activeShell();
  if (!shell?.session || term.active === null) return newTab(folder);
  if (await runningAi()) {
    await newTab(folder);
    notify.show({ text: "An AI runs in that terminal, so a new one was opened in the PDF's folder." }, 3500);
    return;
  }
  await changeFolder(shell, folder);
  focusTerminal();
}

/** `cd` the shell into `folder` (quoted for PowerShell or a POSIX shell). */
async function changeFolder(shell: Shell, folder: string) {
  if (!shell.session) return;
  const command = isWindows
    ? `Set-Location -LiteralPath '${folder.replace(/'/g, "''")}'`
    : `cd '${folder.replace(/'/g, `'\\''`)}'`;
  (await api()).term_write(shell.session, command + "\r");
  shell.cwd = folder;
}

// --- continue the last session? ---------------------------------------------------------------------

/** How each known agent resumes its last session in the current folder. */
// Checked against the CLIs' own help (Codex 0.163, Gemini CLI 0.64); re-check when they update.
const RESUME: Record<string, string> = { claude: "--continue", codex: "resume --last", gemini: "--resume latest" };

let resumeAnswer: ((answer: boolean | null) => void) | null = null;

/** Ask (bar at the bottom of the tab) whether to continue the last session; null = cancelled. */
function askResume(id: number, command: string): Promise<boolean | null> {
  resumeAnswer?.(null);
  return new Promise((resolve) => {
    term.resumeAsk = { id, name: agentLabel(command), flag: RESUME[command.trim().split(/\s+/)[0].toLowerCase()] };
    resumeAnswer = (answer) => {
      term.resumeAsk = null;
      resumeAnswer = null;
      resolve(answer);
    };
  });
}

/** The resume bar's buttons: true = continue, false = new session, null = cancel. */
export function answerResume(answer: boolean | null) {
  resumeAnswer?.(answer);
  setTimeout(focusTerminal, 50);
}

// --- xterm + shell --------------------------------------------------------------------------------

function theme() {
  const css = getComputedStyle(document.documentElement);
  const v = (name: string) => css.getPropertyValue(name).trim();
  const dark = css.colorScheme === "dark";
  return {
    background: v("--surface") || (dark ? "#2c2c2e" : "#ffffff"),
    foreground: v("--text") || (dark ? "#f5f5f7" : "#1d1d1f"),
    cursor: v("--accent") || "#0a84ff",
    selectionBackground: "rgba(10, 132, 255, 0.35)",
  };
}

let themeWatched = false;

async function createShell(id: number, cwd: string | null): Promise<Shell> {
  const [{ Terminal }, { FitAddon }] = await Promise.all([
    import("@xterm/xterm"),
    import("@xterm/addon-fit"),
    import("@xterm/xterm/css/xterm.css"),
  ]);
  const host = document.createElement("div");
  host.className = "phdf-xterm";
  host.style.cssText = "position:absolute;inset:0;padding:4px 0 0 8px;";
  const xterm = new Terminal({
    fontFamily: TERM_FONTS.find((f) => f.name === term.font.name)?.family ?? FALLBACK,
    fontSize: term.font.size,
    cursorBlink: true,
    scrollback: 5000,
    allowProposedApi: false,
    theme: theme(),
  });
  const fit = new FitAddon();
  xterm.loadAddon(fit);
  const shell: Shell = { xterm, fit, host, session: null, cwd, output: false, agentStart: null };
  xterm.onData((data) => {
    if (term.pickFor === id && data.includes("\r")) term.pickFor = null; // typed a command: no question
    if (shell.session) api().then((py) => py.term_write(shell.session!, data));
    else if (data === "\r") restartShell(id);
  });
  xterm.onResize(({ cols, rows }) => {
    if (shell.session) api().then((py) => py.term_resize(shell.session!, cols, rows));
  });
  if (!themeWatched) {
    themeWatched = true;
    // Theme changed (OS or Settings): the CSS colors are already new.
    addEventListener("phdf:theme", () => {
      for (const s of shells.values()) s.xterm.options.theme = theme();
    });
  }
  return shell;
}

async function startShell(id: number) {
  const shell = shells.get(id);
  if (!shell) return;
  const py = await api();
  const { cols, rows } = shell.xterm;
  const sessionId = await py.term_start(shell.cwd, cols, rows);
  shell.session = sessionId;
  shell.output = false;
  (async () => {
    while (shell.session === sessionId) {
      const r = await py.term_read(sessionId, 0.5);
      if (r.data) {
        shell.xterm.write(r.data);
        shell.output = true;
      }
      if (!r.alive) {
        if (shell.session === sessionId) {
          shell.session = null;
          const tab = tabOf(id);
          if (tab) tab.ai = null;
          if (term.active === id) term.ai = null;
          shell.xterm.write("\r\n\x1b[2m[shell exited: press Enter to start a new one]\x1b[0m\r\n");
        }
        break;
      }
    }
  })();
}

/** Show the active tab's terminal in the panel body (the others stay there, hidden). */
function showActive() {
  for (const [id, shell] of shells) {
    shell.host.style.display = id === term.active ? "" : "none";
    // A panel that was closed leaves a detached body behind; the next panel attaches again.
    if (!container?.isConnected) continue;
    if (shell.host.parentElement !== container) container.appendChild(shell.host);
    if (!shell.xterm.element) shell.xterm.open(shell.host);
  }
  term.ai = term.active !== null ? (tabOf(term.active)?.ai ?? null) : null;
  refit();
}

/** Add a terminal tab running a new shell in `folder` and show it; `autoStart` starts the
 *  default agent in it. */
async function addTab(folder: string | null, autoStart = true): Promise<number> {
  const id = nextId++;
  const shell = await createShell(id, folder);
  shells.set(id, shell);
  term.tabs.push({ id, name: `Shell ${id}`, ai: null });
  term.active = id;
  term.ready = true;
  showActive();
  await startShell(id);
  if (autoStart && term.agent) {
    // Not awaited: the panel shows the shell at once; askAi waits for this when it needs the AI.
    const start = startAi(term.agent, id);
    shell.agentStart = start;
    start.finally(() => shell.agentStart === start && (shell.agentStart = null));
  }
  return id;
}

/** The folder of the shell that gets AI requests (null: the backend used the home folder). */
export function terminalFolder(): string | null {
  return target()?.cwd ?? null;
}

/** Make sure a terminal exists and its shell runs (the first one starts in `folder`). */
export async function ensureTerminal(folder: string | null) {
  const shell = activeShell();
  if (shell?.session) return;
  starting ??= (async () => {
    if (!shell) await addTab(folder);
    else await startShell(term.active!);
  })();
  try {
    await starting;
  } finally {
    starting = null;
  }
}

/** A new terminal tab (+), in the same folder as the one shown (or `folder`). It opens a plain
 *  shell and asks which installed agent to start in it (`term.pickFor`). */
export async function newTab(folder: string | null = activeShell()?.cwd ?? null) {
  term.pickFor = await addTab(folder, false);
  setTimeout(focusTerminal, 50);
}

/** The new tab's question answered: start `command` in it, or "" for just the shell. */
export function startInNewTab(command: string) {
  const id = term.pickFor;
  term.pickFor = null;
  if (command && id !== null) startAi(command, id);
  setTimeout(focusTerminal, 50);
}

export function activateTab(id: number) {
  if (!shells.has(id)) return;
  term.active = id;
  showActive();
  setTimeout(focusTerminal, 50);
}

/** Close a terminal tab and its shell; the panel hides when the last one closes. */
export async function closeTab(id: number) {
  const shell = shells.get(id);
  if (!shell) return;
  const i = term.tabs.findIndex((t) => t.id === id);
  shells.delete(id);
  term.tabs.splice(i, 1);
  if (term.active === id) term.active = (term.tabs[i] ?? term.tabs[i - 1])?.id ?? null;
  if (term.pickFor === id) term.pickFor = null;
  if (term.resumeAsk?.id === id) answerResume(null);
  const session = shell.session;
  shell.session = null; // stops its reader loop
  shell.xterm.dispose();
  shell.host.remove();
  if (!term.tabs.length) {
    term.ready = false;
    closeTerminal();
  }
  showActive();
  if (session) (await api()).term_close(session);
}

async function restartShell(id: number) {
  const shell = shells.get(id);
  if (!shell) return;
  if (shell.session) {
    const old = shell.session;
    shell.session = null;
    (await api()).term_close(old);
  }
  const tab = tabOf(id);
  if (tab) tab.ai = null;
  if (term.active === id) term.ai = null;
  shell.xterm.reset();
  await startShell(id);
}

/** Restart the shell of the tab that is shown. */
export async function restart() {
  if (term.active !== null) await restartShell(term.active);
}

/** Put the terminals into `el` (called by whichever panel currently shows them). */
export function attach(el: HTMLElement) {
  container = el;
  showActive();
}

export function refit() {
  requestAnimationFrame(() => {
    const shell = activeShell();
    if (shell?.host.isConnected && shell.host.clientWidth > 0 && shell.host.clientHeight > 0) shell.fit.fit();
  });
}

export function focusTerminal() {
  activeShell()?.xterm.focus();
}

export async function openTerminal(folder: string | null, paneId: number | null) {
  await loadAgent(); // a new shell starts the default agent
  await ensureTerminal(folder); // create it first, so the panel has something to show
  term.open = true;
  term.collapsed = false;
  if (term.dock === "side" && paneId !== null) term.paneId = paneId;
  if (term.agent === null) term.agentAsk = true; // first time: which AI agent?
  saveLayout();
  setTimeout(focusTerminal, 50);
}

// --- the default agent ------------------------------------------------------------------------------

let agentLoaded: Promise<void> | null = null;

export function loadAgent(): Promise<void> {
  agentLoaded ??= api()
    .then((py) => py.get_setting<string | null>("ai.agent", null))
    .then((saved) => void (term.agent = saved ?? null));
  return agentLoaded;
}

export async function setAgent(command: string) {
  term.agent = command.trim();
  (await api()).set_setting("ai.agent", term.agent);
}

/** Waiting for the user to pick an agent (an Ask AI request that came first). */
let pendingAsk: (() => Promise<void>) | null = null;

/** The "Add an AI agent" card: save the choice, then start it (or send what was waiting). */
export async function chooseAgent(command: string) {
  await setAgent(command);
  term.agentAsk = false;
  const pending = pendingAsk;
  pendingAsk = null;
  if (!term.agent) return; // a plain shell
  if (pending) return pending();
  if (!(await runningAi())) await startAi(term.agent);
}

export function dismissAgentAsk() {
  term.agentAsk = false;
  pendingAsk = null;
}

// --- talking to the AI ------------------------------------------------------------------------------

/** Check which AI runs in each tab; returns the one in the tab that is shown. */
export async function runningAi(): Promise<string | null> {
  const py = await api();
  await Promise.all(
    term.tabs.map(async (tab) => {
      const session = shells.get(tab.id)?.session;
      tab.ai = session ? await py.term_ai(session) : null;
    }),
  );
  term.ai = term.active !== null ? (tabOf(term.active)?.ai ?? null) : null;
  return term.ai;
}

/** The tab that gets AI requests: the one shown, or else one where an AI already runs. */
function targetTab(): TermTab | undefined {
  return term.tabs.find((t) => t.id === term.active && t.ai) ?? term.tabs.find((t) => t.ai);
}

function target(): Shell | undefined {
  const tab = targetTab();
  return tab ? shells.get(tab.id) : activeShell();
}

/** Paste text as one block (bracketed paste, so newlines don't submit early); Enter optional. */
async function paste(text: string, submit: boolean) {
  const shell = activeShell();
  if (!shell) return;
  shell.xterm.paste(text);
  if (submit) {
    await new Promise((r) => setTimeout(r, 120));
    if (shell.session) (await api()).term_write(shell.session, "\r");
  }
  focusTerminal();
}

/** Start an AI CLI in a terminal tab (the shown one by default) and wait until it is running.
 *  First the shell goes to the open document's folder (agents keep their sessions per folder),
 *  then, for agents that can, the user picks: continue the last session or a new one. */
async function startAi(command: string, id = term.active): Promise<boolean> {
  const shell = id !== null ? shells.get(id) : undefined;
  if (!shell?.session || id === null) return false;
  for (let i = 0; i < 30 && !shell.output; i++) await sleep(100); // until the prompt is up
  if (term.docFolder && term.docFolder !== shell.cwd) await changeFolder(shell, term.docFolder);
  let line = command;
  const flag = RESUME[command.trim().split(/\s+/)[0].toLowerCase()];
  if (flag) {
    const resume = await askResume(id, command);
    if (resume === null || !shells.get(id)?.session) return false;
    if (resume) line = `${command} ${flag}`;
  }
  (await api()).term_write(shell.session!, line + "\r");
  for (let i = 0; i < 30; i++) {
    await sleep(1000);
    if (!shells.has(id)) return false; // its tab was closed
    await runningAi();
    if (tabOf(id)?.ai) {
      await sleep(2500); // let its prompt appear
      return true;
    }
  }
  notify.show({
    text: `“${command}” did not start. Is it installed and on PATH?`,
    error: true,
    action: { label: "How to", run: () => (term.guideOpen = true) },
  });
  return false;
}

/**
 * Send text to the AI running in the terminal. If the shown tab runs none but another tab does,
 * that tab is used. If none runs, the default agent is started first (chosen on the spot the first
 * time): the text must never land in the plain shell, where it would run as commands.
 */
export async function askAi(text: string, submit: boolean, folder: string | null, paneId: number | null) {
  await openTerminal(folder, paneId);
  await runningAi();
  let withAi = targetTab();
  const starting = activeShell()?.agentStart;
  if (!withAi && starting) {
    if (!(await starting)) return; // it did not start: the error says so
    withAi = targetTab();
  }
  if (withAi) {
    if (withAi.id !== term.active) activateTab(withAi.id);
    return paste(text, submit);
  }
  const send = async () => {
    if (term.agent && (await startAi(term.agent))) await paste(text, submit);
  };
  if (term.agent) return send();
  pendingAsk = send; // after the user picks an agent on the card
  term.agentAsk = true;
}

/** Type a command into the terminal without running it (the user presses Enter). */
export async function typeIntoTerminal(command: string) {
  const folder = activeShell()?.cwd ?? null;
  if (!term.open) await openTerminal(folder, null);
  else await ensureTerminal(folder);
  const session = activeShell()?.session;
  if (session) (await api()).term_write(session, command);
  focusTerminal();
}

export async function closeTerminal() {
  term.open = false;
  saveLayout();
}
