/** Parcours HTTP des identifiants ; comptes temporaires sans envoi de mail réel. */
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
const username = `pwd_${randomUUID().replaceAll("-", "").slice(0, 16)}`;
const original = `Original-${randomUUID()}!`;
const changed = `Changed-${randomUUID()}!`;
const email = `${username}@example.com`;
let password = original;
let cookie = "";
let created = false;
async function request(
  path,
  { method = "GET", body, session = cookie, sentOrigin = origin } = {},
) {
  return fetch(`${base}/api${path}`, {
    method,
    headers: {
      ...(session ? { Cookie: session } : {}),
      ...(method !== "GET"
        ? { Origin: sentOrigin, "Content-Type": "application/json" }
        : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}
function setCookie(response) {
  cookie = response.headers.get("set-cookie").split(";")[0];
}
try {
  const registered = await request("/auth/register", {
    method: "POST",
    body: { username, password, telephone: "" },
  });
  assert.equal(registered.status, 200);
  created = true;
  setCookie(registered);
  assert.equal((await (await request("/session")).json()).data.email, null);
  const body = {
    current_password: password,
    new_password: changed,
    confirm_password: changed,
  };
  assert.equal(
    (await request("/profile/password", { method: "PUT", body, session: "" }))
      .status,
    401,
  );
  assert.equal(
    (
      await request("/profile/password", {
        method: "PUT",
        body,
        sentOrigin: "https://foreign.invalid",
      })
    ).status,
    403,
  );
  assert.equal(
    (
      await request("/profile/password", {
        method: "PUT",
        body: { ...body, confirm_password: "different" },
      })
    ).status,
    400,
  );
  assert.equal(
    (
      await request("/profile/password", {
        method: "PUT",
        body: { ...body, current_password: "wrong" },
      })
    ).status,
    400,
  );
  const oldCookie = cookie;
  const updated = await request("/profile/password", { method: "PUT", body });
  assert.equal(updated.status, 200);
  password = changed;
  assert.match(updated.headers.get("set-cookie"), /Max-Age=0/i);
  assert.equal(
    (await (await request("/session", { session: oldCookie })).json()).data,
    null,
  );
  assert.equal(
    (
      await request("/auth/login", {
        method: "POST",
        body: { username, password: original },
      })
    ).status,
    401,
  );
  const login = await request("/auth/login", {
    method: "POST",
    body: { username, password },
  });
  assert.equal(login.status, 200);
  setCookie(login);
  const forgotten = await request("/auth/forgot-password", {
    method: "POST",
    body: { email: `unknown-${randomUUID()}@example.com` },
  });
  assert.equal(forgotten.status, 202);
  assert.equal(
    (
      await request("/auth/reset-password", {
        method: "POST",
        body: {
          token: "x".repeat(43),
          new_password: original,
          confirm_password: original,
        },
      })
    ).status,
    400,
  );
  assert.equal(
    (
      await request("/profile/email", {
        method: "PATCH",
        body: { email, current_password: "wrong" },
      })
    ).status,
    400,
  );
  const savedEmail = await request("/profile/email", {
    method: "PATCH",
    body: { email, current_password: password },
  });
  assert.equal(savedEmail.status, 200);
  assert.match(savedEmail.headers.get("set-cookie"), /Max-Age=0/i);
  const relogin = await request("/auth/login", {
    method: "POST",
    body: { username, password },
  });
  setCookie(relogin);
  assert.equal((await (await request("/session")).json()).data.email, email);
  console.log(
    "Identifiants HTTP OK : réauthentification, changement, révocation, adresse privée et récupération générique.",
  );
} finally {
  if (created) {
    const response = await fetch(`${backend}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    assert.equal(response.status, 200);
    const token = (await response.json()).data.token;
    const deleted = await fetch(`${backend}/api/user/${username}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    assert.equal(deleted.status, 200);
    console.log("Compte temporaire supprimé.");
  }
}
