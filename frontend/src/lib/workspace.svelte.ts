// Window layout: up to MAX_PANES side-by-side panes, each with its own tabs.
import type { AnyTab, Tab } from "./tab.svelte";

export const MAX_PANES = 3;

let nextPaneId = 1;

export class Pane {
  readonly id = nextPaneId++;
  tabs = $state<AnyTab[]>([]);
  /** Active tab id, or null for the "new tab" page. */
  activeId = $state<number | null>(null);
  /** Relative width (flex-grow). */
  width = $state(1);

  get active(): AnyTab | null {
    return this.tabs.find((t) => t.id === this.activeId) ?? null;
  }
}

export type SplitSide = "left" | "right";

export class Workspace {
  panes = $state<Pane[]>([new Pane()]);
  focusedId = $state(0);

  constructor() {
    this.focusedId = this.panes[0].id;
  }

  get focused(): Pane {
    return this.panes.find((p) => p.id === this.focusedId) ?? this.panes[0];
  }

  get activeTab(): AnyTab | null {
    return this.focused.active;
  }

  get tabCount(): number {
    return this.panes.reduce((n, p) => n + p.tabs.length, 0);
  }

  pane(id: number): Pane | undefined {
    return this.panes.find((p) => p.id === id);
  }

  paneOf(tab: AnyTab): Pane | undefined {
    return this.panes.find((p) => p.tabs.includes(tab));
  }

  /** The open PDF tab for a document (matched by id, or by path after a save changed it). */
  findPdf(docId: string, path: string): Tab | undefined {
    for (const p of this.panes) {
      for (const t of p.tabs) {
        if (t.kind === "pdf" && (t.doc.docId === docId || t.path === path)) return t;
      }
    }
  }

  findByPath(path: string): AnyTab | undefined {
    for (const p of this.panes) {
      const t = p.tabs.find((t) => t.path === path);
      if (t) return t;
    }
  }

  allTabs(): AnyTab[] {
    return this.panes.flatMap((p) => p.tabs);
  }

  focus(pane: Pane) {
    this.focusedId = pane.id;
  }

  activate(tab: AnyTab) {
    const pane = this.paneOf(tab);
    if (!pane) return;
    pane.activeId = tab.id;
    this.focus(pane);
  }

  add(tab: AnyTab, pane: Pane = this.focused, index = pane.tabs.length) {
    pane.tabs.splice(index, 0, tab);
  }

  /** Remove a tab; activates a neighbour and drops the pane if it became empty. */
  remove(tab: AnyTab) {
    const pane = this.paneOf(tab);
    if (!pane) return;
    const i = pane.tabs.indexOf(tab);
    pane.tabs.splice(i, 1);
    if (pane.activeId === tab.id) pane.activeId = (pane.tabs[i] ?? pane.tabs[i - 1])?.id ?? null;
    this.prune();
  }

  /** Move a tab into `to` at `index` (reordering when `to` is its own pane). */
  move(tab: AnyTab, to: Pane, index: number) {
    const from = this.paneOf(tab);
    if (!from) return;
    const i = from.tabs.indexOf(tab);
    if (from === to && (index === i || index === i + 1)) return this.activate(tab);
    from.tabs.splice(i, 1);
    if (from.activeId === tab.id) from.activeId = (from.tabs[i] ?? from.tabs[i - 1])?.id ?? null;
    if (from === to && index > i) index--;
    to.tabs.splice(index, 0, tab);
    this.prune();
    this.activate(tab);
  }

  canSplit(tab: AnyTab, target: Pane): boolean {
    const from = this.paneOf(tab);
    if (!from || this.panes.length >= MAX_PANES) return false;
    return !(from === target && from.tabs.length === 1); // nothing would be left behind
  }

  /** Put a tab in a new pane next to `target`. */
  split(tab: AnyTab, target: Pane, side: SplitSide) {
    if (!this.canSplit(tab, target)) return;
    const pane = new Pane();
    pane.width = target.width / 2;
    target.width /= 2;
    const at = this.panes.indexOf(target) + (side === "right" ? 1 : 0);
    this.panes.splice(at, 0, pane);
    this.move(tab, pane, 0);
  }

  /** Show a (new) tab in a pane beside `target`, or in its neighbour at the pane limit. */
  placeBeside(tab: AnyTab, target: Pane) {
    if (this.panes.length < MAX_PANES) {
      const pane = new Pane();
      pane.width = target.width / 2;
      target.width /= 2;
      this.panes.splice(this.panes.indexOf(target) + 1, 0, pane);
      pane.tabs.push(tab);
    } else {
      const i = this.panes.indexOf(target);
      (this.panes[i + 1] ?? this.panes[i - 1] ?? target).tabs.push(tab);
    }
    this.activate(tab);
  }

  private prune() {
    if (this.panes.length > 1) {
      const empty = this.panes.filter((p) => p.tabs.length === 0);
      for (const p of empty) {
        const i = this.panes.indexOf(p);
        const neighbour = this.panes[i + 1] ?? this.panes[i - 1];
        if (neighbour) neighbour.width += p.width;
        this.panes.splice(i, 1);
      }
    }
    if (!this.pane(this.focusedId)) this.focusedId = this.panes[0].id;
  }
}
