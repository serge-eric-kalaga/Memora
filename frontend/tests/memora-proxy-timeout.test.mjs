import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";
const source = await readFile(
  new URL("../src/app/mapi/[...path]/timeout.ts", import.meta.url),
  "utf8",
);
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText;
const { proxyTimeoutMs } = await import(
  `data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`
);
const chat = ["meetings", "synthetic", "chat"];
test("chat default supports long source batches without changing REST deadlines", () => {
  assert.equal(proxyTimeoutMs("POST", chat), 600000);
  assert.equal(proxyTimeoutMs("GET", ["settings"], "1000"), 120000);
  assert.equal(
    proxyTimeoutMs("POST", ["meetings", "synthetic", "analyze"], "1800000"),
    120000,
  );
  assert.equal(proxyTimeoutMs("GET", chat, "1000"), 120000);
});
test("chat deadline is configured, bounded and safe on invalid values", () => {
  assert.equal(proxyTimeoutMs("POST", chat, "1000"), 1000);
  assert.equal(proxyTimeoutMs("POST", chat, "0"), 1000);
  assert.equal(proxyTimeoutMs("POST", chat, "9999999"), 1800000);
  assert.equal(proxyTimeoutMs("POST", chat, "bad"), 600000);
  assert.equal(proxyTimeoutMs("POST", chat, "  "), 600000);
});
