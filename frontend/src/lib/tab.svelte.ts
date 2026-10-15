// Tabs. A PDF tab (`Tab`) keeps its view, history, search, annotations and integrated note;
// a Markdown tab (`MdTab`) is a standalone note. Both survive tab switches and pane moves.
import {
  api,
  type AnnotChange,
  type AnnotKind,
  type Annotation,
  type FitMode,
  type OpenedDocument,
  type OutlineItem,
  type PdfLink,
  type Point,
  type Rect,
  type Revs,
  type SearchHit,
  type TextLine,
} from "./api";
import { MdDoc } from "./md.svelte";
import { pinBlock, sectionFor } from "./pin";

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

export type Tool = "select" | "note" | "text" | "draw";

export const INK_COLOR = "#0a84ff";

let nextId = 1;

export class Tab {
  readonly kind = "pdf" as const;
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

  // Annotations (unsaved until Ctrl+S).
  annotations = $state<Annotation[] | null>(null);
  selectedAnnot = $state<string | null>(null);
  dirty = $state(false);
  revs = $state<Revs>({});
  tool = $state<Tool>("select");
  panelOpen = $state(false);

  // OCR for pages without text (scans).
  noTextPages = $state<number[] | null>(null);
  /** Per-page "has a text layer", checked lazily as pages are viewed. */
  hasText = $state<Record<number, boolean>>({});
  scanningText = $state(false);
  ocrProgress = $state<{ done: number; total: number } | null>(null);
  private ocrCancel = false;

  // Integrated Markdown note shown beside the PDF in this tab.
  md = $state<MdDoc | null>(null);
  mdOpen = $state(false);
  mdWidth = $state(0.42);
  /** Which file the side panel shows: the integrated note or this document's parking lot. */
  mdView = $state<"note" | "parking">("note");
  parking = $state<MdDoc | null>(null);
  /** Ask the note editor to scroll to a pin: { id, nonce }. */
  mdReveal = $state<{ id: string; nonce: number; focus?: boolean } | null>(null);

  private textCache = new Map<number, Promise<TextLine[]>>();
  private linkCache = new Map<number, Promise<PdfLink[]>>();

  constructor(doc: OpenedDocument) {
    this.doc = doc;
    const { page, scroll, zoom, fit } = doc.position;
    this.page = Math.min(page, doc.info.page_count - 1);
    this.scroll = scroll;
    this.zoom = zoom;
    this.fit = fit;
    this.dirty = doc.dirty;
    this.revs = doc.revs;
    this.pendingJump = { page: this.page, scroll: this.scroll };
  }

  get title() {
    return this.doc.title;
  }

  get path() {
    return this.doc.path;
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

  // --- navigation -----------------------------------------------------------------------------

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

  // --- search ---------------------------------------------------------------------------------

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

  // --- annotations ----------------------------------------------------------------------------

  async loadAnnotations() {
    this.annotations ??= await (await api()).annotations(this.doc.docId);
  }

  private apply(change: AnnotChange) {
    this.dirty = change.dirty;
    this.revs = change.revs;
  }

  async addAnnotation(
    page: number,
    kind: AnnotKind,
    rects: Rect[],
    color: string,
    contents = "",
    strokes: Point[][] | null = null,
  ) {
    await this.loadAnnotations();
    const change = await (await api()).add_annotation(
      this.doc.docId, page, kind, rects, color, contents, strokes,
    ); // prettier-ignore
    this.apply(change);
    this.annotations!.push(change.annotation!);
    return change.annotation!;
  }

  async updateAnnotation(id: string, color?: string | null, contents?: string | null) {
    const change = await (await api()).update_annotation(this.doc.docId, id, color, contents);
    this.apply(change);
    const i = this.annotations?.findIndex((a) => a.id === id) ?? -1;
    if (i >= 0 && change.annotation) this.annotations![i] = change.annotation;
    return change.annotation!;
  }

  async deleteAnnotation(id: string) {
    const change = await (await api()).delete_annotation(this.doc.docId, id);
    this.apply(change);
    this.annotations = this.annotations?.filter((a) => a.id !== id) ?? null;
    if (this.selectedAnnot === id) this.selectedAnnot = null;
  }

  async save() {
    if (this.dirty) this.apply({ ...(await (await api()).save_document(this.doc.docId)) });
    await this.md?.flush();
  }

  /** Scroll to an annotation and select it. */
  async reveal(id: string, fallbackPage?: number) {
    await this.loadAnnotations();
    const annot = this.annotations!.find((a) => a.id === id);
    if (annot) {
      this.navigate({ page: annot.page, y: Math.max(annot.rects[0][1] - 60, 0) });
      this.selectedAnnot = id;
    } else if (fallbackPage !== undefined) {
      this.navigate({ page: fallbackPage });
    }
  }

  // --- integrated note ------------------------------------------------------------------------

  async ensureMd(): Promise<MdDoc> {
    if (!this.md) {
      const { path } = await (await api()).md_for_pdf(this.doc.path);
      const md = new MdDoc(path, `# ${this.title}\n\n`);
      await md.load();
      this.md = md;
    }
    return this.md;
  }

  async toggleMd(open = !this.mdOpen) {
    if (open) {
      await this.ensureMd();
      this.ensureParking(); // for the Parking tab's badge
    }
    this.mdOpen = open;
  }

  async ensureParking(): Promise<MdDoc> {
    if (!this.parking) {
      const path = await (await api()).parking_path(this.doc.path);
      const doc = new MdDoc(path, `# Parking Lot — ${this.title}\n\nThoughts parked while reading in PhDF.\n\n`);
      await doc.load();
      this.parking = doc;
    }
    return this.parking;
  }

  /** Open the side panel on the Parking tab. */
  async showParking() {
    await Promise.all([this.ensureMd(), this.ensureParking()]);
    this.mdView = "parking";
    this.mdOpen = true;
  }

  async setMdView(view: "note" | "parking") {
    if (view === "parking") await this.ensureParking();
    this.mdView = view;
  }

  /** Something was parked: refresh the Parking tab if it is loaded. */
  async parkingChanged() {
    if (this.parking && !this.parking.dirty) await this.parking.load();
  }

  async linkExistingMd(path: string) {
    await (await api()).link_md(this.doc.path, path);
    if (this.md) await this.md.switchTo(path);
    else await this.ensureMd();
  }

  /** "Note in MD": add a pin for an annotation to the note and show it. */
  async noteInMd(annot: Annotation) {
    const md = await this.ensureMd();
    await this.loadOutline();
    if (!md.text.includes(`#${annot.id}`)) md.append(pinBlock(annot, sectionFor(this.outline, annot.page)));
    this.mdOpen = true;
    this.mdReveal = { id: annot.id, nonce: Date.now(), focus: true }; // write right under it
  }

  hasPin(id: string) {
    return !!this.md?.text.includes(`· #${id}`);
  }

  /** Send a pin + quote for an annotation to this book's note in the Obsidian vault. */
  async sendToObsidian(annot: Annotation): Promise<string> {
    await this.loadOutline();
    return (await api()).obsidian_append(this.title, pinBlock(annot, sectionFor(this.outline, annot.page)));
  }

  /** The document's text converted to Markdown (only the text: notes live in the .md note). */
  async exportMarkdown(): Promise<string> {
    return (await (await api()).export_markdown(this.doc.docId)).trimEnd() + "\n";
  }

  // --- OCR ------------------------------------------------------------------------------------

  async checkText(page: number) {
    if (page in this.hasText) return;
    this.hasText[page] = await (await api()).page_has_text(this.doc.docId, page);
  }

  /** Full scan for pages without text — only when asked (slow on big documents). */
  async loadNoTextPages() {
    if (this.noTextPages) return;
    this.scanningText = true;
    try {
      this.noTextPages = await (await api()).pages_without_text(this.doc.docId);
      for (const p of this.noTextPages) this.hasText[p] = false;
    } finally {
      this.scanningText = false;
    }
  }

  /** Recognize text on `pages`, one at a time; can be stopped with `stopOcr`. */
  async runOcr(pages: number[], languages: string[]) {
    if (this.ocrProgress) return;
    this.ocrCancel = false;
    this.ocrProgress = { done: 0, total: pages.length };
    try {
      for (const page of pages) {
        if (this.ocrCancel) break;
        const change = await (await api()).ocr_page(this.doc.docId, page, languages);
        this.apply(change);
        this.textCache.delete(page); // the page has a text layer now
        this.noTextPages = this.noTextPages?.filter((p) => p !== page) ?? null;
        if (change.words > 0) this.hasText[page] = true;
        this.ocrProgress = { done: this.ocrProgress.done + 1, total: pages.length };
      }
    } finally {
      this.ocrProgress = null;
    }
  }

  stopOcr() {
    this.ocrCancel = true;
  }
}

/** A standalone Markdown note in its own tab. */
export class MdTab {
  readonly kind = "md" as const;
  readonly id = nextId++;
  readonly md: MdDoc;

  constructor(md: MdDoc) {
    this.md = md;
  }

  get title() {
    return this.md.name.replace(/\.md$/i, "");
  }

  get path() {
    return this.md.path;
  }

  get dirty() {
    return false; // notes autosave
  }
}

export type AnyTab = Tab | MdTab;
