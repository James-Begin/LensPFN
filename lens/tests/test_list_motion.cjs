const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs
  .readFileSync(
    require("node:path").join(__dirname, "../extension/list-motion.js"),
    "utf8",
  )
  .replace("export function", "function");
const scope = {};
vm.createContext(scope);
vm.runInContext(source, scope);
const calls = [];
function row(id, top) {
  return {
    dataset: { paperId: id },
    getAnimations: () => [],
    getBoundingClientRect: () => ({ top }),
    animate: (frames, options) => calls.push({ frames, options }),
  };
}
function list(children) {
  return {
    children,
    replaceChildren(...rows) {
      this.children = rows;
    },
  };
}
test("reduced motion replaces the list immediately without spatial animation", () => {
  calls.length = 0;
  const target = list([row("old", 20)]);
  const next = [row("new", 20)];
  scope.replacePaperList(target, next, { animate: true, reducedMotion: true });
  assert.equal(target.children[0], next[0]);
  assert.equal(calls.length, 0);
});
test("reranking moves familiar papers and caps arrival delay for new papers", () => {
  calls.length = 0;
  const target = list([row("keep", 100)]);
  const next = [
    row("keep", 20),
    ...Array.from({ length: 20 }, (_, i) => row("new" + i, 100 + i * 20)),
  ];
  scope.replacePaperList(target, next, { animate: true, reducedMotion: false });
  assert.equal(calls[0].frames[0].transform, "translateY(80px)");
  assert.equal(calls.length, 21);
  assert.ok(calls.slice(1).every((call) => call.options.delay <= 168));
});
