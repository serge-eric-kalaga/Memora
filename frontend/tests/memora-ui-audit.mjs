/** Focused local UI audit; synthetic account only, no settings mutation. */
import { chromium } from "@playwright/test";
import assert from "node:assert/strict";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
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
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
});
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
});
const page = await context.newPage();
const results = [];
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
const pass = (text) => {
  results.push(text);
  console.log("PASS", text);
};
try {
  await page.goto(base + "/connexion");
  await page.locator("input[name=username]").fill(account.username);
  await page.locator("input[name=password]").fill(account.password);
  await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await page.waitForURL(base + "/");
  await page
    .getByRole("heading", { name: "Mes réunions", exact: true })
    .waitFor();
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
    false,
  );
  await page
    .getByText("Chargement des réunions…", { exact: true })
    .waitFor({ state: "hidden" });
  await page.screenshot({
    path: artifactPath("logs", "audit-dashboard-desktop.png"),
    fullPage: true,
  });
  pass("Dashboard desktop sans débordement");
  const create = page.getByRole("button", {
    name: "Nouvelle réunion",
    exact: true,
  });
  await create.click();
  const dialog = page.getByRole("dialog");
  await dialog.waitFor();
  const language = dialog.getByRole("combobox", {
    name: "Langue de l’audio",
    exact: true,
  });
  assert.equal(await language.inputValue(), "fr");
  assert.ok(await language.getAttribute("aria-describedby"));
  assert.equal(
    await page.evaluate(
      () => document.activeElement.closest('[role="dialog"]') !== null,
    ),
    true,
  );
  await dialog
    .getByRole("button", { name: "Importer un audio", exact: true })
    .focus();
  await page.keyboard.press("Tab");
  assert.equal(
    await page.evaluate(() =>
      document.activeElement.getAttribute("aria-label"),
    ),
    "Fermer",
  );
  await page.keyboard.press("Shift+Tab");
  assert.equal(
    await page.evaluate(() => document.activeElement.textContent.trim()),
    "Importer un audio",
  );
  await page.keyboard.press("Escape");
  await dialog.waitFor({ state: "hidden" });
  assert.equal(
    await create.evaluate((el) => el === document.activeElement),
    true,
  );
  pass(
    "Dialogue clavier : focus initial, boucle Tab/Shift+Tab, Escape et restauration",
  );
  await page
    .getByRole("combobox", { name: "Langue", exact: true })
    .selectOption("en");
  await page
    .getByRole("heading", { name: "My meetings", exact: true })
    .waitFor();
  await page.getByRole("button", { name: "New meeting", exact: true }).click();
  assert.equal(
    await page
      .getByRole("dialog")
      .getByRole("combobox", { name: "Audio language", exact: true })
      .inputValue(),
    "en",
  );
  await page.keyboard.press("Escape");
  pass(
    "Anglais interface et défaut audio anglais après changement de préférence",
  );
  await page
    .getByRole("combobox", { name: "Theme", exact: true })
    .selectOption("dark");
  await page.waitForFunction(
    () => document.documentElement.getAttribute("data-theme") === "dark",
  );
  await page.screenshot({
    path: artifactPath("logs", "audit-dashboard-dark.png"),
    fullPage: true,
  });
  pass("Thème sombre appliqué");
  await page
    .getByRole("combobox", { name: "Language", exact: true })
    .selectOption("fr");
  await page
    .getByRole("combobox", { name: "Thème", exact: true })
    .selectOption("light");
  const beforeResponse = await page.request.get(base + "/mapi/settings");
  assert.ok(beforeResponse.ok());
  let before = await beforeResponse.json();
  before = before.data || before;
  await page.goto(base + "/parametres");
  await page
    .getByRole("heading", { name: "Paramètres de l’application", exact: true })
    .waitFor();
  await page
    .getByLabel("Durée maximale d’une réunion (minutes)", { exact: true })
    .waitFor();
  const inputs = [
    ["Durée maximale d’une réunion (minutes)", "241"],
    ["Taille maximale d’import (Mo)", "501"],
    ["Conservation des fichiers audio (jours)", "366"],
  ];
  for (const [name, value] of inputs) {
    const input = page.getByLabel(name, { exact: true });
    const previous = await input.inputValue();
    await input.fill(value);
    assert.equal(await input.evaluate((el) => el.validity.rangeOverflow), true);
    assert.equal(await input.evaluate((el) => el.checkValidity()), false);
    await input.fill("0");
    assert.equal(
      await input.evaluate((el) => el.validity.rangeUnderflow),
      true,
    );
    await input.fill(previous);
  }
  const afterResponse = await page.request.get(base + "/mapi/settings");
  let after = await afterResponse.json();
  after = after.data || after;
  assert.deepEqual(after, before);
  pass(
    `Bornes administratives invalides détectées sans requête PUT ; can_administer=${before.can_administer}`,
  );
  await page.screenshot({
    path: artifactPath("logs", "audit-settings-desktop.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  const headerBounds = await page.locator("header.site-header").boundingBox();
  const accountBounds = await page.locator(".nav-actions").boundingBox();
  assert.ok(
    accountBounds.y + accountBounds.height <=
      headerBounds.y + headerBounds.height + 1,
    "Le menu compte doit rester dans l’entête mobile.",
  );
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
    false,
  );
  await page.screenshot({
    path: artifactPath("logs", "audit-settings-mobile.png"),
    fullPage: true,
  });
  await page.goto(base + "/");
  await page
    .getByRole("heading", { name: "Mes réunions", exact: true })
    .waitFor();
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
    false,
  );
  await page
    .getByText("Chargement des réunions…", { exact: true })
    .waitFor({ state: "hidden" });
  await page.screenshot({
    path: artifactPath("logs", "audit-dashboard-mobile.png"),
    fullPage: true,
  });
  pass("Dashboard et paramètres mobile sans débordement");
  if (process.env.MEMORA_TEST_ISOLATED === "1") {
    const response = await page.request.get(base + "/mapi/meetings");
    let meetings = await response.json();
    meetings = meetings.data || meetings;
    let meeting = meetings.find(
      (value) => value.title === "Recette UI complète synthétique",
    );
    if (!meeting) {
      const created = await page.request.post(base + "/mapi/meetings", {
        headers: { Origin: base },
        data: {
          title: "Audit rapport mobile synthétique",
          mode: "import",
          transcription_language: "fr",
        },
      });
      assert.equal(created.status(), 201);
      let seeded = await created.json();
      seeded = seeded.data || seeded;
      const uploaded = await page.request.post(
        base + `/mapi/meetings/${seeded.id}/chunks?seq=0`,
        {
          headers: { Origin: base, "Content-Type": "application/octet-stream" },
          data: await readFile(
            resolve(root, "backend/test/fixtures/memora/french.wav"),
          ),
        },
      );
      assert.ok(uploaded.ok());
      assert.ok(
        (
          await page.request.post(
            base + `/mapi/meetings/${seeded.id}/finalize`,
            { headers: { Origin: base }, data: { expected_chunks: 1 } },
          )
        ).ok(),
      );
      const deadline = Date.now() + 180000;
      while (Date.now() < deadline) {
        const stateResponse = await page.request.get(
          base + `/mapi/meetings/${seeded.id}`,
        );
        let state = await stateResponse.json();
        state = state.data || state;
        if (state.state === "failed")
          throw new Error("Synthetic audit import failed");
        if (state.state === "ready") {
          meeting = state;
          break;
        }
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
    }
    assert.ok(meeting, "Réunion synthétique dédiée présente pour audit mobile");
    // Display-state regression only: no backend data or real job is changed.
    const detailRoute = base + "/mapi/meetings/" + meeting.id;
    await page.route(detailRoute, async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      const value = body.data || body;
      value.state = "analyzing";
      value.version = Math.max(2, value.version);
      value.report_version = value.version - 1;
      await route.fulfill({ response, json: body });
    });
    await page.goto(base + "/reunions/" + meeting.id);
    await page
      .getByRole("status")
      .filter({ hasText: "Une notification vous avertira" })
      .waitFor();
    assert.equal(
      await page
        .getByText("La transcription a été corrigée.", { exact: false })
        .count(),
      0,
    );
    await page.screenshot({
      path: artifactPath("logs", "audit-single-analysis-status.png"),
      fullPage: true,
    });
    await page.unroute(detailRoute);
    pass("Analyse en cours : un seul bandeau, rappel de rapport périmé masqué");
    await page.goto(base + "/reunions/" + meeting.id);
    await page.getByRole("heading", { name: "Résumé", exact: true }).waitFor();
    const actionSection = page
      .locator("section")
      .filter({
        has: page.getByRole("heading", {
          name: "Actions à suivre",
          exact: true,
        }),
      })
      .last();
    const firstAction = actionSection
      .locator('li[class*="reportItem"]')
      .first();
    await firstAction.waitFor();
    const firstReview = firstAction
      .locator('[data-testid^="human-review-actions-"]')
      .first();
    await firstReview
      .getByRole("button", { name: "Valider cet élément", exact: true })
      .click();
    await firstReview
      .getByLabel("Statut", { exact: true })
      .selectOption("confirmed");
    await firstReview
      .getByRole("button", {
        name: "Enregistrer la validation humaine",
        exact: true,
      })
      .click();
    await firstReview.locator('[data-status="confirmed"]').waitFor();
    await firstReview
      .getByRole("button", { name: "Historique des validations", exact: true })
      .click();
    await firstReview.locator("ol li").first().waitFor();
    assert.match(await firstReview.locator("ol").innerText(), /Confirmé/);
    pass(
      "Carte action : validation réelle confirmée, métadonnées et historique accessibles",
    );
    for (const viewport of [
      { name: "desktop", width: 1440, height: 1000 },
      { name: "mobile", width: 390, height: 844 },
    ]) {
      await page.setViewportSize({
        width: viewport.width,
        height: viewport.height,
      });
      for (const theme of ["light", "dark"]) {
        await page
          .getByRole("combobox", { name: "Thème", exact: true })
          .selectOption(theme);
        await page.waitForFunction(
          (value) =>
            document.documentElement.getAttribute("data-theme") === value,
          theme,
        );
        assert.ok(
          await firstAction
            .locator("dl dt")
            .filter({ hasText: "Responsable" })
            .count(),
        );
        assert.ok(
          await firstAction
            .locator("dl dt")
            .filter({ hasText: "Échéance" })
            .count(),
        );
        const style = await firstAction.evaluate((el) => ({
          padding: parseFloat(getComputedStyle(el).paddingTop),
          radius: parseFloat(getComputedStyle(el).borderRadius),
        }));
        assert.ok(style.padding >= 12 && style.radius >= 10);
        assert.equal(
          await page.evaluate(
            () => document.documentElement.scrollWidth > innerWidth,
          ),
          false,
        );
        await actionSection.screenshot({
          path: artifactPath(
            "logs",
            `report-design-actions-${viewport.name}-${theme}.png`,
          ),
        });
        await firstReview
          .getByRole("button", { name: "Valider cet élément", exact: true })
          .click();
        await firstReview
          .getByRole("textbox", { name: "Texte après relecture", exact: true })
          .waitFor();
        await firstReview.getByLabel("Responsable", { exact: true }).waitFor();
        await firstReview
          .getByLabel("Échéance, telle qu’établie", { exact: true })
          .waitFor();
        assert.equal(
          await page.evaluate(
            () => document.documentElement.scrollWidth > innerWidth,
          ),
          false,
        );
        await firstAction.screenshot({
          path: artifactPath(
            "logs",
            `report-design-review-${viewport.name}-${theme}.png`,
          ),
        });
        await firstReview
          .getByRole("button", { name: "Fermer la validation", exact: true })
          .click();
      }
    }
    pass(
      "Cartes actions et formulaire : desktop/mobile clair/sombre sans débordement",
    );
    await page.setViewportSize({ width: 390, height: 844 });
    await page
      .getByRole("combobox", { name: "Thème", exact: true })
      .selectOption("light");
    await page
      .getByRole("button", { name: "Valider cet élément", exact: true })
      .first()
      .click();
    await page.getByLabel("Statut", { exact: true }).first().waitFor();
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
    );
    await page.screenshot({
      path: artifactPath("logs", "audit-human-review-mobile.png"),
      fullPage: true,
    });
    await page.getByRole("button", { name: "Chat IA", exact: true }).click();
    const primaryChat = page.locator("#meeting-chat-panel");
    await primaryChat
      .getByRole("heading", { name: "Memora IA", exact: true })
      .waitFor();
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
        assert.equal(
          await page
            .getByRole("heading", { name: "Résumé", exact: true })
            .count(),
          0,
        );
        assert.ok(
          await primaryChat
            .getByRole("textbox", { name: "Votre question", exact: true })
            .isVisible(),
        );
        assert.equal(
          await page.evaluate(
            () => document.documentElement.scrollWidth > innerWidth,
          ),
          false,
        );
        await primaryChat.screenshot({
          path: artifactPath("logs", `chat-primary-${view.name}-${theme}.png`),
        });
      }
    }
    pass(
      "Chat principal accessible desktop/mobile clair/sombre, composer visible sans rapport concurrent",
    );
    // Long-answer display fixture only; stored meeting/chat remain unchanged.
    await page.route(detailRoute, async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      const value = body.data || body;
      value.chat = [
        {
          version: value.version,
          question: "Quels sont les points essentiels ?",
          answer:
            "## Points essentiels\n\n" +
            Array.from(
              { length: 12 },
              (_, i) =>
                `Point ${i + 1} : vérifier les accès et préparer la démonstration (u3, u7).`,
            ).join("\n\n"),
          sources: (value.segments || []).map((segment) => segment.id),
        },
      ];
      await route.fulfill({ response, json: body });
    });
    await page.goto(base + "/reunions/" + meeting.id);
    await page.getByRole("button", { name: "Chat IA", exact: true }).click();
    await page
      .getByRole("heading", { name: "Points essentiels", exact: true })
      .waitFor();
    for (const view of [
      { name: "desktop", width: 1440, height: 1000 },
      { name: "mobile", width: 390, height: 844 },
    ]) {
      await page.setViewportSize({ width: view.width, height: view.height });
      for (const theme of ["light", "dark"]) {
        await page
          .getByRole("combobox", { name: "Thème", exact: true })
          .selectOption(theme);
        await primaryChat
          .getByText("Quels sont les points essentiels ?", { exact: false })
          .scrollIntoViewIfNeeded();
        assert.equal(await primaryChat.getByText(/\(u3, u7\)/).count(), 0);
        assert.equal(await primaryChat.locator("details[open]").count(), 0);
        assert.ok(await primaryChat.getByRole("textbox").isVisible());
        assert.doesNotMatch(
          await primaryChat
            .getByRole("textbox")
            .evaluate((el) => getComputedStyle(el).fontFamily),
          /monospace/i,
        );
        await primaryChat.screenshot({
          path: artifactPath("logs", `chat-long-${view.name}-${theme}.png`),
        });
      }
    }
    await page.unroute(detailRoute);
    pass(
      "Réponse longue : références internes masquées, sources repliées et police lisible dans quatre vues",
    );
    await page
      .getByRole("button", { name: "Transcription", exact: true })
      .click();
    await page.getByText("Gérer les intervenants", { exact: true }).click();
    await page
      .getByRole("textbox", { name: "Nouveau nom", exact: true })
      .waitFor();
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
    );
    await page.screenshot({
      path: artifactPath("logs", "audit-transcript-tools-mobile.png"),
      fullPage: true,
    });
    pass(
      "Formulaires de validation, lecteur de transcription et intervenants mobile sans débordement",
    );
    await page.route(detailRoute, async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      const value = body.data || body;
      value.automatic_diarization = {
        state: "failed",
        source_version: value.version,
      };
      await route.fulfill({ response, json: body });
    });
    await page.goto(base + "/reunions/" + meeting.id);
    await page
      .getByRole("button", { name: "Transcription", exact: true })
      .click();
    await page
      .getByText(
        "Les intervenants n’ont pas pu être distingués automatiquement",
        { exact: true },
      )
      .waitFor();
    await page
      .getByRole("button", { name: "Distinguer les intervenants", exact: true })
      .click();
    const knownCount = page.getByRole("spinbutton", {
      name: "Nombre d’intervenants connu (facultatif)",
      exact: true,
    });
    await knownCount.fill("2");
    assert.equal(await knownCount.inputValue(), "2");
    assert.ok(await knownCount.evaluate((el) => el === document.activeElement));
    assert.ok(
      await page
        .getByRole("button", {
          name: "Séparer les intervenants localement",
          exact: true,
        })
        .isEnabled(),
    );
    await page.screenshot({
      path: artifactPath("logs", "speaker-failure-recovery-mobile.png"),
      fullPage: true,
    });
    const analysisCount = page.getByRole("spinbutton", {
      name: "Nombre d’intervenants pour l’analyse (facultatif)",
      exact: true,
    });
    const retryAnalysis = page.getByRole("button", {
      name: "Relancer l’analyse",
      exact: true,
    });
    await analysisCount.fill("9");
    assert.ok(await retryAnalysis.isDisabled());
    await analysisCount.fill("2");
    let retryBody;
    await page.route(detailRoute + "/analyze", async (route) => {
      retryBody = route.request().postDataJSON();
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Synthetic retry received" }),
      });
    });
    await retryAnalysis.click();
    await page
      .getByRole("alert")
      .filter({ hasText: "Synthetic retry received" })
      .waitFor();
    assert.equal(retryBody.num_speakers, 2);
    await page.unroute(detailRoute + "/analyze");
    await page.unroute(detailRoute);
    pass(
      "Échec de séparation explicite et relance accessible avec nombre connu, sans renommer toutes les voix",
    );
    let nativeDialogs = 0;
    const unexpectedDialog = async (dialog) => {
      nativeDialogs++;
      await dialog.dismiss();
    };
    page.on("dialog", unexpectedDialog);
    for (const item of [
      {
        trigger: "Retranscrire l’audio",
        title: "Retranscrire l’audio",
        accept: "Retranscrire l’audio",
        path: "/retranscribe",
        method: "POST",
      },
      {
        trigger: "Séparer les intervenants localement",
        title: "Séparer les intervenants",
        accept: "Lancer la séparation",
        path: "/diarize",
        method: "POST",
      },
      {
        trigger: "Supprimer définitivement",
        title: "Supprimer définitivement",
        accept: "Supprimer définitivement",
        path: "",
        method: "DELETE",
      },
    ]) {
      let calls = 0;
      const endpoint = detailRoute + item.path;
      await page.route(endpoint, async (route) => {
        if (route.request().method() !== item.method) return route.continue();
        calls++;
        await route.fulfill({
          status: 409,
          contentType: "application/json",
          body: JSON.stringify({
            detail: "Synthetic confirmation request rejected",
          }),
        });
      });
      const trigger = page.getByRole("button", {
        name: item.trigger,
        exact: true,
      });
      await trigger.click();
      const dialog = page.getByRole("dialog", {
        name: item.title,
        exact: true,
      });
      await dialog.waitFor();
      const cancel = dialog.getByRole("button", {
        name: "Annuler",
        exact: true,
      });
      assert.ok(await cancel.evaluate((el) => el === document.activeElement));
      for (let step = 0; step < 5; step++) {
        await page.keyboard.press("Tab");
        assert.ok(
          await dialog.evaluate((el) => el.contains(document.activeElement)),
        );
      }
      await page.keyboard.press("Escape");
      await dialog.waitFor({ state: "hidden" });
      assert.equal(calls, 0);
      assert.ok(await trigger.evaluate((el) => el === document.activeElement));
      await trigger.click();
      await dialog
        .getByRole("button", { name: "Annuler", exact: true })
        .click();
      assert.equal(calls, 0);
      if (item.path === "/retranscribe") {
        for (const view of [
          { name: "desktop", width: 1440, height: 1000 },
          { name: "mobile", width: 390, height: 844 },
        ]) {
          await page.setViewportSize({
            width: view.width,
            height: view.height,
          });
          for (const theme of ["light", "dark"]) {
            await page
              .getByRole("combobox", { name: "Thème", exact: true })
              .selectOption(theme);
            await trigger.click();
            await dialog.screenshot({
              path: artifactPath(
                "logs",
                `confirmation-${view.name}-${theme}.png`,
              ),
            });
            await cancel.click();
          }
        }
      }
      await trigger.click();
      await dialog
        .getByRole("button", { name: item.accept, exact: true })
        .click();
      await page
        .getByRole("alert")
        .filter({ hasText: "Synthetic confirmation request rejected" })
        .waitFor();
      assert.equal(calls, 1);
      await page.unroute(endpoint);
    }
    page.off("dialog", unexpectedDialog);
    assert.equal(nativeDialogs, 0);
    pass(
      "Trois confirmations intégrées : Annuler/Échap sans requête, focus restauré, une seule requête confirmée, zéro fenêtre JavaScript native",
    );
    const created = await page.request.post(base + "/mapi/meetings", {
      headers: { Origin: base },
      data: {
        title: "Audit microphone mobile synthétique",
        mode: "recording",
        transcription_language: "fr",
      },
    });
    assert.equal(created.status(), 201);
    let draft = await created.json();
    draft = draft.data || draft;
    try {
      await page.goto(base + "/reunions/" + draft.id);
      await page
        .getByRole("button", { name: "Tester le microphone", exact: true })
        .waitFor();
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
        false,
      );
      await page
        .getByText(
          "Prêt à commencer ? Prévenez les participants, puis lancez l’enregistrement.",
          { exact: true },
        )
        .waitFor();
      const tips = page.locator("details").filter({
        has: page.getByText("Conseils pour enregistrer", { exact: true }),
      });
      assert.equal(await tips.getAttribute("open"), null);
      await page
        .getByText("Conseils pour enregistrer", { exact: true })
        .click();
      await tips.getByText(/Durée maximale d’enregistrement/).waitFor();
      assert.match(await tips.innerText(), /120 min/);
      await page
        .getByText("Conseils pour enregistrer", { exact: true })
        .click();
      assert.equal(await tips.getAttribute("open"), null);
      pass(
        "Message utilisateur clair et conseils repliés accessibles sans ouvrir le microphone",
      );
      await page.screenshot({
        path: artifactPath("logs", "audit-microphone-mobile.png"),
        fullPage: true,
      });
      pass(
        "Contrôle microphone mobile visible sans activation automatique ni débordement",
      );
    } finally {
      await page.request.delete(base + "/mapi/meetings/" + draft.id, {
        headers: { Origin: base },
      });
    }
  }
  assert.deepEqual(errors, []);
  pass("Aucune exception JavaScript non gérée");
  await mkdir(resolve(root, "agents/handoffs"), { recursive: true });
  await writeFile(
    artifactPath("handoffs", "ui-audit.md"),
    "# Audit UI ciblé\n\n" +
      new Date().toISOString() +
      "\n\n" +
      results.map((x) => "- VALIDÉ : " + x).join("\n") +
      "\n\nDonnées synthétiques uniquement. Aucun paramètre sauvegardé. Une fixture audio synthétique peut être importée uniquement sur instance isolée pour l’audit autonome. Captures dans agents/logs (locales, ignorées).\n",
  );
} catch (e) {
  console.error(
    String(e.stack || e).replaceAll(account.password, "[redacted]"),
  );
  await page
    .screenshot({
      path: artifactPath("logs", "audit-ui-failure.png"),
      fullPage: true,
      mask: [page.locator("input[type=password]")],
    })
    .catch(() => {});
  process.exitCode = 1;
} finally {
  await browser.close();
}
