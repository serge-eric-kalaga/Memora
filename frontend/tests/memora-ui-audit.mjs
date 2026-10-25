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
