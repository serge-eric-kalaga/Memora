/** Downloads from real isolated API; fixtures and shared links stay on test storage. */
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

async function download(page, format, content, artifactPath) {
  const title =
    content === "report" ? "Exporter le rapport" : "Exporter la transcription";
  await page.getByRole("button", { name: title, exact: true }).click();
  const dialog = page.getByRole("dialog", { name: title, exact: true });
  await dialog
    .getByRole("radio", { name: new RegExp(`^${format.toUpperCase()}\\b`) })
    .check();
  const pending = page.waitForEvent("download");
  await dialog
    .getByRole("button", { name: "Télécharger", exact: true })
    .click();
  const file = await pending;
  assert.equal(await file.failure(), null);
  assert.ok(file.suggestedFilename().endsWith(`.${format}`));
  const bytes = await readFile(await file.path());
  assert.ok(bytes.length > 30);
  if (format === "pdf") assert.equal(bytes.subarray(0, 5).toString(), "%PDF-");
  if (format === "docx") assert.equal(bytes.subarray(0, 2).toString(), "PK");
  if (format === "srt")
    assert.match(bytes.toString(), /\d{2}:\d{2}:\d{2},\d{3} -->/);
  if (format === "vtt") assert.ok(bytes.toString().startsWith("WEBVTT"));
  await file.saveAs(artifactPath("logs", `export-${content}.${format}`));
  await dialog
    .getByRole("status")
    .filter({ hasText: "Téléchargement lancé" })
    .waitFor();
  await dialog.getByText("Fermer", { exact: true }).click();
  return bytes;
}

export async function auditExports(page, browser, base, meeting, artifactPath) {
  assert.equal(process.env.MEMORA_TEST_ISOLATED, "1");
  await page.goto(`${base}/reunions/${meeting.id}`);
  await page
    .getByRole("button", { name: "Exporter le rapport", exact: true })
    .waitFor();
  for (const format of ["pdf", "docx", "txt", "md"])
    await download(page, format, "report", artifactPath);
  await page
    .getByRole("button", { name: "Transcription", exact: true })
    .click();
  for (const format of ["pdf", "docx", "txt", "srt", "vtt"]) {
    const bytes = await download(page, format, "transcript", artifactPath);
    if (format === "txt")
      assert.ok(bytes.toString().includes(meeting.segments[0].text));
  }
  // Historical selection must be sent exactly as displayed, not silently replaced by latest.
  const historical = (meeting.transcript_versions || []).find(
    (v) => v.version !== meeting.version,
  );
  if (historical) {
    await page
      .getByLabel("Version de la transcription", { exact: true })
      .selectOption(String(historical.version));
    await page
      .getByText("Chargement de la transcription historique…", { exact: true })
      .waitFor({ state: "hidden" });
    const response = page.waitForResponse(
      (r) =>
        r.url().includes(`/meetings/${meeting.id}/export?`) &&
        new URL(r.url()).searchParams.get("version") ===
          String(historical.version),
    );
    const bytes = await download(page, "txt", "transcript", artifactPath);
    assert.equal((await response).status(), 200);
    assert.ok(bytes.toString().includes("Version historique"));
  }
  // A refused export is shown in the modal and can be retried without a native alert.
  await page.route(`**/meetings/${meeting.id}/export?**`, (route) =>
    route.fulfill({
      status: 409,
      json: { detail: "La réunion a changé pendant l’export. Relancez-le." },
    }),
  );
  await page
    .getByRole("button", { name: "Exporter la transcription", exact: true })
    .click();
  let dialog = page.getByRole("dialog", {
    name: "Exporter la transcription",
    exact: true,
  });
  await dialog
    .getByRole("button", { name: "Télécharger", exact: true })
    .click();
  await dialog
    .getByRole("alert")
    .filter({ hasText: "La réunion a changé" })
    .waitFor();
  await dialog.getByText("Fermer", { exact: true }).click();
  await page.unroute(`**/meetings/${meeting.id}/export?**`);
  for (const view of [
    { name: "desktop", width: 1440, height: 1000 },
    { name: "mobile", width: 390, height: 844 },
  ]) {
    await page.setViewportSize({ width: view.width, height: view.height });
    for (const theme of ["light", "dark"]) {
      await page
        .getByRole("combobox", { name: "Thème", exact: true })
        .selectOption(theme);
      await page
        .getByRole("button", { name: "Exporter la transcription", exact: true })
        .click();
      dialog = page.getByRole("dialog", {
        name: "Exporter la transcription",
        exact: true,
      });
      const box = await dialog.boundingBox();
      assert.ok(box.x >= 0 && box.x + box.width <= view.width + 1);
      assert.ok(box.y >= 0 && box.y + box.height <= view.height + 1);
      await dialog.screenshot({
        path: artifactPath("logs", `export-dialog-${view.name}-${theme}.png`),
      });
      await page.keyboard.press("Escape");
      assert.ok(
        await page
          .getByRole("button", {
            name: "Exporter la transcription",
            exact: true,
          })
          .evaluate((el) => el === document.activeElement),
      );
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page
    .getByRole("combobox", { name: "Thème", exact: true })
    .selectOption("light");
  const share = await page.request.post(
    `${base}/mapi/meetings/${meeting.id}/shares`,
    {
      headers: { Origin: base },
      data: {
        password: "SyntheticExport25!",
        permissions: {
          report: true,
          transcript: false,
          audio: false,
          chat: false,
          edit: false,
        },
      },
    },
  );
  assert.equal(share.status(), 201);
  const raw = await share.json();
  const data = raw.data || raw;
  const token = data.token || data.id;
  assert.ok(token);
  const guestContext = await browser.newContext();
  const guest = await guestContext.newPage();
  try {
    await guest.goto(`${base}/partage/${token}`);
    await guest.locator("input[type=password]").fill("SyntheticExport25!");
    await guest
      .getByRole("button", { name: "Accéder à la réunion", exact: true })
      .click();
    await guest
      .getByRole("button", { name: "Exporter le rapport", exact: true })
      .waitFor();
    assert.equal(
      await guest
        .getByRole("button", { name: "Exporter la transcription", exact: true })
        .count(),
      0,
    );
    await download(guest, "pdf", "report", artifactPath);
    const denied = await guest.request.get(
      `${base}/mapi/meetings/${meeting.id}/export?content=transcript&format=txt`,
      {
        headers: {
          "X-Share-Token": token,
          "X-Share-Password": "SyntheticExport25!",
        },
      },
    );
    assert.equal(denied.status(), 403);
    const revoked = await page.request.delete(
      `${base}/mapi/meetings/${meeting.id}/shares/${token}`,
      { headers: { Origin: base } },
    );
    assert.equal(revoked.status(), 200);
    const revokedExport = await guest.request.get(
      `${base}/mapi/meetings/${meeting.id}/export?content=report&format=pdf`,
      {
        headers: {
          "X-Share-Token": token,
          "X-Share-Password": "SyntheticExport25!",
        },
      },
    );
    assert.equal(revokedExport.status(), 404);
  } finally {
    await guestContext.close();
  }
  await page.goto(`${base}/reunions/${meeting.id}`);
}
