import { describe, expect, it } from "vitest";
import { renderMarkdown } from "../lib/md/render";

describe("renderMarkdown", () => {
  it("turns footnotes into superscripts and a list", () => {
    const html = renderMarkdown("Claim[^a].\n\n[^a]: The source.\n");
    expect(html).toContain('<sup class="fn"><a href="#fn-1" id="fnref-1">1</a></sup>');
    expect(html).toContain('<section class="footnotes"><ol><li id="fn-1">The source.');
  });

  it("leaves footnote syntax inside code alone", () => {
    const html = renderMarkdown("```\n[^a]: not a note\nx[^a]\n```\n\nUse `[^a]` for notes.\n");
    expect(html).not.toContain("footnotes");
    expect(html).toContain("[^a]: not a note");
    expect(html).toContain("<code>[^a]</code>");
  });

  it("typesets math but not money", () => {
    expect(renderMarkdown("Euler: $e^{i\pi}$")).toContain("katex");
    expect(renderMarkdown("Costs $5 and $6 today")).not.toContain("katex");
  });

  it("keeps math inside code as written", () => {
    expect(renderMarkdown("`$x$`")).toContain("<code>$x$</code>");
  });

  it("renders marks, hides comments, ticks tasks and styles callouts", () => {
    expect(renderMarkdown("a ==key== b")).toContain("<mark>key</mark>");
    expect(renderMarkdown("a %%secret%% b")).not.toContain("secret");
    expect(renderMarkdown("- [x] done")).toContain('<li class="task"><input type="checkbox" disabled checked>');
    expect(renderMarkdown("> [!tip] Hint\n> text")).toContain('class="callout callout-tip"');
  });

  it("never passes HTML through", () => {
    expect(renderMarkdown("<script>alert(1)</script>")).not.toContain("<script>");
  });
});
