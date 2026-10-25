/** Real Next SSE proxy and browser invalidation; disposable synthetic Docker stack only. */
import assert from "node:assert/strict";
import { chromium, request } from "@playwright/test";
import { readFile } from "node:fs/promises";

assert.equal(process.env.MEMORA_TEST_ISOLATED, "1", "Isolated services required");
const base = process.env.MEMORA_UI_URL;
assert.ok(base, "Explicit isolated UI URL required");
const url = new URL(base);
assert.ok(["127.0.0.1", "localhost"].includes(url.hostname));
assert.equal(url.port, "13000", "Only the disposable Docker recipe is permitted");
assert.ok(process.env.MEMORA_TEST_CREDENTIALS, "Explicit synthetic credentials required");
const account = JSON.parse(await readFile(process.env.MEMORA_TEST_CREDENTIALS, "utf8"));
assert.equal(account.username, "synthetic_docker_qa");
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
});
const context = await browser.newContext();
const page = await context.newPage();
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
const changes = [];
page.on("request", (req) => {
  if (req.method() === "GET" && new URL(req.url()).pathname.startsWith("/mapi/"))
    changes.push({ path: new URL(req.url()).pathname, at: Date.now() });
});
let external, guestContext;
const ids = [];
const pass = (text) => console.log("PASS", text);
async function json(response, status = 200) {
  assert.equal(response.status(), status);
  const value = await response.json();
  return value.data || value;
}
try {
  await page.goto(`${base}/connexion`);
  await page.locator("input[name=username]").fill(account.username);
  await page.locator("input[name=password]").fill(account.password);
  await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await page.waitForURL(`${base}/`);
  await page.getByRole("heading", { name: "Mes réunions", exact: true }).waitFor();
  await page.getByText("Chargement des réunions…", { exact: true }).waitFor({ state: "hidden" });
  external = await request.newContext({ storageState: await context.storageState(), extraHTTPHeaders: { Origin: base } });
  const make = async (title) => {
    const meeting = await json(await external.post(`${base}/mapi/meetings`, {
      data: { title, mode: "import", transcription_language: "fr" },
    }), 201);
    ids.push(meeting.id);
    return meeting;
  };
  const first = await make(`Synthétique temps réel ${Date.now()}`);
  await page.getByText(first.title, { exact: true }).first().waitFor();
  pass("Dashboard updated from a separate authenticated client without reload");

  // Read one actual frame through Next and cancel. response.body() would wait
  // indefinitely on an SSE response, so consume the first streamed chunk only.
  const frame = await page.evaluate(async () => {
    const controller = new AbortController();
    const deadline = setTimeout(() => controller.abort(), 5000);
    try {
      const response = await fetch("/mapi/events", { signal: controller.signal });
      const reader = response.body.getReader();
      const chunk = await reader.read();
      await reader.cancel();
      return { status: response.status, type: response.headers.get("content-type"), body: new TextDecoder().decode(chunk.value) };
    } finally {
      clearTimeout(deadline);
      controller.abort();
    }
  });
  assert.equal(frame.status, 200);
  assert.match(frame.type, /text\/event-stream/);
  assert.match(frame.body, /event: refresh\ndata: \{\}/);
  assert.ok(!frame.body.includes(first.title));
  pass("Next proxy streams an immediate SSE invalidation with no private payload");

  await page.waitForTimeout(1500);
  const idleStart = changes.length;
  await page.waitForTimeout(8200);
  assert.deepEqual(changes.slice(idleStart).filter((entry) => entry.path !== "/mapi/events"), []);
  pass("Healthy idle dashboard performs no periodic domain GET during 8 seconds");

  const renamed = `Synthétique actualisée ${Date.now()}`;
  const beforeUpdate = changes.length;
  await json(await external.patch(`${base}/mapi/meetings/${first.id}`, { data: { title: renamed } }));
  await page.getByText(renamed, { exact: true }).first().waitFor({ timeout: 10000 });
  assert.ok(changes.slice(beforeUpdate).some((entry) => entry.path === "/mapi/meetings"));
  pass("Committed change invalidates the browser and refreshes its visible data");

  const beforeReconnect = changes.filter((entry) => entry.path === "/mapi/events").length;
  await context.setOffline(true);
  await page.waitForTimeout(300);
  const missed = `Synthétique reconnexion ${Date.now()}`;
  await json(await external.patch(`${base}/mapi/meetings/${first.id}`, { data: { title: missed } }));
  await context.setOffline(false);
  await page.getByText(missed, { exact: true }).first().waitFor({ timeout: 15000 });
  assert.ok(changes.filter((entry) => entry.path === "/mapi/events").length > beforeReconnect);
  pass("Network reconnect opens a new stream and resynchronizes a missed change");

  const second = await make(`Synthétique confidentielle ${Date.now()}`);
  const share = await json(await external.post(`${base}/mapi/meetings/${first.id}/shares`, {
    data: { permissions: { report: true, transcript: false, audio: false, chat: false, edit: false } },
  }), 201);
  const token = share.id || share.token;
  guestContext = await browser.newContext();
  const guest = await guestContext.newPage();
  await guest.goto(`${base}/partage/${token}`);
  await guest.getByText(missed, { exact: true }).first().waitFor({ timeout: 10000 });
  const headers = { "X-Share-Token": token };
  const denied = await guest.request.get(`${base}/mapi/events?meeting=${second.id}`, { headers });
  assert.ok([401, 403, 404].includes(denied.status()));
  const ownerFeed = await guest.request.get(`${base}/mapi/events`, { headers });
  assert.ok([401, 403, 404].includes(ownerFeed.status()));
  assert.equal(await guest.getByText(second.title, { exact: true }).count(), 0);
  pass("Guest cannot subscribe to another meeting or to an owner feed");

  const guestTitle = `Synthétique invitée ${Date.now()}`;
  await json(await external.patch(`${base}/mapi/meetings/${first.id}`, { data: { title: guestTitle } }));
  await guest.getByText(guestTitle, { exact: true }).first().waitFor({ timeout: 10000 });
  assert.equal(await guest.getByRole("button", { name: "Chat IA", exact: true }).count(), 0);
  pass("Guest receives permitted updates while restricted content stays hidden");
  const revoked = await external.delete(`${base}/mapi/meetings/${first.id}/shares/${token}`);
  assert.ok(revoked.ok());
  await guest.getByText(guestTitle, { exact: true }).first().waitFor({ state: "hidden", timeout: 25000 });
  const revokedFeed = await guest.request.get(`${base}/mapi/events?meeting=${first.id}`, { headers });
  assert.ok([401, 403, 404].includes(revokedFeed.status()));
  pass("Revocation closes access and clears previously displayed guest content");
  assert.deepEqual(errors, []);
  console.log("SUCCESS 8 realtime browser checks; no browser exceptions");
} finally {
  await context.setOffline(false);
  if (external) {
    for (const id of ids) await external.delete(`${base}/mapi/meetings/${id}`).catch(() => {});
    await external.dispose();
  }
  await guestContext?.close();
  await browser.close();
}
