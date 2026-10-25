import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";
const source = await readFile(
  new URL("../src/features/memora/language.ts", import.meta.url),
  "utf8",
);
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText;
const { describeSegmentLanguage } = await import(
  `data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`
);
const identity = (text) => text;
test("unknown provider language does not masquerade as selected or detected French", () => {
  const result = describeSegmentLanguage({ language: "unknown" }, identity);
  assert.equal(result.label, "Langue non déterminée");
  assert.match(result.hint, /ne fournit pas de langue détectée/);
  assert.match(result.hint, /ni de fiabilité chiffrée/);
  assert.doesNotMatch(result.label, /français|%/);
});
test("initial window metadata does not claim a per-segment language detection", () => {
  const result = describeSegmentLanguage(
    {
      language: "fr",
      language_scope: "initial_window_detection",
      language_confidence: null,
    },
    identity,
  );
  assert.equal(result.label, "Langue dominante : français");
  assert.match(result.hint, /début de l’audio/);
  assert.match(result.hint, /peut varier/);
  assert.doesNotMatch(result.label, /%/);
});
test("forced English is explicitly the selected language", () => {
  const result = describeSegmentLanguage(
    { language: "en", language_scope: "forced" },
    identity,
  );
  assert.equal(result.label, "Langue choisie : anglais");
  assert.match(result.hint, /sans détection/);
});
test("older per-segment language labels retain their existing representation", () => {
  assert.deepEqual(describeSegmentLanguage({ language: "en" }, identity), {
    label: "en",
    hint: undefined,
  });
});
test("labels and hints use the interface translator", () => {
  const labels = {
    "Langue dominante :": "Dominant language:",
    français: "French",
  };
  assert.equal(
    describeSegmentLanguage(
      { language: "fr", language_scope: "initial_window_detection" },
      (value) => labels[value] || value,
    ).label,
    "Dominant language: French",
  );
});

test("speech region detection describes the portion and unknown confidence honestly", () => {
  const result = describeSegmentLanguage(
    {
      language: "fr",
      language_scope: "speech_region_detection",
      language_confidence: null,
    },
    identity,
  );
  assert.equal(result.label, "Langue de la portion audio : français");
  assert.match(result.hint, /portion de parole/);
  assert.match(result.hint, /sans pause peuvent ne pas être détectés/);
  assert.match(result.hint, /fiabilité non chiffrée/);
  assert.doesNotMatch(result.label + result.hint, /%|chaque phrase/);
});
test("speech portion English label and uncertainty hint are translated", async () => {
  const dictionary = await readFile(
    new URL("../src/features/memora/i18n.ts", import.meta.url),
    "utf8",
  );
  const labels = {
    "Langue de la portion audio :": "Audio portion language:",
    anglais: "English",
    "Langue estimée pour cette portion de parole. Les changements sans pause peuvent ne pas être détectés ; fiabilité non chiffrée.":
      "Estimated language for this speech portion. Changes without a pause may not be detected; confidence is not quantified.",
  };
  for (const [key, value] of Object.entries(labels)) {
    assert.ok(
      dictionary.includes(JSON.stringify(key)) || dictionary.includes(key),
    );
    assert.ok(dictionary.includes(value));
  }
  const result = describeSegmentLanguage(
    {
      language: "en",
      language_scope: "speech_region_detection",
      language_confidence: null,
    },
    (value) => labels[value] || value,
  );
  assert.equal(result.label, "Audio portion language: English");
  assert.match(result.hint, /without a pause may not be detected/);
  assert.match(result.hint, /confidence is not quantified/);
});
