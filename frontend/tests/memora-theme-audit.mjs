/** Palette regression on real pages; no account creation or mutation. */
import assert from "node:assert/strict";
async function check(page, theme, label) {
  const result = await page.evaluate(() => {
    const root = getComputedStyle(document.documentElement);
    const accent = root.getPropertyValue("--green").trim();
    const scopes = [
      ...document.querySelectorAll(
        'main,[class*="account_root"],[class*="administration_root"]',
      ),
    ].filter((el) => el.getClientRects().length);
    const buttons = [
      ...document.querySelectorAll('button[class*="primary"],a.button-primary'),
    ].filter((el) => el.getClientRects().length && !el.disabled);
    const luminance = (value) => {
      let channels;
      if (value.startsWith("#"))
        channels = [1, 3, 5].map(
          (i) => parseInt(value.slice(i, i + 2), 16) / 255,
        );
      else
        channels = (value.match(/[\d.]+/g) || [])
          .slice(0, 3)
          .map(Number)
          .map((x) => x / 255);
      if (channels.length !== 3) throw Error("Unsupported color " + value);
      return channels
        .map((x) => (x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4))
        .reduce((sum, x, i) => sum + x * [0.2126, 0.7152, 0.0722][i], 0);
    };
    const contrast = (a, b) => {
      const x = luminance(a),
        y = luminance(b);
      return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
    };
    const color = document.createElement("span");
    color.style.color = "var(--green)";
    document.body.append(color);
    const resolved = getComputedStyle(color).color;
    color.remove();
    return {
      accent,
      scopes: scopes.map((el) =>
        getComputedStyle(el).getPropertyValue("--green").trim(),
      ),
      buttons: buttons.map((el) => {
        const s = getComputedStyle(el);
        return {
          background: s.backgroundColor,
          filter: !!el.closest('[class*="toolbar"]'),
          contrast: contrast(s.color, s.backgroundColor),
        };
      }),
      resolved,
      textContrast: contrast(
        root.getPropertyValue("--ink").trim(),
        root.getPropertyValue("--background").trim(),
      ),
      mutedContrast: contrast(
        root.getPropertyValue("--muted").trim(),
        root.getPropertyValue("--soft").trim(),
      ),
      overflow: document.documentElement.scrollWidth > innerWidth,
    };
  });
  assert.equal(result.accent, theme === "dark" ? "#a495ff" : "#6550df", label);
  assert.ok(
    result.scopes.every((accent) => accent === result.accent),
    label + " local palette diverges",
  );
  for (const button of result.buttons) {
    if (!button.filter)
      assert.equal(
        button.background,
        result.resolved,
        label + " primary accent",
      );
    assert.ok(
      button.contrast >= 4.5,
      label + " primary contrast " + button.contrast,
    );
  }
  assert.ok(result.textContrast >= 7, label + " text contrast");
  assert.ok(result.mutedContrast >= 4.5, label + " muted contrast");
  assert.equal(result.overflow, false, label + " overflow");
}
async function views(page, routes, artifactPath) {
  for (const route of routes) {
    await page.goto(route.url);
    await page.locator("#page-content").waitFor();
    await page.locator("#page-content h1").first().waitFor();
    const preference = page.getByRole("combobox", {
      name: "Thème",
      exact: true,
    });
    await preference.waitFor();
    for (const view of [
      { name: "desktop", width: 1440, height: 1000 },
      { name: "mobile", width: 390, height: 844 },
    ]) {
      await page.setViewportSize({ width: view.width, height: view.height });
      for (const theme of ["light", "dark"]) {
        await preference.selectOption(theme);
        await page.waitForFunction(
          (value) => document.documentElement.dataset.theme === value,
          theme,
        );
        await page.mouse.move(0, 0);
        // React theme state precedes completion of finite CSS color transitions.
        await page
          .waitForFunction(
            () => {
              const probe = document.createElement("span");
              probe.style.color = "var(--green)";
              document.body.append(probe);
              const expected = getComputedStyle(probe).color;
              probe.remove();
              return [
                ...document.querySelectorAll(
                  'button[class*="primary"],a.button-primary',
                ),
              ]
                .filter(
                  (el) =>
                    el.getClientRects().length &&
                    !el.disabled &&
                    !el.closest('[class*="toolbar"]'),
                )
                .every(
                  (el) => getComputedStyle(el).backgroundColor === expected,
                );
            },
            undefined,
            { timeout: 3000 },
          )
          .catch(() => {});
        await check(page, theme, route.name + " " + view.name + " " + theme);
        await page.screenshot({
          path: artifactPath(
            "logs",
            `palette-${route.name}-${view.name}-${theme}.png`,
          ),
          fullPage: true,
        });
      }
    }
  }
}
export async function auditPublicPalette(browser, base, artifactPath) {
  const context = await browser.newContext();
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  try {
    await views(
      page,
      [
        "connexion",
        "inscription",
        "mot-de-passe-oublie",
        "confirmer-email",
        "reinitialiser-mot-de-passe",
        "documentation",
      ].map((path) => ({ name: path, url: base + "/" + path })),
      artifactPath,
    );
    assert.deepEqual(errors, []);
  } finally {
    await context.close();
  }
}
export async function auditAccountPalette(page, base, artifactPath) {
  await views(
    page,
    [
      { name: "dashboard", url: base + "/" },
      ...["profil", "administration", "parametres"].map((path) => ({
        name: path,
        url: base + "/" + path,
      })),
    ],
    artifactPath,
  );
  await page
    .getByRole("combobox", { name: "Thème", exact: true })
    .selectOption("light");
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(base + "/");
  await page
    .getByRole("heading", { name: "Mes réunions", exact: true })
    .waitFor();
}
