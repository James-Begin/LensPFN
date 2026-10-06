const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const context = { URL, URLSearchParams };
vm.runInNewContext(
  fs.readFileSync(
    path.join(__dirname, "../extension/reference-parser.js"),
    "utf8",
  ),
  context,
);
const { parse, safeUrl, fromValue } = context.LensReferenceParser;
const base = "https://arxiv.org/html/2303.08774v2";
function entry(text, links = [], blocks = [], fields = {}) {
  return {
    textContent: text,
    querySelector: (selector) =>
      fields[selector] ? { textContent: fields[selector] } : null,
    querySelectorAll: (selector) =>
      selector === "a[href]"
        ? links.map((href) => ({ getAttribute: () => href }))
        : blocks.map((textContent) => ({ textContent })),
  };
}
test("recognizes HTML, PDF, export, ar5iv, DOI, old-style, and versioned arXiv identities", () => {
  for (const url of [
    "https://arxiv.org/html/2207.01848v3",
    "https://export.arxiv.org/pdf/2207.01848v3.pdf",
    "https://ar5iv.labs.arxiv.org/html/2207.01848",
    "https://doi.org/10.48550/arXiv.2207.01848",
  ]) {
    assert.equal(parse(entry("A reference.", [url]), base).id, "2207.01848");
  }
  assert.equal(
    parse(entry("Old work.", ["https://arxiv.org/abs/hep-th/9901001v2"]), base)
      .id,
    "hep-th/9901001",
  );
  assert.equal(
    parse(entry("arXiv preprint 1706.03762v7."), base).id,
    "1706.03762",
  );
  assert.equal(parse(entry("Other identifier 1706.03762."), base).id, null);
});
test("parses structured bibliography blocks without fabricating an arXiv identity", () => {
  const result = parse(
    entry(
      "Alex Example (2024). A journal paper. Example Journal. doi:10.1234/example.",
      [],
      [
        "Alex Example (2024).",
        "A journal paper.",
        "Example Journal. doi:10.1234/example.",
      ],
    ),
    base,
  );
  assert.equal(result.id, null);
  assert.equal(result.details.title, "A journal paper.");
  assert.equal(result.details.authors, "Alex Example (2024).");
  assert.equal(result.details.year, "2024");
  assert.equal(result.details.url, "https://doi.org/10.1234/example");
  assert.match(result.details.publication, /Example Journal/);
});
test("retains unstructured references and ignores unsafe or malformed source links", () => {
  const result = parse(
    entry("A. Author. A paper without reliable title markup.", [
      "javascript:alert(1)",
      "https://arxiv.org/abs/%ZZ",
    ]),
    base,
  );
  assert.equal(result.id, null);
  assert.equal(result.details.title, "");
  assert.match(result.reference, /A paper/);
  assert.equal(safeUrl(null, base), null);
  assert.equal(safeUrl("data:text/html,x", base), null);
  assert.equal(safeUrl("javascript:alert(1)", base), null);
});

test("bibliography back-links never identify the paper being read as the cited work", () => {
  for (const navigation of [
    "#bib.bib1",
    "#S2.p1.1",
    `${base}#S2.p1.1`,
    base,
    `${base}?view=html#S2.p1.1`,
  ]) {
    const result = parse(
      entry("Attention Is All You Need.", [
        navigation,
        "https://arxiv.org/abs/1706.03762v7",
      ]),
      base,
    );
    assert.equal(
      result.id,
      "1706.03762",
      `ignored bibliography navigation: ${navigation}`,
    );
    assert.equal(result.details.url, "https://arxiv.org/abs/1706.03762v7");
    const unresolved = parse(entry("A journal reference.", [navigation]), base);
    assert.equal(unresolved.id, null);
    assert.equal(unresolved.details.url, null);
  }
});

test("a real self-citation remains identifiable from its external paper URL", () => {
  assert.equal(
    parse(
      entry("This earlier work.", [
        "#S2.p1.1",
        "https://arxiv.org/abs/2303.08774",
      ]),
      base,
    ).id,
    "2303.08774",
  );
});

test("manual linking accepts only real arXiv identifiers and supported paper URLs", () => {
  assert.equal(fromValue("https://arxiv.org/abs/1810.04805v2"), "1810.04805");
  assert.equal(fromValue("arXiv:1810.04805"), "1810.04805");
  assert.equal(fromValue("https://example.com/abs/1810.04805"), null);
  assert.equal(fromValue("A paper title"), null);
  const result = parse(
    entry("BERT.", ["https://doi.org/10.18653/v1/N19-1423"]),
    base,
  );
  assert.equal(result.details.doi, "10.18653/v1/N19-1423");
});
