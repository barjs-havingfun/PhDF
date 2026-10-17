// Typed wrapper around the Python API exposed by pywebview (backend/phdf/api.py).

export type Rect = [number, number, number, number]; // x0, y0, x1, y1 in PDF points
export type FitMode = "width" | "page" | "none";

export interface MdFile {
  name: string;
  path: string;
}

export interface AppInfo {
  name: string;
  version: string;
  renderBaseUrl: string;
  windowId: string;
  /** A window made by dragging a tab out: it docks back instead of being restored. */
  detached: boolean;
  platform: "windows" | "macos" | "linux";
}

export interface Position {
  page: number;
  scroll: number; // 0..1 offset within the page
  zoom: number;
  fit: FitMode;
}

export interface OpenedDocument {
  docId: string;
  path: string;
  title: string;
  info: { page_count: number; title: string | null; author: string | null; is_encrypted: boolean; reflowable: boolean };
  pageSizes: [number, number][];
  position: Position;
  dirty: boolean;
  revs: Revs;
  lastOpened: number | null; // unix time of the previous visit
}

export interface NeedsPassword {
  needsPassword: true;
  /** A password was given and it was not right. */
  wrong: boolean;
}

export interface AboutInfo {
  version: string;
  python: string;
  pymupdf: string;
  pywebview: string;
  os: string;
  gui: string;
  frozen: boolean;
  dataDir: string;
  dbBytes: number;
  aiCacheBytes: number;
  coverBytes: number;
  ocrLanguages: string[];
}

export interface Bookmark {
  page: number;
  label: string;
  created: number;
}

export interface LibraryItem {
  docId: string;
  path: string;
  title: string;
  page: number;
  pageCount: number;
  lastOpened: number;
  seconds: number;
  exists: boolean;
}

export interface ReadingStats {
  days: { day: string; seconds: number }[];
  today: number;
  week: number;
  streak: number;
}

/** Render revision per page; bumped when annotations change how a page looks. */
export type Revs = Record<number, number>;

export type AnnotKind =
  | "highlight"
  | "underline"
  | "strikeout"
  | "note"
  | "freetext"
  | "ink"
  | "other";

export type Point = [number, number];

export interface Annotation {
  id: string;
  page: number;
  kind: AnnotKind;
  rects: Rect[];
  color: string;
  contents: string;
  quote: string;
  modified: string | null;
  strokes: Point[][] | null;
  width: number | null;
  font: TextFont | null; // free text
  font_size: number | null;
  bold: boolean | null;
}

export type TextFont = "sans" | "serif" | "mono";

/** How a free-text box is written. */
export interface TextStyle {
  font: TextFont;
  size: number;
  bold: boolean;
}

export interface AnnotChange {
  annotation?: Annotation;
  page?: number;
  dirty: boolean;
  revs: Revs;
}

export interface TextFile {
  exists: boolean;
  text: string;
  mtime: number | null;
}

export interface RecentDocument {
  doc_id: string;
  path: string;
  title: string | null;
  page_count: number;
  last_opened: number;
  page: number;
}

export interface OutlineItem {
  title: string;
  page: number;
  level: number;
  children: OutlineItem[];
}

export interface TextLine {
  bbox: Rect;
  spans: { text: string; bbox: Rect; size: number }[];
}

export interface PdfLink {
  rect: Rect;
  kind: "goto" | "uri" | "other";
  page: number;
  y: number | null;
  uri: string | null;
}

export interface GradingFolder {
  folder: string;
  key: string; // for settings: lower-cased only where paths ignore case
  title: string;
  table: string; // the grades table (.md)
  files: { rel: string; name: string }[];
}

/** The AI's whole-document Markdown copy (✦ menu, "Read as Markdown"). */
export interface MarkdownStatus {
  state: "none" | "working" | "ready" | "error";
  done: number; // pages converted
  total: number;
  error?: string;
}

/** A PhDF Tools session: an edited copy of a PDF (pages served under `id`). */
export interface ToolsState {
  id: string;
  path: string;
  name: string;
  pages: [number, number][]; // size of each page (rotation applied)
  annotated: boolean[];
  canUndo: boolean;
  revs: Revs;
}

export interface ParkedItem {
  line: number;
  text: string; // the whole line after the checkbox
  done: boolean;
  thought: string;
  meta: string; // "source · time", or only the time
}

export interface SearchHit {
  page: number;
  rects: Rect[];
}

interface PyApi {
  app_info(): Promise<AppInfo>;
  pick_pdf(): Promise<string | null>;
  startup_paths(): Promise<string[]>;
  pick_file(kind: "document" | "pdf" | "md"): Promise<string | null>;
  pick_new_md(name?: string): Promise<string | null>;
  open_window(paths: string[], x?: number, y?: number, detached?: boolean): Promise<string>;
  dock(paths: string[]): Promise<void>;
  md_files(folder: string): Promise<MdFile[]>;
  close_window(): Promise<void>;
  toggle_fullscreen(): Promise<void>;
  window_theme(dark: boolean): Promise<void>;
  epub_text_size(size: number): Promise<{ docId: string; pageSizes: [number, number][]; revs: Revs }[]>;
  term_start(cwd?: string | null, cols?: number, rows?: number): Promise<string>;
  term_read(id: string, timeout?: number): Promise<{ data: string; alive: boolean }>;
  term_write(id: string, data: string): Promise<void>;
  term_resize(id: string, cols: number, rows: number): Promise<void>;
  term_ai(id: string): Promise<string | null>;
  term_close(id: string): Promise<void>;
  ai_tools(): Promise<{ claude: boolean; codex: boolean; gemini: boolean }>;
  bookmarks(docId: string): Promise<Bookmark[]>;
  set_bookmark(docId: string, page: number, label?: string): Promise<Bookmark[]>;
  delete_bookmark(docId: string, page: number): Promise<Bookmark[]>;
  log_reading(docId: string, seconds: number): Promise<void>;
  reading_stats(): Promise<ReadingStats>;
  library(): Promise<LibraryItem[]>;
  library_cover(docId: string, path: string): Promise<string | null>;
  window_at(x: number, y: number, scale?: number): Promise<string | null>;
  send_to_window(windowId: string, path: string): Promise<boolean>;
  ai_context(docId: string, firstPage: number, lastPage: number): Promise<{ path: string; first: number; last: number; chars: number }>;
  ai_cache_info(): Promise<{ files: number; bytes: number }>;
  ai_markdown_status(docId: string): Promise<MarkdownStatus>;
  ai_markdown_prepare(docId: string): Promise<MarkdownStatus>;
  ai_cache_clear(): Promise<{ files: number; bytes: number }>;
  parking_path(document?: string | null): Promise<string>;
  parking_add(thought: string, source?: string | null, document?: string | null): Promise<string>;
  parking_list(
    document?: string | null,
  ): Promise<{ path: string; items: ParkedItem[] }>;
  parking_done(line: number, text: string, done?: boolean, document?: string | null): Promise<boolean>;
  /** An encrypted PDF answers `{needsPassword}` until called with the right password. */
  open_document(path: string, password?: string): Promise<OpenedDocument | NeedsPassword>;
  save_page_image(docId: string, page: number, name: string): Promise<string | null>;
  open_in_default_app(path: string): Promise<void>;
  ui_zoom(factor: number): Promise<void>;
  library_remove(docId: string): Promise<void>;
  library_relink(docId: string): Promise<{ ok: boolean; reason?: "cancelled" | "different"; path?: string }>;
  about(): Promise<AboutInfo>;
  close_document(docId: string): Promise<void>;
  outline(docId: string): Promise<OutlineItem[]>;
  text_layer(docId: string, page: number): Promise<TextLine[]>;
  links(docId: string, page: number): Promise<PdfLink[]>;
  search(docId: string, query: string): Promise<SearchHit[]>;
  save_position(
    docId: string,
    page: number,
    scroll: number,
    zoom: number,
    fit: FitMode,
  ): Promise<void>;
  recent_documents(limit?: number): Promise<RecentDocument[]>;
  annotations(docId: string): Promise<Annotation[]>;
  add_annotation(
    docId: string,
    page: number,
    kind: AnnotKind,
    rects: Rect[],
    color: string,
    contents?: string,
    strokes?: Point[][] | null,
    width?: number | null,
    annotId?: string | null,
    font?: TextFont | null,
    fontSize?: number | null,
    bold?: boolean,
  ): Promise<AnnotChange>;
  update_annotation(
    docId: string,
    id: string,
    color?: string | null,
    contents?: string | null,
    font?: TextFont | null,
    fontSize?: number | null,
    bold?: boolean | null,
    rect?: Rect | null,
  ): Promise<AnnotChange>;
  equation_snip(docId: string, page: number, rect: Rect, folder?: string | null): Promise<{ png: string; tex: string }>;
  equation_result(texPath: string): Promise<string | null>;
  equation_cleanup(pngPath: string): Promise<void>;
  delete_annotation(docId: string, id: string): Promise<AnnotChange>;
  move_annotation(docId: string, id: string, dx: number, dy: number): Promise<AnnotChange>;
  save_document(docId: string): Promise<{ dirty: boolean; revs: Revs }>;
  revert_document(docId: string): Promise<{ dirty: boolean; revs: Revs }>;
  ocr_info(): Promise<{ installed: string[]; common: Record<string, string> }>;
  ocr_download(lang: string): Promise<string[]>;
  page_has_text(docId: string, page: number): Promise<boolean>;
  pages_without_text(docId: string): Promise<number[]>;
  ocr_page(docId: string, page: number, languages: string[]): Promise<AnnotChange & { words: number }>;
  export_markdown(docId: string): Promise<string>;
  pick_folder(): Promise<string | null>;
  save_csv(name: string, text: string): Promise<string | null>;
  grading_scan(folder: string): Promise<GradingFolder>;
  grading_copy(folder: string, rel: string): Promise<string>;
  obsidian_append(title: string, block: string): Promise<string>;
  obsidian_write(
    title: string,
    text: string,
    overwrite?: boolean,
  ): Promise<{ path: string; written: boolean; exists: boolean }>;
  open_in_obsidian(path: string): Promise<void>;
  md_for_pdf(pdfPath: string): Promise<{ path: string; exists: boolean; linked: boolean }>;
  pdf_for_md(mdPath: string): Promise<string | null>;
  link_md(pdfPath: string, mdPath: string): Promise<void>;
  read_text(path: string): Promise<TextFile>;
  write_text(path: string, text: string): Promise<number>;
  file_mtime(path: string): Promise<number | null>;
  rename_file(path: string, name: string): Promise<string>;
  tools_open(path: string): Promise<ToolsState>;
  tools_apply(id: string, op: Record<string, unknown>): Promise<ToolsState>;
  tools_undo(id: string): Promise<ToolsState>;
  tools_has_annotations(id: string, pages?: number[] | null): Promise<boolean>;
  tools_chapters(id: string): Promise<number[]>;
  tools_save(id: string, keepAnnotations?: boolean): Promise<string>;
  tools_extract(id: string, pages: number[], keepAnnotations?: boolean): Promise<string | null>;
  tools_split(id: string, parts: number[][], keepAnnotations?: boolean): Promise<string[]>;
  tools_close(id: string): Promise<void>;
  open_external(url: string): Promise<void>;
  peek_url(url: string, large?: boolean): Promise<boolean>;
  peek_expand(): Promise<void>;
  peek_close(): Promise<void>;
  get_setting<T>(key: string, defaultValue?: T): Promise<T>;
  set_setting(key: string, value: unknown): Promise<void>;
}

declare global {
  interface Window {
    pywebview?: { api: PyApi };
  }
}

let ready: Promise<PyApi> | null = null;

/** Resolves once pywebview has injected the API. Never resolves in a plain browser. */
export function api(): Promise<PyApi> {
  ready ??= new Promise((resolve) => {
    if (window.pywebview?.api) resolve(window.pywebview.api);
    else window.addEventListener("pywebviewready", () => resolve(window.pywebview!.api), { once: true });
  });
  return ready;
}

let renderBase = "";

export function setRenderBaseUrl(url: string) {
  renderBase = url;
}

/** URL of a rendered page image. `scale` is device pixels per PDF point. */
export function pageImageUrl(
  docId: string,
  page: number,
  scale: number,
  clip?: Rect,
  rev = 0,
): string {
  const s = `s=${scale.toFixed(2)}`;
  const c = clip ? `&clip=${clip.map((v) => v.toFixed(1)).join(",")}` : "";
  const r = rev ? `&r=${rev}` : ""; // new URL after annotation edits (images are cached)
  return `${renderBase}/page/${docId}/${page}.png?${s}${c}${r}`;
}
