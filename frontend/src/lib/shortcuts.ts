// Window-wide keyboard shortcuts. App hands over what they act on; this file only maps keys.
import { ui } from "./notify.svelte";
import { arrowStep, read, stepRow } from "./reading.svelte";
import type { AnyTab, Tab } from "./tab.svelte";
import type Viewer from "./viewer/Viewer.svelte";

export interface ShortcutContext {
  active: Tab | null; // focused PDF
  current: AnyTab | null; // focused tab of any kind
  viewer: () => Viewer | undefined;
  dialogOpen: boolean; // a sheet handles its own keys (Escape, Enter)
  peekOpen: boolean;
  parkingOpen: boolean;
  toggleTerminal: () => void;
  toggleParking: () => void;
  toggleZen: () => void;
  toggleFullscreen: () => void;
  pickAndOpen: () => void;
  saveCurrent: () => void;
  togglePalette: () => void;
  undo: () => void;
  redo: () => void;
  toggleBookmark: () => void;
  copyWithCitation: () => void;
  newTab: () => void;
  closeTab: (tab: AnyTab) => void;
  cycleTab: (delta: number) => void;
  focusSearch: () => void;
  startGoto: () => void;
  toggleSidebar: () => void;
}

export function inTextField(e: KeyboardEvent) {
  const el = e.target as HTMLElement;
  return el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable;
}

export function handleShortcut(e: KeyboardEvent, x: ShortcutContext) {
  const mod = e.ctrlKey || e.metaKey;
  const key = e.key.toLowerCase();
  const active = x.active;
  let handled = true;

  // Terminal toggle works everywhere; other shortcuts stay out of the terminal's way.
  if (mod && (e.code === "Backquote" || key === "`")) {
    e.preventDefault();
    return x.toggleTerminal();
  }
  if ((e.target as HTMLElement).closest?.(".xterm")) return;
  if (e.defaultPrevented) return; // handled by the note editor (Ctrl+= zoom, Ctrl+E code…)
  if (x.dialogOpen) return;
  const typing = inTextField(e);

  if (mod && e.shiftKey && (key === " " || e.code === "Space")) x.toggleParking();
  else if (mod && key === ".") x.toggleZen();
  else if (key === "f11" || (e.metaKey && e.ctrlKey && key === "f")) x.toggleFullscreen(); // ⌃⌘F on a Mac
  else if (key === "escape" && read.zen && !x.peekOpen && !x.parkingOpen) x.toggleZen();
  else if (mod && key === "o") x.pickAndOpen();
  else if (mod && key === "s") x.saveCurrent();
  else if (mod && key === "k") x.togglePalette();
  else if (mod && !e.shiftKey && key === "z" && active && !typing) x.undo();
  else if (mod && (key === "y" || (e.shiftKey && key === "z")) && active && !typing) x.redo();
  else if (mod && key === "b" && active && !typing) x.toggleBookmark();
  else if (mod && e.shiftKey && key === "c" && active && !typing && getSelection()?.toString()) x.copyWithCitation();
  else if (mod && key === "p" && active) ui.print = true;
  else if (mod && key === "t") x.newTab();
  else if (mod && key === "w") x.current && x.closeTab(x.current);
  else if (key === "escape" && active && active.tool !== "select") active.tool = "select";
  else if (mod && key === "tab") x.cycleTab(e.shiftKey ? -1 : 1);
  else if (mod && key === "f" && active && !typing) x.focusSearch();
  else if (mod && key === "g" && active && !typing) x.startGoto();
  else if (mod && (key === "=" || key === "+") && active && !typing) x.viewer()?.zoomBy(1.2);
  else if (mod && key === "-" && active && !typing) x.viewer()?.zoomBy(1 / 1.2);
  else if (mod && key === "0" && active && !typing) x.viewer()?.setZoom(1);
  else if (mod && key === "\\") x.toggleSidebar();
  else if (!typing && ((e.altKey && key === "arrowleft") || (e.metaKey && key === "["))) active?.goBack(); // ⌘[ ⌘] on a Mac
  else if (!typing && e.metaKey && key === "]") active?.goForward();
  else if (!typing && e.altKey && key === "arrowright") active?.goForward();
  else if (active && !mod && !e.altKey && !typing && !x.peekOpen) {
    const step = arrowStep(key, active.rtl);
    if (step) active.pendingJump = { page: stepRow(active.page, step, active.pageCount) };
    else if (key === "home") active.navigate({ page: 0 });
    else if (key === "end") active.navigate({ page: active.pageCount - 1 });
    else handled = false;
  } else handled = false;

  if (handled) e.preventDefault();
}
