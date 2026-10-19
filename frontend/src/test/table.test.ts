import { describe, expect, it } from "vitest";
import { getCell, newTableText, setCells, toCsv } from "../lib/grading/table";

describe("grades table", () => {
  const text = newTableText("Midterm", 2);

  it("reads and writes cells, leaving the rest as it was", () => {
    const before = `Notes above\n\n${text}\nNotes below\n`;
    const after = setCells(before, 2, { Name: "Ada", Grade: "95" });
    expect(getCell(after, 2, "Name")).toBe("Ada");
    expect(getCell(after, 2, "Grade")).toBe("95");
    expect(getCell(after, 1, "Name")).toBe("");
    expect(after.startsWith("Notes above")).toBe(true);
    expect(after.endsWith("Notes below\n")).toBe(true);
  });

  it("escapes pipes in cells", () => {
    const after = setCells(text, 1, { Name: "A | B" });
    expect(getCell(after, 1, "Name")).toBe("A | B");
  });

  it("exports CSV with quoting", () => {
    const csv = toCsv(setCells(text, 1, { Name: 'Smith, "J"' }));
    expect(csv.split("\r\n")[0]).toBe("#,Name,Grade,Comment");
    expect(csv).toContain('"Smith, ""J"""');
  });
});
