// Close a menu when the user presses anywhere outside it. Full-screen "backdrop" divs don't work
// everywhere: inside a toolbar with backdrop-filter or a container query, `position: fixed` is
// relative to that toolbar, so the backdrop only covers the toolbar.

/** While a menu is open: a press outside `node()` (the menu and its button) calls `close`.
 *  Use in an `$effect` and return its result, so the listener goes away with the menu. */
export function outsideClose(node: () => Element | null | undefined, close: () => void): () => void {
  const down = (e: PointerEvent) => {
    const el = node();
    if (el && !el.contains(e.target as Node)) close();
  };
  document.addEventListener("pointerdown", down, true);
  return () => document.removeEventListener("pointerdown", down, true);
}
