// Per-document state for one open tab. Survives tab switches (the viewer remounts from it).
import {
  api,
  type FitMode,
  type OpenedDocument,
  type OutlineItem,
  type PdfLink,
  type Rect,
  type SearchHit,
  type TextLine,
} from "./api";

export interface Location {
  page: number;
  scroll: number; // 0..1 within the page
}

export interface Jump {
  page: number;
  y?: number | null; // PDF points from the top of the page
  scroll?: number; // or a 0..1 fraction
}

export interface FlatHit {
  page: number;
  rect: Rect;
}

let nextId = 1;

export class Tab {
  readonly id = nextId++;
  readonly doc: OpenedDocument;

  // Current view, written by the viewer while scrolling.
  page = $state(0);
  scroll = $state(0);
  zoom = $state(1);
  fit = $state<FitMode>("width");

  // Navigation history for links/outline/search jumps (not plain scrolling).
  back = $state<Location[]>([]);
  forward = $state<Location[]>([]);
  /** A jump the viewer should perform; it clears this once done. */
  pendingJump = $state<Jump | null>(null);

  outline = $state<OutlineItem[] | null>(null);

  searchQuery = $state("");
  searchHits = $state<FlatHit[]>([]);
  searchIndex = $state(-1);
  searching = $state(false);

  private textCache = new Map<number, Promise<TextLine[]>>();
  private linkCache = new Map<number, Promise<PdfLink[]>>();

  constructor(doc: OpenedDocument) {
    this.doc = doc;
    const { page, scroll, zoom, fit } = doc.position;
    this.page = Math.min(page, doc.info.page_count - 1);
    this.scroll = scroll;
    this.zoom = zoom;
    this.fit = fit;
    this.pendingJump = { page: this.page, scroll: this.scroll };
  }

  get pageCount() {
    return this.doc.info.page_count;
  }

  textLines(page: number): Promise<TextLine[]> {
    let p = this.textCache.get(page);
    if (!p) this.textCache.set(page, (p = api().then((py) => py.text_layer(this.doc.docId, page))));
    return p;
  }

  links(page: number): Promise<PdfLink[]> {
    let p = this.linkCache.get(page);
    if (!p) this.linkCache.set(page, (p = api().then((py) => py.links(this.doc.docId, page))));
    return p;
  }

  async loadOutline() {
    this.outline ??= await (await api()).outline(this.doc.docId);
  }

  /** Jump somewhere and remember where we were (for Back). */
  navigate(target: Jump) {
    const page = Math.max(0, Math.min(this.pageCount - 1, target.page));
    this.back.push({ page: this.page, scroll: this.scroll });
    this.forward = [];
    this.pendingJump = { ...target, page };
  }

  goBack() {
    const loc = this.back.pop();
    if (!loc) return;
    this.forward.push({ page: this.page, scroll: this.scroll });
    this.pendingJump = { page: loc.page, scroll: loc.scroll };
  }

  goForward() {
    const loc = this.forward.pop();
    if (!loc) return;
    this.back.push({ page: this.page, scroll: this.scroll });
    this.pendingJump = { page: loc.page, scroll: loc.scroll };
  }

  async search(query: string) {
    this.searchQuery = query;
    if (!query.trim()) {
      this.searchHits = [];
      this.searchIndex = -1;
      return;
    }
    this.searching = true;
    const hits: SearchHit[] = await (await api()).search(this.doc.docId, query);
    if (query !== this.searchQuery) return; // a newer search started meanwhile
    this.searching = false;
    this.searchHits = hits.flatMap((h) => h.rects.map((rect) => ({ page: h.page, rect })));
    // Start at the first hit at or after the current page.
    const first = this.searchHits.findIndex((h) => h.page >= this.page);
    this.searchIndex = this.searchHits.length ? Math.max(first, 0) : -1;
    this.showHit();
  }

  stepSearch(delta: number) {
    const n = this.searchHits.length;
    if (!n) return;
    this.searchIndex = (this.searchIndex + delta + n) % n;
    this.showHit();
  }

  clearSearch() {
    this.searchQuery = "";
    this.searchHits = [];
    this.searchIndex = -1;
  }

  private showHit() {
    const hit = this.searchHits[this.searchIndex];
    if (hit) this.pendingJump = { page: hit.page, y: Math.max(hit.rect[1] - 80, 0) };
  }
}
