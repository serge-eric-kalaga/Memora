/** Real Next session proxy + synthetic HTTP backend, ephemeral loopback ports only. */
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";
import { createServer } from "node:http";
import { spawn } from "node:child_process";
import { mkdtemp, cp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const folder = await mkdtemp(join(tmpdir(), "memora-session-recovery-"));
const cases = {
  invalid: [403, "Token Invalide"],
  expired: [403, "Session expirée"],
  migrated: [403, "Session expirée ; reconnectez-vous"],
  forbidden: [403, "Permission insuffisante"],
  unavailable: [503, "Synthetic service unavailable"],
};
let backendCalls = 0;
const backend = createServer((req, res) => {
  assert.equal(req.url, "/api/user/me");
  const key = req.headers.authorization?.replace(/^Bearer /, "");
  const entry = cases[key];
  assert.ok(entry, "Only synthetic test tokens are accepted");
  backendCalls++;
  res.writeHead(entry[0], { "content-type": "application/json" });
  res.end(JSON.stringify({ message: entry[1] }));
});
await new Promise((resolve) => backend.listen(0, "127.0.0.1", resolve));
const reserve = createServer();
await new Promise((resolve) => reserve.listen(0, "127.0.0.1", resolve));
const frontendPort = reserve.address().port;
await new Promise((resolve) => reserve.close(resolve));
let frontend;
try {
  await cp(resolve(root, "frontend/.next/standalone"), folder, {
    recursive: true,
  });
  await cp(
    resolve(root, "frontend/.next/static"),
    join(folder, ".next/static"),
    { recursive: true },
  );
  const base = `http://127.0.0.1:${frontendPort}`;
  frontend = spawn(process.execPath, [join(folder, "server.js")], {
    cwd: folder,
    env: {
      ...process.env,
      HOSTNAME: "127.0.0.1",
      PORT: String(frontendPort),
      BACKEND_URL: `http://127.0.0.1:${backend.address().port}`,
      APP_ORIGIN: base,
      NEXT_PUBLIC_APP_NAME: "Memora",
    },
    stdio: ["ignore", "ignore", "pipe"],
  });
  let startupError = "";
  frontend.stderr.on("data", (data) => {
    startupError += data.toString();
  });
  for (let attempt = 0; attempt < 100; attempt++) {
    if (frontend.exitCode !== null)
      throw Error(`Isolated frontend failed: ${startupError}`);
    try {
      await fetch(base + "/api/session", {
        signal: AbortSignal.timeout(2000),
      });
      break;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
  }
  for (const key of ["invalid", "expired", "migrated"]) {
    const response = await fetch(base + "/api/session", {
      headers: { cookie: `template_session=${key}` },
    });
    assert.equal(response.status, 200, key);
    assert.deepEqual(await response.json(), { data: null });
    const cookie = response.headers.get("set-cookie");
    assert.match(cookie, /template_session=;/);
    assert.match(cookie, /Max-Age=0/i);
    console.log(
      `PASS ${key}: expired session becomes 200/null and clears cookie`,
    );
  }
  for (const [key, status] of [
    ["forbidden", 403],
    ["unavailable", 503],
  ]) {
    const response = await fetch(base + "/api/session", {
      headers: { cookie: `template_session=${key}` },
    });
    assert.equal(response.status, status);
    assert.equal(response.headers.get("set-cookie"), null);
    const body = await response.json();
    assert.ok(body.message);
    assert.equal("data" in body, false);
    console.log(
      `PASS ${key}: HTTP ${status} remains an error without logging out`,
    );
  }
  assert.equal(backendCalls, 5);
  console.log(
    "PASS All five authenticated requests reached the synthetic HTTP backend",
  );
  const browser = await chromium.launch({
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
    headless: true,
  });
  try {
    const context = await browser.newContext();
    await context.addCookies([
      { name: "template_session", value: "migrated", url: base },
    ]);
    const page = await context.newPage();
    await page.goto(base, { waitUntil: "networkidle" });
    await page
      .getByRole("link", { name: "Se connecter", exact: true })
      .first()
      .waitFor();
    assert.equal(
      await page
        .getByText(/service.*indisponible|impossible de vérifier/i)
        .count(),
      0,
    );
    assert.equal(
      (await context.cookies()).some(
        (cookie) => cookie.name === "template_session",
      ),
      false,
    );
    console.log(
      "PASS Chromium legacy session opens login affordance and clears cookie without unavailable error",
    );
  } finally {
    await browser.close();
  }
} finally {
  if (frontend) {
    frontend.kill("SIGTERM");
    await new Promise((resolve) => {
      if (frontend.exitCode !== null) resolve();
      else frontend.once("exit", resolve);
    });
  }
  backend.closeAllConnections();
  await new Promise((resolve) => backend.close(resolve));
  await rm(folder, { recursive: true, force: true });
}
