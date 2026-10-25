import test from "node:test";
import assert from "node:assert/strict";
import ts from "typescript";
import { readFileSync } from "node:fs";
const source = ts.transpileModule(
  readFileSync(
    new URL("../src/features/memora/chat-answer.ts", import.meta.url),
    "utf8",
  ),
  { compilerOptions: { module: ts.ModuleKind.ES2022 } },
).outputText;
const { readableChatAnswer } = await import(
  "data:text/javascript;base64," + Buffer.from(source).toString("base64")
);
test("Internal citation groups disappear without changing facts, paragraphs or domain identifiers", () => {
  assert.equal(
    readableChatAnswer(
      "Accès limité (u3), puis attente (u28, u29).\n\nBudget (2026) : 100 euros. USB u3 conservé.",
    ),
    "Accès limité, puis attente.\n\nBudget (2026) : 100 euros. USB u3 conservé.",
  );
  assert.equal(
    readableChatAnswer("**Action** [u9; u10] : vérifier."),
    "**Action** : vérifier.",
  );
  assert.equal(
    readableChatAnswer("Texte (utile), unité u3 et <script>x</script>."),
    "Texte (utile), unité u3 et <script>x</script>.",
  );
});
