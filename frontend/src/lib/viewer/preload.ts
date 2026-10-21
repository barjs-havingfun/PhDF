// Page images loaded and decoded ahead (book view's next / previous spread). A PageView whose
// image URL is here shows it at once instead of loading it again: the render server sends
// no-store, so nothing else guarantees the web view still has it.
export const preloaded = new Map<string, HTMLImageElement>();
