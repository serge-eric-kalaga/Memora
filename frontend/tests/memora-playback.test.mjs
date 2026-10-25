import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";
const source = await readFile(
  new URL("../src/features/memora/playback.ts", import.meta.url),
  "utf8",
);
const code = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2023,
  },
}).outputText;
const { segmentAt, adjacentSegment, loopRange } = await import(
  `data:text/javascript;base64,${Buffer.from(code).toString("base64")}`
);
const segments = [
  { id: "a", start: 0, end: 2 },
  { id: "b", start: 3, end: 5 },
  { id: "c", start: 5, end: 9 },
];
test("highlights speech boundaries without filling silence", () => {
  assert.equal(segmentAt(segments, 0)?.id, "a");
  assert.equal(segmentAt(segments, 2), undefined);
  assert.equal(segmentAt(segments, 5)?.id, "c");
  assert.equal(segmentAt(segments, 9), undefined);
  assert.equal(segmentAt(segments, NaN), undefined);
});
test("navigation respects gaps and ends", () => {
  assert.equal(adjacentSegment(segments, 1, 1)?.id, "b");
  assert.equal(adjacentSegment(segments, 2.5, 1)?.id, "b");
  assert.equal(adjacentSegment(segments, 2.5, -1)?.id, "a");
  assert.equal(adjacentSegment(segments, 0, -1), undefined);
  assert.equal(adjacentSegment(segments, 8, 1), undefined);
});
test("loop clamps audio and rejects invalid intervals", () => {
  assert.deepEqual(loopRange(segments[2], 7), { start: 5, end: 7 });
  assert.equal(loopRange(segments[2], 4), null);
  assert.equal(loopRange(segments[0], Infinity), null);
  assert.equal(loopRange({ id: "a", start: 1, end: 1.01 }, 5), null);
  assert.equal(loopRange(undefined, 5), null);
});
