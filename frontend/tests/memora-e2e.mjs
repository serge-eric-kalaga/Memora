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
page.on("pageerror", (e) => {
  errors.push(e.message);
  console.error(
    "Browser exception",
    JSON.stringify({
      url: new URL(page.url()).pathname,
      lastCheckpoint: reports.at(-1),
      message: e.message,
      stack: e.stack,
    }),
  );
});
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function ready() {
  await page
    .getByRole("heading", { name: "Résumé", exact: true })
    .waitFor({ timeout: 180000 });
}
async function meetingData() {
  const id = new URL(page.url()).pathname.split("/").filter(Boolean).at(-1);
  const response = await owner.request.get(`${base}/mapi/meetings/${id}`);
  assert.equal(response.status(), 200);
  return response.json();
}
async function automaticSpeakers() {
  if (process.env.MEMORA_TEST_ISOLATED !== "1") return;
  const meeting = await meetingData();
  assert.equal(meeting.settings.auto_diarization_new_meetings, true);
  assert.equal(meeting.automatic_diarization.state, "completed");
  assert.equal(meeting.version, 2);
  assert.equal(meeting.report_version, meeting.version);
  assert.equal(
    meeting.diarization.engine,
    process.env.MEMORA_DIARIZATION_ENGINE === "ecapa-tdnn"
      ? "ecapa-silero-ahc-v1"
      : "resemblyzer-silero-ahc-v2",
  );
  const labeled = meeting.segments.filter((segment) => segment.speaker_id);
  assert.ok(
    labeled.length > 0,
    "Real synthetic audio must produce a speaker group",
  );
  for (const segment of labeled) {
    assert.match(segment.speaker, /^Intervenant [1-9][0-9]*$/);
    assert.equal(segment.speaker_uncertain, false);
    assert.equal(segment.speaker_provenance.engine, meeting.diarization.engine);
    assert.match(segment.speaker_provenance.model_sha256, /^[a-f0-9]{64}$/);
  }
  const id = meeting.id;
  const response = await owner.request.get(
    `${base}/mapi/meetings/${id}/transcript?version=1`,
  );
  assert.equal(response.status(), 200);
  const original = await response.json();
  assert.equal(original.segments.length, meeting.segments.length);
  for (let index = 0; index < original.segments.length; index++) {
    const before = original.segments[index];
    const after = meeting.segments[index];
    assert.ok(!before.speaker_id, "ASR source must not invent a speaker group");
    for (const key of ["id", "start", "end", "text"])
      assert.deepEqual(after[key], before[key]);
  }
  pass(
    "Intervenants automatiques réels : provenance locale, source ASR v1 conservée et rapport v2",
  );
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
  const originalMeetingUrl = await create(
    "Recette UI complète synthétique",
    "import",
  );
  await page.locator("input[type=file]").setInputFiles(fixture);
  await ready();
  pass("Import navigateur → Whisper → Ollama → rapport persisté");
  await automaticSpeakers();
  const humanReview = page.locator('[data-testid^="human-review-"]').first();
  await humanReview
    .getByRole("button", { name: "Valider cet élément", exact: true })
    .click();
  await humanReview
    .getByLabel("Statut", { exact: true })
    .selectOption("confirmed");
  await humanReview
    .getByRole("button", {
      name: "Enregistrer la validation humaine",
      exact: true,
    })
    .click();
  await humanReview.getByText("Confirmé", { exact: true }).waitFor();
  await humanReview
    .getByRole("button", { name: "Historique des validations", exact: true })
    .click();
  await humanReview.locator("ol li").first().waitFor();
  pass(
    "Validation humaine persistée séparément du rapport IA, historique accessible",
  );
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
    .locator('[class*="answerBody"]')
    .filter({ hasText: /Alice/ })
    .waitFor({ timeout: 180000 });
  const chatPanel = page.locator("#meeting-chat-panel");
  assert.ok(await chatPanel.isVisible());
  assert.equal(
    await page.getByRole("heading", { name: "Résumé", exact: true }).count(),
    0,
  );
  assert.ok(
    await chatPanel.evaluate(
      (element) =>
        !!(
          element.compareDocumentPosition(
            Array.from(document.querySelectorAll("h2")).find(
              (heading) => heading.textContent === "Audio de la réunion",
            ),
          ) & Node.DOCUMENT_POSITION_FOLLOWING
        ),
    ),
  );
  await page.setViewportSize({ width: 390, height: 844 });
  const chatBox = await chatPanel.boundingBox();
  const audioBox = await page
    .getByRole("heading", { name: "Audio de la réunion", exact: true })
    .boundingBox();
  assert.ok(chatBox && audioBox && chatBox.y < audioBox.y);
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
    false,
  );
  await page.screenshot({
    path: artifactPath("logs", "browser-chat-mobile.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.reload();
  await page.getByRole("button", { name: "Chat IA", exact: true }).click();
  await page
    .locator("#meeting-chat-panel")
    .getByText("Qui prépare la démonstration ?", { exact: false })
    .waitFor();
  await page.locator('#meeting-chat-panel [class*="answerBody"]').filter({hasText:/Alice/}).waitFor();
  pass(
    "Chat réel prioritaire desktop/mobile, source et conversation restaurée après actualisation",
  );
  await page
    .getByRole("button", { name: "Transcription", exact: true })
    .click();
  const tools = page.getByLabel("Outils de lecture de transcription", {
    exact: true,
  });
  await tools.waitFor();
  if (process.env.MEMORA_TEST_ISOLATED === "1") {
    assert.ok(
      await page
        .locator("strong")
        .filter({ hasText: /^Intervenant [1-9][0-9]*$/ })
        .count(),
    );
  }
  await page
    .locator("audio")
    .first()
    .evaluate(async (audio) => {
      if (audio.readyState < 1)
        await new Promise((resolve) =>
          audio.addEventListener("loadedmetadata", resolve, { once: true }),
        );
    });
  await tools
    .getByRole("combobox", { name: "Vitesse de lecture", exact: true })
    .selectOption("0.75");
  assert.equal(
    await page
      .locator("audio")
      .first()
      .evaluate((audio) => audio.playbackRate),
    0.75,
  );
  await tools
    .getByRole("button", { name: "Écouter le passage en boucle", exact: true })
    .click();
  await tools
    .getByRole("button", { name: "Arrêter la boucle", exact: true })
    .waitFor();
  await page.waitForFunction(() =>
    document.querySelector('[data-segment-start][class*="selectedSegment"]'),
  );
  const nextPassage = page.locator("[data-segment-start]").nth(1);
  const expectedStart = Number(
    await nextPassage.getAttribute("data-segment-start"),
  );
  await nextPassage.getByRole("button").first().click();
  await tools
    .getByRole("button", { name: "Écouter le passage en boucle", exact: true })
    .waitFor();
  assert.ok(
    await page
      .locator("audio")
      .first()
      .evaluate(
        (audio, start) =>
          audio.currentTime >= start && audio.currentTime < start + 2,
        expectedStart,
      ),
  );
  await tools.focus();
  await page.keyboard.press("Alt+Space");
  assert.equal(
    await page
      .locator("audio")
      .first()
      .evaluate((audio) => audio.paused),
    true,
  );
  pass(
    "Lecture synchronisée : surlignage, vitesse, boucle, saut externe libéré et raccourci clavier",
  );
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
    .getByText("Comparer cette correction", { exact: true })
    .first()
    .click();
  assert.ok(await page.locator("del").first().isVisible());
  assert.ok(await page.locator("ins").first().isVisible());
  pass("Comparaison avant/après affichée sans écraser la source");
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
  const captureUrl = await create(
    "Recette capture synthétique pause réseau",
    "recording",
  );
  await page
    .getByRole("button", { name: "Tester le microphone", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Arrêter le test", exact: true })
    .waitFor();
  assert.equal(
    await page
      .getByRole("button", { name: "Enregistrer", exact: true })
      .isDisabled(),
    true,
  );
  await page
    .getByRole("button", {
      name: "Enregistrer un échantillon (10 s max.)",
      exact: true,
    })
    .click();
  await sleep(1200);
  await page
    .getByRole("button", { name: "Terminer l’échantillon", exact: true })
    .click();
  await page
    .getByText("Réécouter votre échantillon", { exact: true })
    .waitFor();
  await page
    .getByRole("button", { name: "Arrêter le test", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Enregistrer", exact: true })
    .waitFor({ state: "visible" });
  assert.equal(
    await page
      .getByRole("button", { name: "Enregistrer", exact: true })
      .isEnabled(),
    true,
  );
  pass(
    "Contrôle microphone factice, échantillon local et arrêt avant capture réunion",
  );
  await page.evaluate(() => {
    window.__captureProof = { requests: 0, stopped: 0 };
    const original = navigator.mediaDevices.getUserMedia.bind(
      navigator.mediaDevices,
    );
    navigator.mediaDevices.getUserMedia = async (constraints) => {
      window.__captureProof.requests++;
      const stream = await original(constraints);
      for (const track of stream.getTracks()) {
        const stop = track.stop.bind(track);
        track.stop = () => {
          window.__captureProof.stopped++;
          stop();
        };
      }
      return stream;
    };
  });
  await page.getByRole("button", { name: "Enregistrer", exact: true }).click();
  await page.getByRole("button", { name: "Pause", exact: true }).waitFor();
  const recordingSignal = page.getByRole("region", {
    name: "Signal audio de l’enregistrement",
    exact: true,
  });
  await recordingSignal.waitFor();
  await recordingSignal
    .getByText("Enregistrement en cours", { exact: true })
    .waitFor({ timeout: 30000 });
  // The first "receiving" frame may still contain silence while the fake
  // device starts. Require a real non-zero measured level, with a bounded wait.
  await page.waitForFunction(
    () => {
      const meter = document.querySelector(
        '[aria-label="Signal audio de l’enregistrement"] meter[aria-label="Niveau audio capté"]',
      );
      return meter instanceof HTMLMeterElement && meter.value > 0;
    },
    null,
    { timeout: 30000 },
  );
  assert.ok(
    Number(
      await recordingSignal
        .getByRole("meter", { name: "Niveau audio capté", exact: true })
        .getAttribute("value"),
    ) > 0,
  );
  await page.getByText(/1 fragments confirmés/).waitFor({ timeout: 30000 });
  await page
    .getByRole("heading", { name: /Transcription en direct/ })
    .waitFor({ timeout: 180000 });
  pass(
    "Capture synthétique, fragment confirmé et transcription en direct réelle",
  );
  const sourceBeforeNavigation = await meetingData();
  assert.ok(Array.isArray(sourceBeforeNavigation.chunks));
  const chunksBeforeNavigation = sourceBeforeNavigation.chunks.length;
  const bytesBeforeNavigation = sourceBeforeNavigation.chunks.reduce(
    (total, chunk) => total + chunk.bytes,
    0,
  );
  await page.getByRole("link", { name: "Mes réunions", exact: true }).click();
  await page.waitForURL(base + "/");
  const persistentBar = page.getByTestId("persistent-capture-bar");
  await persistentBar.waitFor();
  assert.equal(
    await page.getByRole("dialog").count(),
    0,
    "Creation dialog must not reopen when navigating back to dashboard",
  );
  for (const view of [
    { name: "desktop", width: 1440, height: 1000 },
    { name: "mobile", width: 390, height: 844 },
  ]) {
    await page.setViewportSize({ width: view.width, height: view.height });
    for (const theme of ["light", "dark"]) {
      await page
        .getByRole("combobox", { name: "Thème", exact: true })
        .selectOption(theme);
      await page.waitForFunction(
        (value) => document.documentElement.dataset.theme === value,
        theme,
      );
      await persistentBar.screenshot({
        path: artifactPath(
          "logs",
          `persistent-capture-${view.name}-${theme}.png`,
        ),
      });
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
        false,
      );
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page
    .getByRole("combobox", { name: "Thème", exact: true })
    .selectOption("light");
  await page.locator("button.account-trigger").click();
  await page.getByRole("menuitem", { name: /Modifier mon profil/ }).click();
  await page.waitForURL(base + "/profil");
  await persistentBar.waitFor();
  await page.locator('a[href="/"]').first().click();
  await page.waitForURL(base + "/");
  await page
    .locator(`a[href="${new URL(originalMeetingUrl).pathname}"]`)
    .first()
    .click();
  await page.waitForURL(originalMeetingUrl);
  await persistentBar.waitFor();
  await persistentBar
    .getByRole("button", { name: "Pause", exact: true })
    .click();
  await persistentBar
    .getByRole("button", { name: "Reprendre", exact: true })
    .waitFor();
  await sleep(500);
  assert.deepEqual(await page.evaluate(() => window.__captureProof), {
    requests: 1,
    stopped: 0,
  });
  await persistentBar
    .getByRole("button", { name: "Reprendre", exact: true })
    .click();
  await persistentBar
    .getByRole("link", { name: "Retour à la réunion", exact: true })
    .click();
  await page.waitForURL(captureUrl);
  await recordingSignal.waitFor();
  await page.waitForFunction(() =>
    document.body.innerText.includes("fragments confirmés"),
  );
  const navigationSaveDeadline = Date.now() + 30000;
  while (
    (await meetingData()).chunks.length <= chunksBeforeNavigation &&
    Date.now() < navigationSaveDeadline
  )
    await sleep(1000);
  assert.ok(
    (await meetingData()).chunks.length > chunksBeforeNavigation,
    "Real saved chunks must progress through navigation",
  );
  assert.ok(
    (await meetingData()).chunks.reduce(
      (total, chunk) => total + chunk.bytes,
      0,
    ) > bytesBeforeNavigation,
  );
  assert.deepEqual(await page.evaluate(() => window.__captureProof), {
    requests: 1,
    stopped: 0,
  });
  pass(
    "Capture continue via dashboard/profil/autre réunion, barre pause/reprise/retour sans réouverture du micro",
  );
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  await recordingSignal
    .getByText("Enregistrement en pause", { exact: true })
    .waitFor();
  assert.equal(
    Number(
      await recordingSignal
        .getByRole("meter", { name: "Niveau audio capté", exact: true })
        .getAttribute("value"),
    ),
    0,
  );
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
  await page.getByRole("link", { name: "Mes réunions", exact: true }).click();
  await page.waitForURL(base + "/");
  await persistentBar
    .getByRole("button", { name: "Terminer et analyser", exact: true })
    .click();
  await persistentBar.waitFor({ state: "hidden", timeout: 30000 });
  assert.equal(await page.evaluate(() => window.__captureProof.requests), 1);
  assert.ok(await page.evaluate(() => window.__captureProof.stopped > 0));
  await page
    .locator(`a[href="${new URL(captureUrl).pathname}"]`)
    .first()
    .click();
  await page.waitForURL(captureUrl);
  await ready();
  pass(
    "Reprise fragments, finalisation depuis barre globale et rapport réel après capture",
  );
  if (
    process.env.MEMORA_TEST_ISOLATED === "1" &&
    ["parakeet-mlx", "mlx-whisper"].includes(
      process.env.MEMORA_FRENCH_ASR_ENGINE || "",
    )
  ) {
    await create("Recette française synthétique", "import", "fr");
    await page
      .locator("input[type=file]")
      .setInputFiles(resolve(root, "backend/test/fixtures/memora/french.wav"));
    await ready();
    await automaticSpeakers();
    await page
      .getByRole("button", { name: "Transcription", exact: true })
      .click();
    if (process.env.MEMORA_FRENCH_ASR_ENGINE === "parakeet-mlx") {
      const unknown = page
        .getByText("Langue non déterminée", { exact: true })
        .first();
      await unknown.waitFor();
      assert.match(
        await unknown.getAttribute("title"),
        /ne fournit pas de langue détectée/,
      );
    } else {
      const chosen = page
        .getByText("Langue choisie : français", { exact: true })
        .first();
      await chosen.waitFor();
      assert.match(
        await chosen.getAttribute("title"),
        /sans détection propre à ce passage/,
      );
    }
    await page.getByRole("button", { name: "Corriger", exact: true }).click();
    await page
      .getByRole("textbox", { name: "Intervenant 1", exact: true })
      .fill("Voix synthétique");
    await page
      .getByRole("button", { name: "Enregistrer les corrections", exact: true })
      .click();
    await page.getByText(/Le rapport est à actualiser/).waitFor();
    await page
      .locator("strong")
      .filter({ hasText: /^Voix synthétique$/ })
      .first()
      .waitFor();
    pass(
      "Import français réel, langue non inventée et correction persistée dans le navigateur",
    );
    const versionBeforeRename = (await meetingData()).version;
    await page.getByText("Gérer les intervenants", { exact: true }).click();
    await page
      .getByRole("combobox", { name: "Étiquette actuelle", exact: true })
      .selectOption("Voix synthétique");
    await page
      .getByRole("textbox", { name: "Nouveau nom", exact: true })
      .fill("Camille synthétique");
    await page
      .getByRole("button", { name: "Renommer tous ces passages", exact: true })
      .click();
    await page
      .locator("strong")
      .filter({ hasText: /^Camille synthétique$/ })
      .first()
      .waitFor();
    await page
      .getByRole("combobox", {
        name: "Version de la transcription",
        exact: true,
      })
      .selectOption("1");
    await page
      .getByText("Version historique en lecture seule.", { exact: false })
      .waitFor();
    await page
      .getByRole("combobox", {
        name: "Version de la transcription",
        exact: true,
      })
      .selectOption(String(versionBeforeRename + 1));
    assert.equal((await meetingData()).version, versionBeforeRename + 1);
    pass("Renommage global persisté et ancienne transcription consultable");
    const versionBeforeSeparation = (await meetingData()).version;
    await page.getByText("Gérer les intervenants", { exact: true }).click();
    await page
      .getByRole("spinbutton", {
        name: "Nombre d’intervenants connu (facultatif)",
        exact: true,
      })
      .fill("1");
    await page
      .getByRole("button", {
        name: "Séparer les intervenants localement",
        exact: true,
      })
      .click();
    await page
      .getByRole("dialog", { name: "Séparer les intervenants", exact: true })
      .getByRole("button", { name: "Lancer la séparation", exact: true })
      .click();
    await page.waitForFunction(
      (expectedVersion) =>
        document.querySelector("select") &&
        Array.from(document.querySelectorAll("select")).some(
          (select) => select.value === String(expectedVersion),
        ),
      versionBeforeSeparation + 1,
      { timeout: 120000 },
    );
    await page
      .getByText("Intervenants estimés localement ; aucune identité déduite.", {
        exact: false,
      })
      .waitFor();
    pass(
      "Séparation locale réelle déclenchée dans le navigateur, nouvelle version et avertissements visibles",
    );

    await page.screenshot({
      path: artifactPath("logs", "browser-french-transcript.png"),
      fullPage: true,
    });
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
