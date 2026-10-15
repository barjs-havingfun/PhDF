// Pointer-based tab dragging. Pointer capture keeps events coming even outside the window,
// which is how a tab dropped outside is detected (→ new window).
import type { AnyTab as Tab } from "./tab.svelte";

export type DropTarget =
  | { kind: "bar"; paneId: number; index: number } // reorder / move into a tab bar
  | { kind: "split"; paneId: number; side: "left" | "right" } // new pane beside a pane
  | { kind: "into"; paneId: number } // move into a pane (end of its tabs)
  | { kind: "window"; screenX: number; screenY: number }; // dropped outside: new window

const THRESHOLD = 6; // px before a press becomes a drag
const SPLIT_EDGE = 0.3; // outer 30% of a pane splits it

class DragState {
  tab = $state<Tab | null>(null);
  x = $state(0);
  y = $state(0);
  target = $state<DropTarget | null>(null);
  /** Set briefly after a drop so the tab's click handler ignores the release. */
  suppressClick = false;
}

export const drag = new DragState();

export interface DragHooks {
  /** Filter out targets that are not allowed (e.g. a fourth pane). */
  accept: (tab: Tab, target: DropTarget) => boolean;
  drop: (tab: Tab, target: DropTarget) => void;
}

function hitTest(x: number, y: number, screenX: number, screenY: number): DropTarget | null {
  if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) return { kind: "window", screenX, screenY };
  const els = document.elementsFromPoint(x, y) as HTMLElement[];

  const bar = els.find((el) => el.dataset.paneBar);
  if (bar) {
    const tabs = [...bar.querySelectorAll<HTMLElement>("[data-tab-id]")];
    const index = tabs.filter((t) => {
      const r = t.getBoundingClientRect();
      return r.left + r.width / 2 < x;
    }).length;
    return { kind: "bar", paneId: Number(bar.dataset.paneBar), index };
  }

  const body = els.find((el) => el.dataset.paneBody);
  if (body) {
    const paneId = Number(body.dataset.paneBody);
    const r = body.getBoundingClientRect();
    const rel = (x - r.left) / r.width;
    if (rel < SPLIT_EDGE) return { kind: "split", paneId, side: "left" };
    if (rel > 1 - SPLIT_EDGE) return { kind: "split", paneId, side: "right" };
    return { kind: "into", paneId };
  }
  return null;
}

/** Capture the pointer so moves outside the window still arrive (no-op for synthetic events). */
export function capture(el: HTMLElement, pointerId: number) {
  try {
    el.setPointerCapture(pointerId);
  } catch {
    // not an active pointer (e.g. scripted tests)
  }
}

export function startTabDrag(e: PointerEvent, tab: Tab, hooks: DragHooks) {
  if (e.button !== 0) return;
  const el = e.currentTarget as HTMLElement;
  const startX = e.clientX;
  const startY = e.clientY;
  let dragging = false;

  capture(el, e.pointerId);

  const move = (ev: PointerEvent) => {
    if (!dragging) {
      if (Math.hypot(ev.clientX - startX, ev.clientY - startY) < THRESHOLD) return;
      dragging = true;
      drag.tab = tab;
    }
    drag.x = ev.clientX;
    drag.y = ev.clientY;
    const target = hitTest(ev.clientX, ev.clientY, ev.screenX, ev.screenY);
    drag.target = target && hooks.accept(tab, target) ? target : null;
  };

  const end = (ev: PointerEvent) => {
    el.removeEventListener("pointermove", move);
    el.removeEventListener("pointerup", end);
    el.removeEventListener("pointercancel", end);
    if (el.hasPointerCapture?.(ev.pointerId)) el.releasePointerCapture(ev.pointerId);
    if (!dragging) return;
    const target = ev.type === "pointerup" ? drag.target : null;
    drag.tab = null;
    drag.target = null;
    drag.suppressClick = true;
    setTimeout(() => (drag.suppressClick = false));
    if (target) hooks.drop(tab, target);
  };

  el.addEventListener("pointermove", move);
  el.addEventListener("pointerup", end);
  el.addEventListener("pointercancel", end);
}
