import { describe, expect, it } from "vitest";
import type { Rect } from "../lib/api";
import { joinParts, mergeLines } from "../lib/viewer/rects";
import type { TextSelection } from "../lib/viewer/Viewer.svelte";

const box = { x: 1 } as unknown as DOMRect;
const part = (text: string, page: number, y: number): TextSelection => ({
  text,
  byPage: new Map<number, Rect[]>([[page, [[10, y, 100, y + 10]]]]),
  box,
});

describe("mergeLines", () => {
  it("joins rects on one line and keeps lines apart", () => {
    const lines = mergeLines([
      [50, 100, 80, 110],
      [10, 101, 40, 111],
      [10, 130, 90, 140],
    ]);
    expect(lines).toEqual([
      [10, 100, 80, 111],
      [10, 130, 90, 140],
    ]);
  });
});

describe("joinParts", () => {
  it("is null without parts and passes a single part through", () => {
    expect(joinParts([], box)).toBeNull();
    expect(joinParts([part("one", 0, 10)], box)?.parts).toBeUndefined();
  });

  it("orders parts by page and position, keeping each part's rects", () => {
    const sel = joinParts([part("later", 1, 10), part("second", 0, 300), part("first", 0, 20)], box)!;
    expect(sel.text).toBe("first\n\nsecond\n\nlater");
    expect(sel.parts).toHaveLength(3);
    expect(sel.byPage.get(0)).toHaveLength(2);
    expect(sel.byPage.get(1)).toHaveLength(1);
  });
});
