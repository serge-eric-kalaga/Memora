import test from "node:test";
import assert from "node:assert/strict";
import ts from "typescript";
import { readFileSync } from "node:fs";
const source = ts.transpileModule(
  readFileSync(
    new URL("../src/features/memora/speaker-label.ts", import.meta.url),
    "utf8",
  ),
  { compilerOptions: { module: ts.ModuleKind.ES2022 } },
).outputText;
const { speakerLabel } = await import(
  "data:text/javascript;base64," + Buffer.from(source).toString("base64")
);
test("Unassigned labels never fabricate a speaker number", () => {
  for (const label of [
    null,
    undefined,
    "",
    "Intervenant non identifié",
    "Unidentified speaker",
    "unknown",
  ]) {
    assert.equal(speakerLabel(label), "Voix à vérifier");
    assert.equal(speakerLabel(label, true), "Voice to verify");
  }
});
test("Actual numbered speakers and human names are preserved", () => {
  assert.equal(speakerLabel("Intervenant 2"), "Intervenant 2");
  assert.equal(speakerLabel("Intervenant 2", true), "Speaker 2");
  for (const label of ["Alice", "Unknown Artist", "Intervenant principal"])
    assert.equal(speakerLabel(label, true), label);
});
