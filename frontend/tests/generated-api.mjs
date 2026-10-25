/** Vérifier l’intégration du SDK dans le proxy et l’isolation des JWT entre requêtes concurrentes. */
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
const envFile = fileURLToPath(new URL("../../.env.dev", import.meta.url));
if (existsSync(envFile)) process.loadEnvFile(envFile);
const base = process.env.FRONTEND_TEST_URL || "http://localhost:3000";
const backend =
  process.env.BACKEND_TEST_URL ||
  process.env.BACKEND_URL ||
  "http://localhost:8080";
const origin = new URL(base).origin;
const accounts = [];
async function request(path, body, cookie = "") {
  return fetch(`${base}/api${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      ...(body === undefined
        ? {}
        : { Origin: origin, "Content-Type": "application/json" }),
      ...(cookie ? { Cookie: cookie } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}
try {
  const config = await request("/auth/config");
  assert.equal(config.status, 200);
  assert.equal(
    (await config.json()).data.email_verification_enabled,
    false,
    "Exécuter ces tests avec EMAIL_VERIFICATION_ENABLED=false",
  );
  for (let index = 0; index < 2; index++) {
    const account = {
      username: `sdk_${randomUUID().replaceAll("-", "").slice(0, 16)}`,
      password: `Generated-${randomUUID()}!`,
      cookie: "",
    };
    const response = await request("/auth/register", {
      ...account,
      telephone: "",
    });
    assert.equal(response.status, 200);
    accounts.push(account);
    account.cookie = response.headers.get("set-cookie").split(";")[0];
  }
  await Promise.all(
    Array.from({ length: 20 }, async (_, index) => {
      const account = accounts[index % 2];
      const response = await request("/session", undefined, account.cookie);
      assert.equal(response.status, 200);
      const user = (await response.json()).data;
      assert.equal(
        user.username,
        account.username,
        "Un JWT ne doit jamais être partagé entre les instances du SDK",
      );
      assert.equal(user.token, undefined);
      assert.equal(user.password, undefined);
    }),
  );
  const unknown = `unknown-${randomUUID()}@example.com`;
  assert.equal(
    (await request("/auth/resend-verification", { email: unknown })).status,
    202,
  );
  assert.equal(
    (await request("/auth/verify-email", { token: "x".repeat(43) })).status,
    400,
  );
  const invalid = await fetch(`${base}/api/profile/photo`, {
    method: "PUT",
    headers: {
      Origin: origin,
      Cookie: accounts[0].cookie,
      "Content-Type": "multipart/form-data; boundary=invalid",
    },
    body: "invalid multipart",
  });
  assert.equal(invalid.status, 400);
  console.log(
    "SDK HTTP OK : contrats, confirmation, multipart invalide et isolation de 20 requêtes concurrentes.",
  );
} finally {
  for (const account of accounts) {
    const response = await fetch(`${backend}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: account.username,
        password: account.password,
      }),
    });
    assert.equal(response.status, 200);
    const token = (await response.json()).data.token;
    const deleted = await fetch(
      `${backend}/api/user/${encodeURIComponent(account.username)}`,
      { method: "DELETE", headers: { Authorization: `Bearer ${token}` } },
    );
    assert.equal(deleted.status, 200);
  }
}
