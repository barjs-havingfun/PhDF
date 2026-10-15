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
  open_window(paths: string[], x?: number, y?: number): Promise<string>;
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
export function pageImageUrl(docId: string, page: number, scale: number, clip?: Rect): string {
  const s = `s=${scale.toFixed(2)}`;
  const c = clip ? `&clip=${clip.map((v) => v.toFixed(1)).join(",")}` : "";
  return `${renderBase}/page/${docId}/${page}.png?${s}${c}`;
}
