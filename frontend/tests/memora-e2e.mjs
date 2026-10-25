/** Local real end-to-end recipe. Only synthetic fixtures and Chromium's fake microphone. */
import { chromium } from "@playwright/test";
import assert from "node:assert/strict";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { resolve, dirname } from "node:path";
const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const base = process.env.MEMORA_UI_URL || "http://localhost:3000";
const artifactPrefix = process.env.MEMORA_TEST_ARTIFACT_PREFIX || "";
if (!/^[A-Za-z0-9_-]*$/.test(artifactPrefix))
  throw new Error("Invalid test artifact prefix");
const artifactPath = (folder, name) =>
  resolve(root, "agents", folder, artifactPrefix + name);
const account = JSON.parse(
  await readFile(
    resolve(root, process.env.MEMORA_TEST_CREDENTIALS || ".memora/demo.json"),
    "utf8",
  ),
);
const fixture = resolve(root, "backend/test/fixtures/memora/mixed-native.wav");
const reports = [];
const errors = [];
const pass = (label) => {
  reports.push(label);
  console.log("PASS", label);
};
const browser = await chromium.launch({
  headless: true,
  ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
    ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
    : {}),
  args: [
    "--use-fake-device-for-media-stream",
    "--use-fake-ui-for-media-stream",
    `--use-file-for-fake-audio-capture=${fixture}`,
  ],
});
const owner = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  permissions: ["microphone"],
});
const page = await owner.newPage();
page.on("pageerror", (e) => errors.push(e.message));
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function ready() {
  await page
    .getByRole("heading", { name: "Résumé", exact: true })
    .waitFor({ timeout: 180000 });
}
async function create(title, mode, language = "auto") {
  await page.goto(base + "/");
  await page
    .getByRole("button", { name: "Nouvelle réunion", exact: true })
    .click();
  await page.getByRole("dialog").getByRole("textbox").fill(title);
  // The default fixture alternates languages; the dedicated French case overrides it.
  await page
    .getByRole("dialog")
    .getByRole("combobox", { name: /^Langue de l’audio/ })
    .selectOption(language);
  await page
    .getByRole("button", {
      name: mode === "import" ? "Importer un audio" : "Enregistrer",
      exact: true,
    })
    .click();
  await page.waitForURL(/\/reunions\//);
  return page.url();
}
try {
  await page.goto(base + "/connexion");
  await page.locator("input[name=username]").fill(account.username);
  await page.locator("input[name=password]").fill(account.password);
  await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await page.waitForURL(base + "/", { timeout: 30000 });
  await page
    .getByRole("button", { name: "Nouvelle réunion", exact: true })
    .waitFor();
  pass("Authentification réelle et dashboard");
  await create("Recette UI complète synthétique", "import");
  await page.locator("input[type=file]").setInputFiles(fixture);
  await ready();
  pass("Import navigateur → Whisper → Ollama → rapport persisté");
  await page.screenshot({
    path: artifactPath("logs", "browser-report-desktop.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Chat IA", exact: true }).click();
  await page
    .locator("#meeting-chat-panel")
    .getByRole("textbox", { name: "Votre question", exact: true })
    .fill("Qui prépare la démonstration ?");
  await page
    .locator("#meeting-chat-panel")
    .getByRole("button", { name: "Poser la question", exact: true })
    .click();
  await page
    .locator("#meeting-chat-panel")
    .getByText(/Alice/)
    .last()
    .waitFor({ timeout: 180000 });
  pass("Chat réel rendu avec source");
  await page
    .getByRole("button", { name: "Transcription", exact: true })
    .click();
  await page.getByRole("button", { name: "Corriger", exact: true }).click();
  await page
    .getByRole("textbox", { name: "Passage 1", exact: true })
    .fill(
      "Bonjour, nous décidons de lancer le projet Memora lundi. Alice préparera la démonstration vendredi.",
    );
  await page
    .getByRole("textbox", { name: "Intervenant 1", exact: true })
    .fill("Camille (synthétique)");
  await page
    .getByRole("button", { name: "Enregistrer les corrections", exact: true })
    .click();
  await page.getByText(/Le rapport est à actualiser/).waitFor();
  await page.getByRole("button", { name: "Chat IA", exact: true }).click();
  await page.getByText(/Ancienne source/).waitFor();
  pass("Correction versionnée, rapport périmé et ancien chat identifié");
  await page
    .getByRole("button", { name: "Régénérer le rapport", exact: true })
    .click();
  await page.getByRole("button", { name: "Rapport", exact: true }).click();
  await page
    .getByRole("combobox", { name: "Version du rapport" })
    .locator("option")
    .filter({ hasText: /Version\s*2/ })
    .waitFor({ state: "attached", timeout: 180000 });
  assert.equal(
    await page
      .getByRole("combobox", { name: "Version du rapport" })
      .locator("option")
      .count(),
    2,
  );
  pass("Régénération réelle et deux versions consultables");
  await page.getByRole("button", { name: "Partager", exact: true }).click();
  await page
    .getByRole("button", { name: "Créer le lien", exact: true })
    .click();
  const link = await page
    .getByRole("textbox", { name: "Lien de partage", exact: true })
    .inputValue();
  const guest = await browser.newContext({
    viewport: { width: 390, height: 844 },
  });
  const gp = await guest.newPage();
  gp.on("pageerror", (e) => errors.push(e.message));
  assert.equal(
    new URL(link, base).origin,
    new URL(base).origin,
    "Guest link must stay on the configured test instance",
  );
  await gp.goto(new URL(link, base).toString());
  await gp
    .getByRole("heading", { name: "Résumé", exact: true })
    .waitFor({ timeout: 30000 });
  assert.equal(
    await gp.getByRole("button", { name: "Archiver", exact: true }).count(),
    0,
  );
  assert.equal(
    await gp.evaluate(() => document.documentElement.scrollWidth > innerWidth),
    false,
  );
  await gp.screenshot({
    path: artifactPath("logs", "browser-guest-mobile.png"),
    fullPage: true,
  });
  pass("Invité sans compte, contenus autorisés et responsive mobile");
  await page.getByRole("button", { name: "Fermer", exact: true }).click();
  await page.getByRole("button", { name: "Partager", exact: true }).click();
  await page
    .getByRole("button", { name: "Révoquer", exact: true })
    .last()
    .click();
  await gp.reload();
  await gp
    .getByRole("alert")
    .filter({ hasText: /indisponible|révoqué|expiré/ })
    .waitFor({ timeout: 20000 });
  pass("Révocation observable dans page invitée déjà ouverte");
  await guest.close();
  await page.getByRole("button", { name: "Fermer", exact: true }).click();
  await page.getByRole("button", { name: "Archiver", exact: true }).click();
  await page.getByRole("button", { name: "Restaurer", exact: true }).waitFor();
  await page.getByRole("button", { name: "Restaurer", exact: true }).click();
  pass("Archivage et restauration navigateur");
  // Capture never opens the physical microphone: Chromium flags supply only the WAV fixture.
  await create("Recette capture synthétique pause réseau", "recording");
  await page.getByRole("button", { name: "Enregistrer", exact: true }).click();
  await page.getByRole("button", { name: "Pause", exact: true }).waitFor();
  await page.getByText(/1 fragments confirmés/).waitFor({ timeout: 30000 });
  await page
    .getByRole("heading", { name: /Transcription en direct/ })
    .waitFor({ timeout: 180000 });
  pass(
    "Capture synthétique, fragment confirmé et transcription en direct réelle",
  );
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  const timer = page.locator('[class*="timer"]').first();
  const paused = await timer.innerText();
  await sleep(2500);
  assert.equal(await timer.innerText(), paused);
  await page.getByRole("button", { name: "Reprendre", exact: true }).click();
  await owner.setOffline(true);
  await sleep(12000);
  await page.getByText(/Audio conservé sur cet appareil/).waitFor();
  assert.match(
    await page.locator("body").innerText(),
    /[1-9]\d* en attente locale/,
  );
  pass(
    "Pause fige durée ; coupure réseau signalée sans faux accusé de sauvegarde",
  );
  await owner.setOffline(false);
  await page
    .getByRole("button", { name: "Reprendre la sauvegarde", exact: true })
    .click();
  await page.getByText(/0 en attente locale/).waitFor();
  await page
    .getByRole("button", { name: "Terminer et analyser", exact: true })
    .click();
  await ready();
  pass("Reprise fragments, finalisation et rapport réel après capture");
  if (
    process.env.MEMORA_TEST_ISOLATED === "1" &&
    process.env.MEMORA_FRENCH_ASR_ENGINE === "parakeet-mlx"
  ) {
    await create("Recette française synthétique", "import", "fr");
    await page.locator("input[type=file]").setInputFiles(
      resolve(root, "backend/test/fixtures/memora/french.wav"),
    );
    await ready();
    await page.getByRole("button", { name: "Transcription", exact: true }).click();
    const unknown = page.getByText("Langue non déterminée", { exact: true }).first();
    await unknown.waitFor();
    assert.match(await unknown.getAttribute("title"), /ne fournit pas de langue détectée/);
    await page.getByRole("button", { name: "Corriger", exact: true }).click();
    await page.getByRole("textbox", { name: "Intervenant 1", exact: true }).fill("Voix synthétique");
    await page.getByRole("button", { name: "Enregistrer les corrections", exact: true }).click();
    await page.getByText(/Le rapport est à actualiser/).waitFor();
    await page.getByText("Voix synthétique", { exact: true }).first().waitFor();
    pass("Import français réel, langue non inventée et correction persistée dans le navigateur");
    await page.screenshot({ path: artifactPath("logs", "browser-french-transcript.png"), fullPage: true });
  }
  assert.deepEqual(errors, []);
  pass("Aucune exception JavaScript non gérée");
  await mkdir(resolve(root, "agents/handoffs"), { recursive: true });
  await writeFile(
    artifactPath("handoffs", "browser.md"),
    "# Recette navigateur réelle\n\n" +
      new Date().toISOString() +
      "\n\n" +
      reports.map((x) => "- VALIDÉ : " + x).join("\n") +
      "\n\nChromium headless ordinateur 1440×1000 et mobile 390×844. Microphone exclusivement synthétique ; pas de validation appareil physique, veille réelle ou Safari/iOS. Aucun token/password conservé dans ce rapport. Captures locales dans agents/logs, ignorées de Git.\n",
  );
} catch (error) {
  const safeUrl = new URL(page.url());
  safeUrl.pathname = safeUrl.pathname.replace(
    /\/partage\/[A-Za-z0-9_-]+/g,
    "/partage/[token]",
  );
  safeUrl.search = "";
  safeUrl.hash = "";
  console.error("Échec sur la page", safeUrl.toString());
  try {
    await mkdir(resolve(root, "agents/logs"), { recursive: true });
    await page.screenshot({
      path: artifactPath("logs", "browser-failure.png"),
      fullPage: true,
      mask: [
        page.locator('input[type="password"]'),
        page.getByRole("textbox", { name: "Lien de partage", exact: true }),
      ],
    });
    console.error(
      `Capture locale masquée : agents/logs/${artifactPrefix}browser-failure.png`,
    );
  } catch {
    console.error("Capture de diagnostic indisponible.");
  }
  console.error(
    String(error.stack || error)
      .replaceAll(account.password, "[redacted]")
      .replace(/\/partage\/[A-Za-z0-9_-]+/g, "/partage/[token]"),
  );
  process.exitCode = 1;
} finally {
  await browser.close();
}
