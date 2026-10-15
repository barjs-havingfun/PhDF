// The AI terminal: one persistent xterm + shell per window. Panels (side / bottom dock) adopt its
// DOM element, so moving or collapsing the panel never restarts the shell or loses its scrollback.
import type { FitAddon } from "@xterm/addon-fit";
import type { Terminal } from "@xterm/xterm";
import { api } from "../api";
import { notify } from "../notify.svelte";

export type Dock = "side" | "bottom";

export const term = $state({
  open: false,
  dock: "side" as Dock,
  collapsed: false,
  sideFraction: 0.45, // terminal's share of the side column when the note is shown below it
  sideWidth: 0.4, // side column width (fraction of the pane) when no note is shown
  bottomHeight: 260, // px
  paneId: null as number | null, // pane whose side column hosts the terminal
  dragging: false,
  dropTarget: null as Dock | null,
  ai: null as string | null, // "claude" / "codex" when running
  ready: false, // xterm created (panels attach it once this is true)
  guideOpen: false, // the "How to set up an AI" sheet
});

export const HEADER_HEIGHT = 30;

let xterm: Terminal | null = null;
let fitAddon: FitAddon | null = null;
let host: HTMLDivElement | null = null;
let session: string | null = null;
let cwd: string | null = null;
let starting: Promise<void> | null = null;

// --- layout persistence -------------------------------------------------------------------------

let saveTimer: ReturnType<typeof setTimeout> | undefined;
export function saveLayout() {
  clearTimeout(saveTimer);
  const { dock, collapsed, sideFraction, sideWidth, bottomHeight } = term;
  saveTimer = setTimeout(
    () => api().then((py) => py.set_setting("terminal.layout", { dock, collapsed, sideFraction, sideWidth, bottomHeight })),
    400,
  );
}

export async function loadLayout() {
  const saved = await (await api()).get_setting<Partial<typeof term> | null>("terminal.layout", null);
  if (saved) Object.assign(term, saved);
}

// --- xterm + shell --------------------------------------------------------------------------------

function theme() {
  const css = getComputedStyle(document.documentElement);
  const v = (name: string) => css.getPropertyValue(name).trim();
  const dark = matchMedia("(prefers-color-scheme: dark)").matches;
  return {
    background: v("--surface") || (dark ? "#2c2c2e" : "#ffffff"),
    foreground: v("--text") || (dark ? "#f5f5f7" : "#1d1d1f"),
    cursor: v("--accent") || "#0a84ff",
    selectionBackground: "rgba(10, 132, 255, 0.35)",
  };
}

async function createXterm() {
  const [{ Terminal }, { FitAddon }] = await Promise.all([
    import("@xterm/xterm"),
    import("@xterm/addon-fit"),
    import("@xterm/xterm/css/xterm.css"),
  ]);
  host = document.createElement("div");
  host.className = "phdf-xterm";
  host.style.cssText = "position:absolute;inset:0;padding:4px 0 0 8px;";
  xterm = new Terminal({
    fontFamily: '"Cascadia Mono", "Cascadia Code", Consolas, "SF Mono", Menlo, monospace',
    fontSize: 13,
    cursorBlink: true,
    scrollback: 5000,
    allowProposedApi: false,
    theme: theme(),
  });
  fitAddon = new FitAddon();
  xterm.loadAddon(fitAddon);
  xterm.onData((data) => {
    if (session) api().then((py) => py.term_write(session!, data));
    else if (data === "\r") restart();
  });
  xterm.onResize(({ cols, rows }) => {
    if (session) api().then((py) => py.term_resize(session!, cols, rows));
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (xterm) xterm.options.theme = theme();
  });
}

async function startShell() {
  const py = await api();
  const { cols, rows } = xterm!;
  session = await py.term_start(cwd, cols, rows);
  const id = session;
  (async () => {
    while (session === id) {
      const r = await py.term_read(id, 0.5);
      if (r.data) xterm?.write(r.data);
      if (!r.alive) {
        if (session === id) {
          session = null;
          term.ai = null;
          xterm?.write("\r\n\x1b[2m[shell exited — press Enter to start a new one]\x1b[0m\r\n");
        }
        break;
      }
    }
  })();
}

/** Make sure the terminal exists and its shell runs (started in `folder` the first time). */
export async function ensureTerminal(folder: string | null) {
  if (session && xterm) return;
  starting ??= (async () => {
    if (!xterm) await createXterm();
    term.ready = true;
    cwd = folder;
    await startShell();
  })();
  try {
    await starting;
  } finally {
    starting = null;
  }
}

export async function restart() {
  if (session) {
    const old = session;
    session = null;
    (await api()).term_close(old);
  }
  xterm?.reset();
  await startShell();
}

/** Put the terminal into `container` (called by whichever panel currently shows it). */
export function attach(container: HTMLElement) {
  if (!host || !xterm) return;
  if (host.parentElement !== container) container.appendChild(host);
  if (!xterm.element) xterm.open(host);
  refit();
}

export function refit() {
  requestAnimationFrame(() => {
    if (host?.isConnected && host.clientWidth > 0 && host.clientHeight > 0) fitAddon?.fit();
  });
}

export function focusTerminal() {
  xterm?.focus();
}

export async function openTerminal(folder: string | null, paneId: number | null) {
  await ensureTerminal(folder); // create it first, so the panel has something to show
  term.open = true;
  term.collapsed = false;
  if (term.dock === "side" && paneId !== null) term.paneId = paneId;
  saveLayout();
  setTimeout(focusTerminal, 50);
}

// --- talking to the AI ------------------------------------------------------------------------------

export async function runningAi(): Promise<string | null> {
  if (!session) return null;
  term.ai = await (await api()).term_ai(session);
  return term.ai;
}

/** Paste text as one block (bracketed paste, so newlines don't submit early); Enter optional. */
async function paste(text: string, submit: boolean) {
  if (!xterm) return;
  xterm.paste(text);
  if (submit) {
    await new Promise((r) => setTimeout(r, 120));
    if (session) (await api()).term_write(session, "\r");
  }
  focusTerminal();
}

/** Start an AI CLI in the terminal and wait until it is running. */
async function startAi(command: "claude" | "codex"): Promise<boolean> {
  if (!session) return false;
  (await api()).term_write(session, command + "\r");
  for (let i = 0; i < 30; i++) {
    await new Promise((r) => setTimeout(r, 1000));
    if (await runningAi()) {
      await new Promise((r) => setTimeout(r, 2500)); // let its prompt appear
      return true;
    }
  }
  notify.error(`“${command}” did not start — is it installed and on PATH?`);
  return false;
}

/**
 * Send text to the AI running in the terminal. If none runs, ask which one to start first — the
 * text must never land in the plain shell, where it would run as commands.
 */
export async function askAi(text: string, submit: boolean, folder: string | null, paneId: number | null) {
  await openTerminal(folder, paneId);
  if (await runningAi()) return paste(text, submit);
  const go = (command: "claude" | "codex") => async () => {
    if (await startAi(command)) await paste(text, submit);
  };
  notify.show(
    {
      text: "No AI is running in the terminal. Start one:",
      action: { label: "Claude", run: go("claude") },
      action2: { label: "Codex", run: go("codex") },
    },
    20000,
  );
}

/** Type a command into the terminal without running it (the user presses Enter). */
export async function typeIntoTerminal(command: string) {
  if (!term.open) await openTerminal(cwd, null);
  else await ensureTerminal(cwd);
  if (session) (await api()).term_write(session, command);
  focusTerminal();
}

export async function closeTerminal() {
  term.open = false;
  saveLayout();
}
