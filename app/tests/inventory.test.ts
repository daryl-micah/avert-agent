import { describe, expect, it } from "vitest";

import { buildInventory, parseCallSitesJsonl } from "../src/inventory/inventory";

const hash = "a".repeat(64);

function callSite(model: string | null, binding: "literal" | "dynamic" = "literal") {
  return {
    surface: {
      provider: "openai",
      resource: "chat.completions",
      operation: "create",
      field_path: "model",
      value: model,
    },
    repo: "acme/api",
    file_path: "src/client.py",
    line_start: 12,
    line_end: 12,
    language: "python" as const,
    value_binding: binding,
    confidence: 1,
    extractor: "tree_sitter.python",
    file_content_hash: hash,
  };
}

describe("inventory", () => {
  it("parses JSONL and reports its line on invalid input", () => {
    expect(parseCallSitesJsonl(`${JSON.stringify(callSite("gpt-4"))}\n`)).toHaveLength(1);
    expect(() => parseCallSitesJsonl("{}\nnot-json\n")).toThrow("line 1");
    expect(() => parseCallSitesJsonl(JSON.stringify({ ...callSite("gpt-4"), confidence: 2 })))
      .toThrow("Invalid CallSite");
  });

  it("groups call sites and applies lifecycle status", () => {
    const sites = [callSite("gpt-old"), { ...callSite("gpt-old"), file_path: "src/jobs.py" }];
    const inventory = buildInventory(
      sites,
      [{
        provider: "openai",
        resource: "chat.completions",
        operation: "create",
        model: "gpt-old",
        replacement: "gpt-new",
        effective_at: "2026-09-01",
      }],
      "2026-08-12",
    );

    expect(inventory.callSiteCount).toBe(2);
    expect(inventory.attentionCount).toBe(2);
    expect(inventory.dependencies).toHaveLength(1);
    expect(inventory.dependencies[0]).toMatchObject({
      status: "retiring",
      replacement: "gpt-new",
      locations: [{ filePath: "src/client.py" }, { filePath: "src/jobs.py" }],
    });
  });

  it("marks dynamic values unknown", () => {
    const inventory = buildInventory([callSite(null, "dynamic")], [], "2026-08-12");
    expect(inventory.dependencies[0].status).toBe("unknown");
    expect(inventory.attentionCount).toBe(0);
  });
});
