import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";
import { createInstance } from "i18next";

const root = fileURLToPath(new URL("../src", import.meta.url));
const dateSource = readFileSync(resolve(root, "lib/date.ts"), "utf8");
const dateModule = ts.transpileModule(dateSource, {
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText;
const { formatConnection } = await import(
  `data:text/javascript;base64,${Buffer.from(dateModule).toString("base64")}`
);
const fr = JSON.parse(readFileSync(resolve(root, "lib/i18n/locales/fr.json")));
const en = JSON.parse(readFileSync(resolve(root, "lib/i18n/locales/en.json")));

test("catalogues complets avec les mêmes variables d’interpolation", () => {
  assert.deepEqual(Object.keys(fr).sort(), Object.keys(en).sort());
  for (const key of Object.keys(fr)) {
    assert.ok(fr[key].trim() && en[key].trim(), `Traduction vide : ${key}`);
    const variables = (value) =>
      [...value.matchAll(/{{\s*([^}]+)\s*}}/g)]
        .map((match) => match[1].trim())
        .sort();
    assert.deepEqual(variables(fr[key]), variables(en[key]), key);
  }
});

test("toutes les clés littérales utilisées par les composants sont traduites", () => {
  function visitDirectory(directory) {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const path = resolve(directory, entry.name);
      if (entry.isDirectory()) {
        visitDirectory(path);
        continue;
      }
      if (!path.endsWith(".tsx")) continue;
      const file = ts.createSourceFile(
        path,
        readFileSync(path, "utf8"),
        ts.ScriptTarget.Latest,
        true,
        ts.ScriptKind.TSX,
      );
      function visit(node) {
        if (
          ts.isCallExpression(node) &&
          node.expression.getText(file) === "t" &&
          node.arguments[0] &&
          ts.isStringLiteral(node.arguments[0])
        ) {
          assert.ok(
            node.arguments[0].text in fr,
            `${entry.name} : ${node.arguments[0].text}`,
          );
        }
        ts.forEachChild(node, visit);
      }
      visit(file);
    }
  }
  visitDirectory(root);
});

test("traduction anglaise, interpolation et repli français", async () => {
  const instance = createInstance();
  await instance.init({
    resources: { fr: { translation: fr }, en: { translation: en } },
    lng: "en",
    fallbackLng: "fr",
    keySeparator: false,
    nsSeparator: false,
  });
  assert.equal(instance.t("Se connecter"), "Sign in");
  assert.equal(
    instance.t("Bonjour, {{username}}", { username: "demo" }),
    "Hello, demo",
  );
  await instance.changeLanguage("fr");
  assert.equal(instance.t("Se connecter"), "Se connecter");
  await instance.changeLanguage("xx");
  assert.equal(instance.t("Se connecter"), "Se connecter");
});

test("dates affichées selon la langue et valeurs absentes ou invalides", () => {
  assert.match(formatConnection("2026-10-19T12:00:00Z", "en"), /Oct/);
  assert.match(formatConnection("2026-10-19T12:00:00Z", "fr"), /oct\./);
  assert.equal(formatConnection(null, "en"), "First sign-in");
  assert.equal(formatConnection("invalid", "fr"), "Date indisponible");
});
