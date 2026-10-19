// Tabs. A PDF tab (`Tab`) keeps its view, history, search, annotations and integrated note;
// a Markdown tab (`MdTab`) is a standalone note. Both survive tab switches and pane moves.
import {
  api,
  type AnnotChange,
  type AnnotKind,
  type Annotation,
  type FitMode,
  type OpenedDocument,
  type Bookmark,
  type OutlineItem,
  type PdfLink,
  type Point,
  type Rect,
  type Revs,
  type SearchHit,
  type TextLine,
  type TextStyle,
} from "./api";
import type { EqJob, SnipKind } from "./ai/equation.svelte";
import type { TextSelection } from "./viewer/Viewer.svelte";
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

/** Pen settings for the draw tool (shared by all tabs, remembered). */
export const ink = $state({ color: "#0a84ff", width: 2 });
export const INK_WIDTHS = [1.5, 2.5, 4, 7];

export async function loadInk() {
  const saved = await (await api()).get_setting<{ color: string; width: number } | null>("ink", null);
  if (saved) Object.assign(ink, saved);
}

export function saveInk() {
  api().then((py) => py.set_setting("ink", { ...ink }));
}

/** Font, size and weight for new text boxes (shared by all tabs, remembered). */
export const textStyle = $state<TextStyle>({ font: "sans", size: 12, bold: false });
export const TEXT_SIZES = [8, 10, 12, 14, 18, 24, 36];

export async function loadTextStyle() {
  const saved = await (await api()).get_setting<TextStyle | null>("textStyle", null);
  if (saved) Object.assign(textStyle, saved);
}

export function saveTextStyle() {
  api().then((py) => py.set_setting("textStyle", { ...textStyle }));
}

/** The box a text needs at a given style (PDF points), from its top-left corner. */
export function textBoxRect(x: number, y: number, text: string, s: TextStyle): Rect {
  const lines = text.split("\n");
  const longest = Math.max(1, ...lines.map((l) => l.length));
  const em = s.font === "mono" ? 0.62 : 0.56;
  const w = Math.max(40, Math.min(420, longest * s.size * em * (s.bold ? 1.08 : 1) + 12));
  const h = lines.length * s.size * 1.4 + 6;
  return [x, y, x + w, y + h];
}

/** One undoable annotation change. */
interface Op {
  label: string;
  undo: () => Promise<void>;
  redo: () => Promise<void>;
}

const HL_START = "<!-- phdf:highlights";
const HL_END = "<!-- /phdf:highlights -->";

let nextId = 1;

const PAGE_CACHE = 80; // pages whose text layer / links are kept per tab

/** Small LRU: a Map keeps insertion order, so re-inserting marks an entry as recent. */
function cached<T>(cache: Map<number, Promise<T>>, page: number, load: () => Promise<T>): Promise<T> {
  let p = cache.get(page);
  if (p) cache.delete(page);
  else p = load();
  cache.set(page, p);
  if (cache.size > PAGE_CACHE) cache.delete(cache.keys().next().value!);
  return p;
}

/** A new style (and the box it needs) for an existing text box. */
export type Restyle = Partial<TextStyle> & { rect?: Rect };

export class Tab {
  readonly kind = "pdf" as const;
  readonly id = nextId++;
  doc = $state() as OpenedDocument; // reactive: an e-book's pages change with its text size

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

  /** Equation → LaTeX: the page is in "draw a rectangle" mode, then the job and its preview. */
  snipping = $state<SnipKind | null>(null); // drawing a rectangle for the AI
  equation = $state<EqJob | null>(null);

  /** Finished pen strokes still drawn on top of their page until its new image (with the saved
   *  drawing) has loaded; `rev` is that image's revision, null while saving. */
  pendingInk = $state.raw<{ page: number; points: Point[]; color: string; width: number; rev: number | null }[]>([]);

  /** Earlier parts of a Ctrl / ⌘-drag selection. The browser holds only the newest range, so
   *  the viewer draws these itself. */
  keptSel = $state.raw<TextSelection[]>([]);

  /** An annotation being dragged: drawn as an outline at its new place until released. */
  moving = $state<{ id: string; dx: number; dy: number } | null>(null);

  // Undo / redo of annotation changes (session only).
  undoStack = $state<Op[]>([]);
  redoStack = $state<Op[]>([]);

  bookmarks = $state<Bookmark[]>([]);
  /** "Where was I?" card: shown once when a document is reopened. */
  welcomeBack = $state(false);

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
    this.welcomeBack = !!doc.lastOpened && (page > 0 || scroll > 0.05);
    this.pendingJump = { page: this.page, scroll: this.scroll };
  }

  /** An e-book (EPUB…): laid out into pages by PhDF, no annotations in the file. */
  get isBook() {
    return this.doc.info.reflowable;
  }

  /** The e-book was laid out again (new text size): new pages, about the same place. */
  reflow(change: { pageSizes: [number, number][]; revs: Revs }) {
    const old = this.doc.pageSizes.length;
    const pages = change.pageSizes.length;
    const at = Math.min(pages - 1, Math.round(((this.page + this.scroll) / old) * pages));
    this.doc.pageSizes = change.pageSizes;
    this.doc.info.page_count = pages;
    this.revs = change.revs;
    this.textCache.clear();
    this.linkCache.clear();
    this.searchHits = [];
    this.pendingJump = { page: at };
  }

  /** Shown instead of the document title (grading: the student). */
  label = $state<string | null>(null);

  get title() {
    return this.label ?? this.doc.title;
  }

  get path() {
    return this.doc.path;
  }

  get pageCount() {
    return this.doc.info.page_count;
  }

  textLines(page: number): Promise<TextLine[]> {
    return cached(this.textCache, page, () => api().then((py) => py.text_layer(this.doc.docId, page)));
  }

  links(page: number): Promise<PdfLink[]> {
    return cached(this.linkCache, page, () => api().then((py) => py.links(this.doc.docId, page)));
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
    // Other tabs of this window on the same document (Open Beside); other windows hear it from
    // the backend.
    const detail = { docId: this.doc.docId, dirty: change.dirty, revs: change.revs, source: this };
    window.dispatchEvent(new CustomEvent("phdf:doc-changed", { detail }));
  }

  /** The same document was changed in another view (pane or window): show its state. Undo
   *  steps stay per view. */
  async sync(change: { dirty: boolean; revs: Revs }) {
    this.dirty = change.dirty;
    this.revs = change.revs;
    if (this.annotations) this.annotations = await (await api()).annotations(this.doc.docId);
  }

  // The raw operations (no history); the public ones below record undo steps.

  private async _add(a: Omit<Annotation, "id" | "quote" | "modified"> & { id?: string }) {
    await this.loadAnnotations();
    const change = await (await api()).add_annotation(
      this.doc.docId, a.page, a.kind, a.rects, a.color, a.contents, a.strokes, a.width, a.id ?? null,
      a.font, a.font_size, a.bold ?? false,
    ); // prettier-ignore
    this.apply(change);
    this.annotations!.push(change.annotation!);
    return change.annotation!;
  }

  private async _update(id: string, color?: string | null, contents?: string | null, style?: Restyle | null) {
    const change = await (await api()).update_annotation(
      this.doc.docId, id, color, contents, style?.font ?? null, style?.size ?? null, style?.bold ?? null, style?.rect ?? null,
    ); // prettier-ignore
    this.apply(change);
    const i = this.annotations?.findIndex((a) => a.id === id) ?? -1;
    if (i >= 0 && change.annotation) this.annotations![i] = change.annotation;
    return change.annotation!;
  }

  private async _delete(id: string) {
    const change = await (await api()).delete_annotation(this.doc.docId, id);
    this.apply(change);
    this.annotations = this.annotations?.filter((a) => a.id !== id) ?? null;
    if (this.selectedAnnot === id) this.selectedAnnot = null;
  }

  private record(op: Op) {
    this.undoStack.push(op);
    if (this.undoStack.length > 200) this.undoStack.shift();
    this.redoStack = [];
  }

  async addAnnotation(
    page: number,
    kind: AnnotKind,
    rects: Rect[],
    color: string,
    contents = "",
    strokes: Point[][] | null = null,
    width: number | null = null,
    style: TextStyle | null = null,
  ) {
    const created = await this._add({
      page, kind, rects, color, contents, strokes, width,
      font: style?.font ?? null, font_size: style?.size ?? null, bold: style?.bold ?? null,
    }); // prettier-ignore
    const snapshot = { ...created };
    this.record({
      label: `Add ${kind}`,
      undo: () => this._delete(snapshot.id),
      redo: async () => void (await this._add(snapshot)),
    });
    return created;
  }

  async updateAnnotation(id: string, color?: string | null, contents?: string | null, style?: Restyle | null) {
    const before = this.annotations?.find((a) => a.id === id);
    const updated = await this._update(id, color, contents, style);
    if (before) {
      const prev = { color: before.color, contents: before.contents };
      const prevStyle: Restyle | null = style
        ? { font: before.font ?? "sans", size: before.font_size ?? 12, bold: !!before.bold, rect: before.rects[0] }
        : null;
      this.record({
        label: style ? "Change text style" : "Edit annotation",
        undo: async () =>
          void (await this._update(id, color != null ? prev.color : null, contents != null ? prev.contents : null, prevStyle)),
        redo: async () => void (await this._update(id, color, contents, style)),
      });
    }
    return updated;
  }

  async deleteAnnotation(id: string) {
    const snapshot = this.annotations?.find((a) => a.id === id);
    await this._delete(id);
    if (snapshot) {
      this.record({
        label: `Delete ${snapshot.kind}`,
        undo: async () => void (await this._add({ ...snapshot })), // same id: note pins keep working
        redo: () => this._delete(snapshot.id),
      });
    }
  }

  private async _move(id: string, dx: number, dy: number) {
    const change = await (await api()).move_annotation(this.doc.docId, id, dx, dy);
    this.apply(change);
    const i = this.annotations?.findIndex((a) => a.id === id) ?? -1;
    if (i >= 0 && change.annotation) this.annotations![i] = change.annotation;
  }

  /** Drag a note, text box or drawing to another spot on its page. */
  async moveAnnotation(id: string, dx: number, dy: number) {
    await this._move(id, dx, dy);
    this.record({
      label: "Move annotation",
      undo: () => this._move(id, -dx, -dy),
      redo: () => this._move(id, dx, dy),
    });
  }

  async undo() {
    const op = this.undoStack.pop();
    if (!op) return null;
    await op.undo();
    this.redoStack.push(op);
    return op.label;
  }

  async redo() {
    const op = this.redoStack.pop();
    if (!op) return null;
    await op.redo();
    this.undoStack.push(op);
    return op.label;
  }

  // --- bookmarks ------------------------------------------------------------------------------

  async loadBookmarks() {
    this.bookmarks = await (await api()).bookmarks(this.doc.docId);
  }

  isBookmarked(page: number) {
    return this.bookmarks.some((b) => b.page === page);
  }

  async toggleBookmark(page = this.page) {
    const py = await api();
    this.bookmarks = this.isBookmarked(page)
      ? await py.delete_bookmark(this.doc.docId, page)
      : await py.set_bookmark(this.doc.docId, page, "");
    return this.isBookmarked(page);
  }

  async renameBookmark(page: number, label: string) {
    this.bookmarks = await (await api()).set_bookmark(this.doc.docId, page, label);
  }

  // --- highlights → note -----------------------------------------------------------------------

  /** Write every annotation, in page order, under a line at the end of the integrated note.
   *  Re-running replaces that section only; the user's own writing above it is untouched. */
  async exportHighlightsToNote() {
    await Promise.all([this.loadAnnotations(), this.loadOutline()]);
    const md = await this.ensureMd();
    const marks = (this.annotations ?? [])
      .filter((a) => a.kind !== "other")
      .sort((a, b) => a.page - b.page || (a.rects[0]?.[1] ?? 0) - (b.rects[0]?.[1] ?? 0));
    // The markers let a re-export replace only this section (they are hidden in previews).
    let block = `---\n## Highlights\n${HL_START} -->\n\n`;
    let lastPage = -1;
    for (const a of marks) {
      const section = sectionFor(this.outline, a.page);
      if (a.page !== lastPage) {
        block += `### p. ${a.page + 1}${section ? ` · §${section}` : ""}\n\n`;
        lastPage = a.page;
      }
      const pin = pinBlock(a, section).trimEnd();
      if (a.kind === "note" || a.kind === "freetext") {
        block += `${pin}\n> 📝 ${a.contents.trim().replace(/\n/g, "\n> ")}\n\n`;
      } else if (a.kind === "ink") {
        block += `${pin}\n> ✏️ Drawing\n\n`;
      } else {
        block += `${pin}\n`;
        if (a.contents.trim()) block += `\n${a.contents.trim()}\n`;
        block += "\n";
      }
    }
    if (!marks.length) block += "_No highlights yet._\n\n";
    block += `${HL_END}\n`;

    const text = md.text;
    const start = text.indexOf(HL_START);
    let next: string;
    if (start >= 0) {
      const sep = text.lastIndexOf("---\n## Highlights", start);
      const from = sep >= 0 ? sep : start;
      const endAt = text.indexOf(HL_END, start);
      const to = endAt >= 0 ? endAt + HL_END.length + 1 : text.length;
      next = text.slice(0, from) + block + text.slice(to);
    } else {
      next = text.replace(/\s*$/, "") + "\n\n" + block;
    }
    md.replaceText(next);
    this.mdView = "note";
    this.mdOpen = true;
    return marks.length;
  }

  async save() {
    if (this.dirty) this.apply({ ...(await (await api()).save_document(this.doc.docId)) });
    await this.md?.flush();
    await this.parking?.flush();
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

  /** Show another note beside this PDF (grading: the folder's grades table). */
  attachNote(md: MdDoc) {
    this.md = md;
    this.mdView = "note";
    this.mdOpen = true;
  }

  detachNote() {
    this.label = null;
    this.md = null;
    this.mdOpen = false;
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
      const doc = new MdDoc(path, `# Parking Lot: ${this.title}\n\nThoughts parked while reading in PhDF.\n\n`);
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
