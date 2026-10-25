/** Real Next proxy + synthetic delayed HTTP backend, both on ephemeral loopback ports. */
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { spawn } from "node:child_process";
import { mkdtemp, cp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const folder = await mkdtemp(join(tmpdir(), "memora-proxy-deadline-"));
const backend = createServer(async (req, res) => {
  let text = "";
  for await (const chunk of req) text += chunk;
  const slow =
    req.url.endsWith("/chat") && JSON.parse(text || "{}").question === "slow";
  const delay = slow ? 1600 : req.url.endsWith("/settings") ? 1150 : 0;
  setTimeout(() => {
    if (!res.destroyed) {
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ answer: "Synthetic response", sources: [] }));
    }
  }, delay);
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
      MEMORA_CHAT_TIMEOUT_MS: "1000",
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
      await fetch(base + "/mapi/settings", {
        signal: AbortSignal.timeout(2000),
      });
      break;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
  }
  const options = (question) => ({
    method: "POST",
    headers: { origin: base, "content-type": "application/json" },
    body: JSON.stringify({ question }),
  });
  const normal = await fetch(
    base + "/mapi/meetings/synthetic/chat",
    options("normal"),
  );
  assert.equal(normal.status, 200);
  assert.equal((await normal.json()).answer, "Synthetic response");
  console.log("PASS Chat returns complete normal backend response");
  const timedOut = await fetch(
    base + "/mapi/meetings/synthetic/chat",
    options("slow"),
  );
  assert.equal(timedOut.status, 504);
  const error = await timedOut.json();
  assert.match(error.message, /délai autorisé/);
  assert.match(error.message, /historique/);
  console.log(
    "PASS Configured 1000 ms chat deadline returns explicit 504 on delayed backend",
  );
  const rest = await fetch(base + "/mapi/settings");
  assert.equal(rest.status, 200);
  assert.equal((await rest.json()).answer, "Synthetic response");
  console.log(
    "PASS REST request lasting 1150 ms is unaffected by the 1000 ms chat setting",
  );
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
