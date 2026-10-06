const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const parser = fs.readFileSync(
  path.join(__dirname, "../extension/reference-parser.js"),
  "utf8",
);
const prefetchSource = fs.readFileSync(
  path.join(__dirname, "../extension/citation-prefetch.js"),
  "utf8",
);
const recommendationSource = fs.readFileSync(
  path.join(__dirname, "../extension/citation-recommendations.js"),
  "utf8",
);
const source = fs.readFileSync(
  path.join(__dirname, "../extension/citations.js"),
  "utf8",
);

function reader(
  reference,
  links,
  { status = null, discover = false, resolution = null } = {},
) {
  const handlers = {};
  const messages = [];
  const classes = new Set();
  const anchor = {
    hash: "#bib.bib1",
    textContent: "[1]",
    getAttribute: () => anchor.hash,
    classList: { add: (x) => classes.add(x), remove: (x) => classes.delete(x) },
    closest: (selector) => (selector === "a[href]" ? anchor : null),
  };
  const entry = {
    textContent: reference,
    closest: () => (anchor.hash === "#S1" ? null : entry),
    querySelector: () => null,
    querySelectorAll: (selector) =>
      selector === "a[href]"
        ? links.map((href) => ({ getAttribute: () => href }))
        : [],
  };
  const document = {
    adoptedStyleSheets: [],
    head: { append: () => {} },
    createElement: () => ({}),
    querySelector: () => null,
    querySelectorAll: () => (discover ? [anchor, anchor] : []),
    getElementById: (id) => (id === anchor.hash.slice(1) ? entry : null),
    addEventListener: (event, handler) => {
      handlers[event] = handler;
    },
  };
  const popup = {
    host: {
      hidden: true,
      addEventListener: () => {},
      matches: () => false,
      contains: () => false,
    },
    root: { querySelector: () => null },
    papers: [],
    matches: [],
    resolutions: [],
    show: () => {
      popup.host.hidden = false;
    },
    hide: () => {
      popup.host.hidden = true;
    },
    updatePaper: (paper) => popup.papers.push(paper),
    beginMatch: () => {},
    resolving: () => {},
    updateResolution: (result) => popup.resolutions.push(result),
    updateRating: (rating) => {
      popup.rating = rating;
    },
    updateMatch: (match) => popup.matches.push(match),
    error: () => {},
  };
  const chrome = {
    runtime: {
      onMessage: {
        addListener: (fn) => {
          handlers.runtimeMessage = fn;
        },
      },
      sendMessage: (message) => {
        messages.push(message);
        if (message.path === "/api/resolve-reference" && resolution)
          return Promise.resolve({ ok: true, data: resolution });
        if (message.path === "/api/status" && status)
          return Promise.resolve({
            ok: true,
            data: { ...status, ratings: { ...status.ratings } },
          });
        const id = message.path
          ? new URL(message.path, "http://127.0.0.1").searchParams.get("id")
          : null;
        return Promise.resolve({
          ok: true,
          data: {
            title: `Paper ${id}`,
            id,
            match: id === "2207.01848" ? 0.42 : 0.76,
          },
        });
      },
    },
  };
  const suggestions = {
    reports: [],
    started: 0,
    ratings: {},
    suspend() {},
    begin() {
      this.started++;
    },
    complete(report) {
      this.reports.push(report);
    },
    updateRatings(ratings) {
      this.ratings = ratings;
    },
  };
  vm.runInNewContext(parser + prefetchSource + recommendationSource + source, {
    document,
    chrome,
    URL,
    setTimeout,
    clearTimeout,
    CSSStyleSheet: class {
      replaceSync() {}
    },
    LensCitationPopup: {
      create: (options) => {
        popup.callbacks = options;
        return popup;
      },
    },
    LensRecommendationPopup: {
      create: (options) => {
        suggestions.callbacks = options;
        return suggestions;
      },
    },
    location: {
      pathname: "/html/2303.08774",
      href: "https://arxiv.org/html/2303.08774",
    },
  });
  return { anchor, handlers, messages, classes, popup, suggestions };
}

test("focus on a linked bibliography citation highlights it and selects an arXiv paper", () => {
  const fixture = reader("[1] Attention Is All You Need. arXiv:1706.03762.", [
    "https://arxiv.org/abs/1706.03762v7",
  ]);
  fixture.handlers.focusin({ target: fixture.anchor });
  assert.equal(
    fixture.messages.find((message) => message.type === "citation").type,
    "citation",
  );
  assert.equal(
    fixture.messages.find((message) => message.type === "citation").citation.id,
    "1706.03762",
  );
  assert.equal(
    fixture.messages.find((message) => message.type === "citation").citation
      .reference,
    "[1] Attention Is All You Need. arXiv:1706.03762.",
  );
  assert.equal(fixture.classes.has("lens-citation-active"), true);
  assert.equal(fixture.popup.host.hidden, false);
});

test("unresolved references remain visible without inventing an arXiv ID", () => {
  const fixture = reader("[1] A journal-only publication.", []);
  fixture.handlers.focusin({ target: fixture.anchor });
  assert.equal(
    fixture.messages.find((message) => message.type === "citation").citation.id,
    null,
  );
  fixture.anchor.hash = "#S1";
  fixture.handlers.focusin({ target: fixture.anchor });
  assert.equal(
    fixture.messages.filter((message) => message.type === "citation").length,
    1,
  );
});

test("Escape dismisses the popup and does not reopen it on returned focus", () => {
  const fixture = reader("[1] A journal-only publication.", []);
  fixture.anchor.focus = () =>
    fixture.handlers.focusin({ target: fixture.anchor });
  fixture.handlers.focusin({ target: fixture.anchor });
  fixture.handlers.keydown({ key: "Escape" });
  assert.equal(fixture.popup.host.hidden, true);
});

test("bibliography entry markup accepts non-bib fragment names and full same-page links", () => {
  const fixture = reader("A reference.", [
    "https://doi.org/10.48550/arXiv.2207.01848",
  ]);
  fixture.anchor.hash = "#ref-article";
  fixture.anchor.getAttribute = () =>
    `https://arxiv.org/html/2303.08774${fixture.anchor.hash}`;
  fixture.handlers.focusin({ target: fixture.anchor });
  assert.equal(
    fixture.messages.find((message) => message.type === "citation").citation.id,
    "2207.01848",
  );
  const count = fixture.messages.length;
  fixture.anchor.getAttribute = () =>
    `https://other.example/html/2303.08774${fixture.anchor.hash}`;
  fixture.handlers.focusin({ target: fixture.anchor });
  assert.equal(fixture.messages.length, count);
});

test("each citation requests and displays its own paper and match despite document back-links", async () => {
  for (const id of ["2207.01848", "1706.03762"]) {
    const fixture = reader("A cited paper.", [
      "#bib.bib1",
      "https://arxiv.org/html/2303.08774#S2.p1.1",
      `https://arxiv.org/abs/${id}`,
    ]);
    fixture.handlers.focusin({ target: fixture.anchor });
    await new Promise((resolve) => setTimeout(resolve, 20));
    const paths = fixture.messages
      .filter(
        (message) => message.type === "api" && message.path !== "/api/status",
      )
      .map((message) => message.path);
    assert.deepEqual(paths, [
      `/api/paper?id=${id}`,
      `/api/paper-match?id=${id}`,
    ]);
    assert.equal(fixture.popup.papers[0].id, id);
    assert.equal(fixture.popup.papers[0].title, `Paper ${id}`);
    assert.equal(fixture.popup.matches[0].id, id);
    assert.equal(
      fixture.popup.matches[0].match,
      id === "2207.01848" ? 0.42 : 0.76,
    );
  }
});

test("page open prefetches once and rating notifications refresh scores only at the new snapshot", async () => {
  const status = {
    citation_session: "test",
    citation_revision: 0,
    citation_day: "2026-10-04",
    citation_changes: 0,
    tabpfn_configured: true,
    need_ratings: 0,
    ratings: {},
  };
  const fixture = reader(
    "A cited paper.",
    ["https://arxiv.org/abs/2207.01848"],
    { status, discover: true },
  );
  await new Promise((resolve) => setTimeout(resolve, 30));
  const requests = () =>
    fixture.messages.filter(
      (m) => m.type === "api" && m.path.startsWith("/api/paper-match"),
    ).length;
  assert.equal(requests(), 1);
  assert.equal(fixture.suggestions.reports.length, 1);
  assert.equal(fixture.suggestions.reports[0].papers[0].paper.id, "2207.01848");
  fixture.handlers.focusin({ target: fixture.anchor });
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal(fixture.popup.matches[0].id, "2207.01848");
  assert.equal(requests(), 1);
  status.citation_changes = 1;
  status.ratings["2207.01848"] = 1;
  fixture.handlers.runtimeMessage({ type: "changed" });
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal(requests(), 1);
  assert.equal(fixture.popup.rating, 1);
  assert.equal(fixture.suggestions.reports.length, 1);
  status.citation_revision = 1;
  status.citation_changes = 0;
  fixture.handlers.runtimeMessage({ type: "changed" });
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal(requests(), 2);
  assert.equal(fixture.suggestions.reports.length, 2);
  assert.equal(fixture.popup.matches.at(-1).rating, 1);
});

test("a DOI-only citation gains its correct paper identity and match after resolution", async () => {
  const fixture = reader("BERT. doi:10.18653/v1/N19-1423", [], {
    resolution: { state: "resolved", candidates: [{ id: "1810.04805" }] },
  });
  fixture.handlers.focusin({ target: fixture.anchor });
  await new Promise((resolve) => setTimeout(resolve, 30));
  const lookup = fixture.messages.find(
    (m) => m.path === "/api/resolve-reference",
  );
  assert.equal(lookup.body.doi, "10.18653/v1/N19-1423");
  assert.equal(
    fixture.messages.filter((m) => m.type === "citation").at(-1).citation.id,
    "1810.04805",
  );
  assert.equal(fixture.popup.matches.at(-1).id, "1810.04805");
});

test("a title match is selected and scored without user confirmation", async () => {
  const fixture = reader("BERT title reference.", [], {
    resolution: {
      state: "resolved",
      candidates: [{ id: "1810.04805", title: "BERT" }],
    },
  });
  fixture.handlers.focusin({ target: fixture.anchor });
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal(fixture.popup.resolutions.length, 0);
  assert.equal(
    fixture.messages.filter((m) => m.type === "citation").at(-1).citation.id,
    "1810.04805",
  );
  assert.equal(fixture.popup.matches.at(-1).id, "1810.04805");
});

test("references without arXiv links resolve and precompute matches before hovering", async () => {
  const status = {
    citation_session: "test",
    citation_revision: 0,
    citation_day: "2026-10-04",
    tabpfn_configured: true,
    need_ratings: 0,
    ratings: {},
  };
  const fixture = reader("BERT title reference.", [], {
    status,
    discover: true,
    resolution: {
      state: "resolved",
      candidates: [{ id: "1810.04805", title: "BERT" }],
    },
  });
  await new Promise((resolve) => setTimeout(resolve, 30));
  assert.equal(
    fixture.messages.filter((m) => m.path === "/api/resolve-reference").length,
    1,
  );
  assert.equal(
    fixture.messages.filter((m) => m.path === "/api/paper-match?id=1810.04805")
      .length,
    1,
  );
  assert.equal(fixture.suggestions.reports[0].papers[0].paper.id, "1810.04805");
  fixture.handlers.focusin({ target: fixture.anchor });
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal(fixture.popup.matches.at(-1).id, "1810.04805");
  assert.equal(
    fixture.messages.filter((m) => m.path === "/api/paper-match?id=1810.04805")
      .length,
    1,
  );
});

test("a recommendation opens the selected cited paper in Lens", async () => {
  const fixture = reader("A reference.", ["https://arxiv.org/abs/2207.01848"]);
  const selected = {
    id: "2207.01848",
    label: "[1]",
    reference: "A reference.",
    details: {},
  };
  fixture.suggestions.callbacks.onOpen(selected);
  assert.equal(
    fixture.messages.filter((m) => m.type === "citation").at(-1).citation,
    selected,
  );
  assert.equal(fixture.messages.at(-1).type, "open");
});
