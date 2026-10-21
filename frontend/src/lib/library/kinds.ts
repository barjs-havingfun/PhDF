// Library tags and filters: the kind of a document, from its file name.

export const KINDS = { pdf: "PDF", epub: "EPUB", mng: "MNG" } as const;
export type DocKind = keyof typeof KINDS;

export function docKind(path: string): DocKind {
  const ext = path.toLowerCase().split(".").pop();
  return ext === "cbz" ? "mng" : ext === "epub" ? "epub" : "pdf";
}
