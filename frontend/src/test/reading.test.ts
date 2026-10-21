import { describe, expect, it, vi } from "vitest";

vi.mock("../lib/api", () => ({ api: vi.fn() }));

import { arrowStep, onScreen, read, stepRow } from "../lib/reading.svelte";
import { docKind } from "../lib/library/kinds";

describe("right to left", () => {
  it("puts the first page of a spread on the right", () => {
    expect(onScreen([4, 5], false)).toEqual([4, 5]);
    expect(onScreen([4, 5], true)).toEqual([5, 4]);
    expect(onScreen([0], true)).toEqual([0]);
  });

  it("turns forward with ←", () => {
    expect(arrowStep("arrowright", false)).toBe(1);
    expect(arrowStep("arrowleft", true)).toBe(1);
    expect(arrowStep("arrowright", true)).toBe(-1);
    expect(arrowStep("home", true)).toBe(0);
    read.pages = "spread";
    expect(stepRow(4, arrowStep("arrowleft", true) as 1, 10)).toBe(6);
  });
});

describe("library kinds", () => {
  it("comes from the file name", () => {
    expect(docKind("C:\Books\One Piece 01.CBZ")).toBe("mng");
    expect(docKind("/books/a.epub")).toBe("epub");
    expect(docKind("/books/paper.pdf")).toBe("pdf");
  });
});
