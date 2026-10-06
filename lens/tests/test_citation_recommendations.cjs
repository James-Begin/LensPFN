const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(
  path.join(__dirname, "../extension/citation-recommendations.js"),
  "utf8",
);
function runtime() {
  const context = {};
  vm.runInNewContext(source, context);
  return context.LensCitationRecommendations;
}
function make(prefetch, currentId = "reading") {
  const context = {};
  vm.runInNewContext(source, context);
  const reports = [],
    resolved = [];
  const batch = context.LensCitationRecommendations.create({
    prefetch,
    currentId,
    onComplete: (report) => reports.push(report),
    onResolved: (reference, id) => resolved.push([reference, id]),
  });
  return { batch, reports, resolved };
}
const citation = (id, reference = id) => ({
  id,
  reference,
  label: "[1]",
  details: {},
});
const tick = () => new Promise((resolve) => setTimeout(resolve, 5));

test("completion waits for every reference and ranks actual scores once per paper", async () => {
  let release;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  const calls = [];
  const prefetch = {
    paper: async (id) => ({ id, title: id }),
    match: async (id) => {
      calls.push(id);
      if (id === "slow") await gate;
      return { match: id === "slow" ? 0.9 : 0.4 };
    },
    resolve: async () => ({ state: "resolved", candidates: [{ id: "slow" }] }),
  };
  const { batch, reports, resolved } = make(prefetch);
  const finished = batch.run([
    citation("fast"),
    citation("fast"),
    citation("slow"),
    citation(null, "resolved by title"),
  ]);
  await tick();
  assert.equal(reports.length, 0);
  release();
  await finished;
  assert.equal(reports.length, 1);
  assert.deepEqual(
    Array.from(reports[0].papers, (row) => row.paper.id),
    ["slow", "fast"],
  );
  assert.equal(calls.filter((id) => id === "slow").length, 1);
  assert.deepEqual(resolved, [["resolved by title", "slow"]]);
});

test("missing references, failed requests and unavailable scores do not block completion", async () => {
  const prefetch = {
    paper: async (id) => ({ id, title: id }),
    match: async (id) => {
      if (id === "failed") throw new Error("Unavailable");
      return { match: id === "no-score" ? null : 0.7 };
    },
    resolve: async () => ({ state: "unresolved", candidates: [] }),
  };
  const { batch, reports } = make(prefetch);
  await batch.run([
    citation("good"),
    citation("failed"),
    citation("no-score"),
    citation(null, "journal only"),
    citation("reading"),
  ]);
  assert.equal(reports[0].unavailable, 3);
  assert.deepEqual(
    Array.from(reports[0].papers, (row) => row.paper.id),
    ["good"],
  );
});

test("a previous snapshot finishing late never replaces the refreshed recommendations", async () => {
  let release;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  const prefetch = {
    paper: async (id) => ({ id, title: id }),
    match: async (id) => {
      if (id === "old") await gate;
      return { match: 0.8 };
    },
  };
  const { batch, reports } = make(prefetch);
  const previous = batch.run([citation("old")]);
  batch.invalidate();
  await batch.run([citation("new")]);
  release();
  await previous;
  assert.equal(reports.length, 1);
  assert.equal(reports[0].papers[0].paper.id, "new");
});

test("incorrect identities and non-finite probabilities never become recommendations", async () => {
  const prefetch = {
    paper: async (id) => ({ id: id === "wrong" ? "other" : id, title: id }),
    match: async (id) => ({
      match: id === "nan" ? NaN : id === "outside" ? 1.2 : 0.5,
    }),
  };
  const { batch, reports } = make(prefetch);
  await batch.run([citation("wrong"), citation("nan"), citation("outside")]);
  assert.equal(reports[0].papers.length, 0);
  assert.equal(reports[0].unavailable, 3);
});

test("a failed metadata request still waits for its outstanding score before completion", async () => {
  let release;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  const prefetch = {
    paper: async () => {
      throw new Error("Metadata unavailable");
    },
    match: async () => {
      await gate;
      return { match: 0.7 };
    },
  };
  const { batch, reports } = make(prefetch);
  const finished = batch.run([citation("slow")]);
  await tick();
  assert.equal(reports.length, 0);
  release();
  await finished;
  assert.equal(reports[0].unavailable, 1);
});

test("remaining references sum probabilities once and drop either kind of rating", () => {
  const { remaining } = runtime();
  const rows = [
    { paper: { id: "a" }, match: 0.9, rating: 0 },
    { paper: { id: "a" }, match: 0.9, rating: 0 },
    { paper: { id: "b" }, match: 0.6, rating: 0 },
    { paper: { id: "c" }, match: 0.8, rating: 1 },
  ];
  const report = { papers: rows, total: 6, unavailable: 2, checked: 5 };
  assert.equal(remaining(report).expected, 1.5);
  const next = remaining(report, { a: 1, b: -1 });
  assert.equal(next.unrated, 1);
  assert.equal(next.expected, 0.8);
  assert.equal(next.scored, 3);
  assert.equal(next.unavailable, 2);
  assert.equal(next.checked, 5);
  assert.equal(remaining({ ...report, papers: [] }).expected, 0);
});

test("progress publishes only the current batch and retains unresolved coverage", async () => {
  const reports = [];
  let first;
  const prefetch = {
    paper: (id) => Promise.resolve({ id, title: id }),
    match: (id) => Promise.resolve({ match: 0.75, rating: 0 }),
    resolve: () => Promise.resolve({ state: "unresolved" }),
  };
  const recommendations = runtime().create({
    prefetch,
    onResolved() {},
    onComplete: (report) => {
      first = report;
    },
    onProgress: (report) => reports.push(report),
  });
  await recommendations.run([
    { id: "a", reference: "a" },
    { id: null, reference: "unknown" },
  ]);
  assert.equal(reports.length, 2);
  assert.equal(reports.at(-1).checked, 2);
  assert.equal(reports.at(-1).unavailable, 1);
  assert.equal(first.total, 2);
});
