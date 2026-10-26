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
const { speakerLabel, hasUnresolvedSpeakerFailure } = await import(
  "data:text/javascript;base64," + Buffer.from(source).toString("base64")
);
test("Speaker failure survives text revisions, but not successful separation or complete manual attribution", () => {
  const meeting = {
    version: 3,
    automatic_diarization: { state: "failed", source_version: 1 },
    segments: [{ speaker: "Intervenant non identifié" }],
  };
  assert.equal(hasUnresolvedSpeakerFailure(meeting), true);
  assert.equal(hasUnresolvedSpeakerFailure({ ...meeting, diarization: { speaker_count: 2 } }), false);
  assert.equal(hasUnresolvedSpeakerFailure({ ...meeting, segments: [{ speaker: "Alice" }] }), false);
  assert.equal(hasUnresolvedSpeakerFailure({ ...meeting, automatic_diarization: { state: "completed", source_version: 3 } }), false);
  assert.equal(hasUnresolvedSpeakerFailure({ ...meeting, version: 0 }), false);
});
test("Unassigned labels never fabricate a speaker number", () => {
  for (const label of [
    null,
    undefined,
    "",
    "Intervenant non identifié",
    "Unidentified speaker",
    "unknown",
    "Voix à vérifier",
    "Voice to verify",
  ]) {
    assert.equal(speakerLabel(label), "Intervenant");
    assert.equal(speakerLabel(label, true), "Speaker");
  }
});
test("Actual numbered speakers and human names are preserved", () => {
  assert.equal(speakerLabel("Intervenant 2"), "Intervenant 2");
  assert.equal(speakerLabel("Intervenant 2", true), "Speaker 2");
  for (const label of ["Alice", "Unknown Artist", "Intervenant principal"])
    assert.equal(speakerLabel(label, true), label);
});
