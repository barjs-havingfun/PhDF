// Typed wrapper around the Python API exposed by pywebview (backend/phdf/api.py).

export type Rect = [number, number, number, number]; // x0, y0, x1, y1 in PDF points
export type FitMode = "width" | "page" | "none";

export interface AppInfo {
  name: string;
  version: string;
  renderBaseUrl: string;
  windowId: string;
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
  info: { page_count: number; title: string | null; author: string | null; is_encrypted: boolean };
  pageSizes: [number, number][];
  position: Position;
  dirty: boolean;
  revs: Revs;
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

export interface SearchHit {
  page: number;
  rects: Rect[];
}

interface PyApi {
  app_info(): Promise<AppInfo>;
  pick_pdf(): Promise<string | null>;
  pick_file(kind: "document" | "pdf" | "md"): Promise<string | null>;
  pick_new_md(name?: string): Promise<string | null>;
  open_window(paths: string[], x?: number, y?: number): Promise<string>;
  close_window(): Promise<void>;
  toggle_fullscreen(): Promise<void>;
  parking_path(document?: string | null): Promise<string>;
  parking_add(thought: string, source?: string | null, document?: string | null): Promise<string>;
  parking_list(
    document?: string | null,
  ): Promise<{ path: string; items: { line: number; text: string; done: boolean }[] }>;
  parking_done(line: number, text: string, done?: boolean, document?: string | null): Promise<boolean>;
  open_document(path: string): Promise<OpenedDocument>;
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
  ): Promise<AnnotChange>;
  update_annotation(
    docId: string,
    id: string,
    color?: string | null,
    contents?: string | null,
  ): Promise<AnnotChange>;
  delete_annotation(docId: string, id: string): Promise<AnnotChange>;
  save_document(docId: string): Promise<{ dirty: boolean; revs: Revs }>;
  revert_document(docId: string): Promise<{ dirty: boolean; revs: Revs }>;
  ocr_info(): Promise<{ installed: string[]; common: Record<string, string> }>;
  ocr_download(lang: string): Promise<string[]>;
  page_has_text(docId: string, page: number): Promise<boolean>;
  pages_without_text(docId: string): Promise<number[]>;
  ocr_page(docId: string, page: number, languages: string[]): Promise<AnnotChange & { words: number }>;
  export_markdown(docId: string): Promise<string>;
  pick_folder(): Promise<string | null>;
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
  open_external(url: string): Promise<void>;
  peek_url(url: string): Promise<boolean>;
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
