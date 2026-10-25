/** Isolated UI contract test; every API request is synthetic and intercepted. No microphone. */
import { chromium } from "@playwright/test";
import assert from "node:assert/strict";
const base = process.env.MEMORA_UI_URL || "http://127.0.0.1:3002";
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
});
const page = await browser.newPage();
const errors = [];
page.on("pageerror", (e) => {
  errors.push(e.message);
  console.error(
    "Synthetic UI error at",
    new URL(page.url()).pathname,
    e.stack || e.message,
  );
});
let finalized = 0,
  expected = 0,
  holdFirst = true,
  releaseFirst,
  edit = true,
  analyzed = 0,
  denied = false,
  deleteFails = true;
const gate = new Promise((resolve) => {
  releaseFirst = resolve;
});
const sequences = [];
const meeting = {
  id: "synthetic-import-recovery",
  title: "Import recovery synthetic",
  mode: "import",
  state: "draft",
  created: 1,
  version: 0,
  report_version: null,
  duration: 0,
  segments: [],
  reports: [],
  shares: [],
  chunks: [],
  settings: { max_duration_minutes: 120, max_upload_mb: 250 },
  permissions: {
    view: true,
    manage: true,
    edit: true,
    transcript: true,
    report: true,
    audio: false,
    chat: false,
  },
};
const guest = () => ({
  ...meeting,
  state: "ready",
  version: 1,
  report_version: 0,
  duration: 11,
  report_id: "report0",
  segments: [
    {
      id: "s0",
      start: 0,
      end: 1,
      text: "Synthetic source",
      speaker: "Unidentified",
    },
  ],
  reports: [
    {
      id: "report0",
      version: 0,
      revision: 1,
      created: 1,
      data: {
        summary: [],
        topics: [],
        decisions: [],
        actions: [],
        open_questions: [],
      },
    },
  ],
  permissions: {
    view: true,
    manage: false,
    edit,
    transcript: true,
    report: true,
    audio: false,
    chat: false,
  },
});
try {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const data = url.pathname.endsWith("/session")
      ? {
          username: "isolated_synthetic",
          telephone: null,
          email: null,
          email_verified_at: null,
          last_login_at: null,
          profile_photo_url: null,
        }
      : { is_superuser: false, permissions: [] };
    await route.fulfill({ json: { data } });
  });
  await page.route("**/mapi/**", async (route) => {
    const request = route.request(),
      url = new URL(request.url());
    if (request.method() === "DELETE") {
      await route.fulfill({
        status: deleteFails ? 503 : 200,
        json: deleteFails
          ? { detail: "Synthetic deletion unavailable" }
          : { deleted: true },
      });
      return;
    }
    if (
      url.pathname === "/mapi/meetings" ||
      url.pathname === "/mapi/notifications"
    ) {
      await route.fulfill({ json: [] });
      return;
    }
    if (
      denied &&
      (request.headers()["x-share-token"] || url.pathname.includes("/share/"))
    ) {
      await route.fulfill({
        status: 404,
        json: { detail: "Synthetic share revoked" },
      });
      return;
    }

    if (url.pathname.includes("/chunks")) {
      sequences.push(Number(url.searchParams.get("seq")));
      if (holdFirst) {
        holdFirst = false;
        await gate;
      }
      try {
        await route.fulfill({ json: { saved: true } });
      } catch {}
      return;
    }
    if (url.pathname.endsWith("/finalize")) {
      finalized++;
      expected = request.postDataJSON().expected_chunks;
      meeting.state = "queued";
      await route.fulfill({ json: { state: "queued" } });
      return;
    }
    if (url.pathname.endsWith("/analyze")) {
      analyzed++;
      await route.fulfill({ json: { state: "queued" } });
      return;
    }
    const isGuest =
      Boolean(request.headers()["x-share-token"]) ||
      url.pathname.includes("/share/");
    await route.fulfill({ json: isGuest ? guest() : meeting });
  });
  await page.goto(base + "/reunions/" + meeting.id);
  await page
    .getByRole("button", { name: "Choisir un fichier audio", exact: true })
    .waitFor();
  const input = page.locator("input[type=file]"),
    file = {
      name: "synthetic-resume.wav",
      mimeType: "audio/wav",
      buffer: Buffer.alloc(4 * 1024 * 1024 + 44),
    };
  const started = page.waitForRequest((r) => r.url().includes("/chunks"));
  await input.setInputFiles(file);
  await started;
  assert.equal(
    await page
      .getByRole("button", { name: "Supprimer définitivement", exact: true })
      .isDisabled(),
    true,
  );
  assert.equal(await input.inputValue(), "");
  await page
    .getByRole("button", { name: "Interrompre le transfert", exact: true })
    .click();
  await page
    .getByRole("alert")
    .filter({ hasText: /Transfert interrompu/ })
    .waitFor();
  assert.equal(finalized, 0);
  assert.equal(
    await page
      .getByRole("button", { name: "Terminer et analyser", exact: true })
      .count(),
    0,
  );
  assert.equal(
    await page
      .getByRole("button", {
        name: "Finaliser l’audio sauvegardé",
        exact: true,
      })
      .count(),
    0,
  );
  console.log(
    "PASS Interrupted import cannot finalize partial audio; file input is reusable",
  );
  releaseFirst();
  const finished = page.waitForRequest((r) => r.url().endsWith("/finalize"));
  await input.setInputFiles(file);
  await finished;
  await page
    .getByText(/En attente…|En attente/)
    .first()
    .waitFor();
  assert.equal(finalized, 1);
  assert.equal(expected, 3);
  assert.deepEqual(sequences, [0, 0, 1, 2]);
  console.log(
    "PASS Same-file resume completes all three chunks and finalizes once",
  );
  await page.goto(base + "/partage/guest-edit-synthetic");
  const regenerate = page.getByRole("button", {
    name: "Régénérer le rapport",
    exact: true,
  });
  await regenerate.waitFor();
  await regenerate.click();
  assert.equal(analyzed, 1);
  console.log("PASS Authorized guest editor can request report regeneration");
  edit = false;
  await page.reload();
  await page
    .getByRole("heading", { name: meeting.title, exact: true })
    .waitFor();
  assert.equal(
    await page
      .getByRole("button", { name: "Régénérer le rapport", exact: true })
      .count(),
    0,
  );
  denied = true;
  await page
    .getByRole("alert")
    .filter({ hasText: "Synthetic share revoked" })
    .waitFor({ timeout: 10000 });
  assert.equal(
    await page
      .getByRole("heading", { name: meeting.title, exact: true })
      .count(),
    0,
  );
  console.log(
    "PASS Revoked share removes the in-app meeting view without page reload",
  );
  await page.goto(base + "/reunions/" + meeting.id);
  const remove = page.getByRole("button", {
    name: "Supprimer définitivement",
    exact: true,
  });
  await remove.waitFor();
  page.once("dialog", (dialog) => dialog.accept());
  await remove.click();
  await page
    .getByRole("alert")
    .filter({ hasText: "Synthetic deletion unavailable" })
    .waitFor();
  assert.ok(page.url().endsWith("/reunions/" + meeting.id));
  console.log("PASS Failed deletion preserves the page and displays the error");
  await page.evaluate(
    (id) =>
      new Promise((resolve, reject) => {
        const open = indexedDB.open("memora-audio", 1);
        open.onsuccess = () => {
          const db = open.result,
            tx = db.transaction("chunks", "readwrite");
          tx.objectStore("chunks").put({
            key: id + ":99",
            meeting: id,
            seq: 99,
            blob: new Blob(["synthetic"]),
          });
          tx.oncomplete = () => {
            db.close();
            resolve();
          };
          tx.onerror = () => reject(tx.error);
        };
        open.onerror = () => reject(open.error);
      }),
    meeting.id,
  );
  deleteFails = false;
  page.once("dialog", (dialog) => dialog.accept());
  await remove.click();
  await page.waitForURL(base + "/");
  const localCount = await page.evaluate(
    () =>
      new Promise((resolve, reject) => {
        const open = indexedDB.open("memora-audio", 1);
        open.onsuccess = () => {
          const db = open.result,
            request = db.transaction("chunks").objectStore("chunks").getAll();
          request.onsuccess = () => {
            db.close();
            resolve(request.result.length);
          };
          request.onerror = () => reject(request.error);
        };
        open.onerror = () => reject(open.error);
      }),
  );
  assert.equal(localCount, 0);
  console.log(
    "PASS Successful server deletion clears pending local chunks before leaving",
  );
  assert.deepEqual(errors, []);
  console.log(
    "PASS Read-only guest has no regeneration control; no JavaScript exception",
  );
} finally {
  releaseFirst();
  await browser.close();
}
