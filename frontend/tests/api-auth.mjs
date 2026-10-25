/** Tests HTTP du parcours réel ; crée puis supprime un compte temporaire. */
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
const envFile = fileURLToPath(new URL("../../.env.dev", import.meta.url));
if (existsSync(envFile)) process.loadEnvFile(envFile);
import { randomUUID } from "node:crypto";
const base = process.env.FRONTEND_TEST_URL || "http://localhost:3000";
const backend = process.env.BACKEND_TEST_URL || process.env.BACKEND_URL || "http://localhost:8080";
const origin = new URL(base).origin;
const username = `e2e_${randomUUID().replaceAll("-", "").slice(0, 16)}`;
const password = `Test-${randomUUID()}!`;
let cookie = "";
let created = false;
async function request(
  path,
  {
    method = "GET",
    body,
    origin: sentOrigin = origin,
    session = cookie,
    headers: extra = {},
  } = {},
) {
  const headers = { ...extra, ...(session ? { Cookie: session } : {}) };
  if (method !== "GET") headers.Origin = sentOrigin;
  if (body !== undefined && !(body instanceof FormData))
    headers["Content-Type"] = "application/json";
  return fetch(`${base}/api${path}`, {
    method,
    headers,
    body:
      body === undefined
        ? undefined
        : body instanceof FormData
          ? body
          : JSON.stringify(body),
  });
}
try {
  assert.equal((await request("/session")).status, 200);
  assert.equal((await (await request("/session")).json()).data, null);
  assert.equal(
    (await request("/profile", { method: "PATCH", body: { telephone: "123" } }))
      .status,
    401,
  );
  assert.equal(
    (
      await request("/auth/login", {
        method: "POST",
        origin: "https://untrusted.invalid",
        body: { username, password },
      })
    ).status,
    403,
  );
  assert.equal(
    (
      await request("/auth/login", {
        method: "POST",
        body: { username, password: "incorrect" },
      })
    ).status,
    401,
  );
  const registration = await request("/auth/register", {
    method: "POST",
    body: { username, password, telephone: "" },
  });
  const registered = await registration.json();
  assert.equal(registration.status, 200, JSON.stringify(registered));
  created = true;
  const setCookie = registration.headers.get("set-cookie");
  assert.match(setCookie, /HttpOnly/i);
  assert.match(setCookie, /SameSite=lax/i);
  cookie = setCookie.split(";")[0];
  assert.equal(registered.data.username, username);
  assert.ok(registered.data.last_login_at.endsWith("Z"));
  assert.equal(registered.data.token, undefined);
  assert.equal(registered.data.password, undefined);
  assert.equal(
    (await (await request("/session")).json()).data.username,
    username,
  );
  assert.equal(
    (
      await request("/auth/register", {
        method: "POST",
        body: { username, password, telephone: "" },
      })
    ).status,
    400,
  );
  const updated = await request("/profile", {
    method: "PATCH",
    body: { telephone: "+22670000000" },
  });
  assert.equal(updated.status, 200);
  assert.equal((await updated.json()).data.telephone, "+22670000000");
  const badPhoto = new FormData();
  badPhoto.set(
    "photo",
    new Blob(["<svg/>"], { type: "image/svg+xml" }),
    "invalid.svg",
  );
  assert.equal(
    (await request("/profile/photo", { method: "PUT", body: badPhoto })).status,
    415,
  );
  const photo = new FormData();
  photo.set(
    "photo",
    new Blob(
      [
        Buffer.from(
          "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAGUlEQVR4nGOUSQtgIAUwkaR6VMOohiGlAQC1dgDyL12+YgAAAABJRU5ErkJggg==",
          "base64",
        ),
      ],
      { type: "image/png" },
    ),
    "profile.png",
  );
  const upload = await request("/profile/photo", {
    method: "PUT",
    body: photo,
  });
  assert.equal(upload.status, 200);
  const url = (await upload.json()).data.profile_photo_url;
  assert.ok(url.startsWith("/api/profile/photo?v="));
  const image = await fetch(`${base}${url}`, { headers: { Cookie: cookie } });
  assert.equal(image.status, 200);
  assert.equal(image.headers.get("content-type"), "image/webp");
  assert.equal((await request("/profile/photo", { session: "" })).status, 401);
  const logout = await request("/auth/logout", { method: "POST" });
  assert.equal(logout.status, 200);
  assert.match(logout.headers.get("set-cookie"), /Max-Age=0/i);
  cookie = "";
  assert.equal((await (await request("/session")).json()).data, null);
  const login = await request("/auth/login", {
    method: "POST",
    body: { username, password },
  });
  assert.equal(login.status, 200);
  cookie = login.headers.get("set-cookie").split(";")[0];
  assert.equal(
    (await (await request("/session")).json()).data.telephone,
    "+22670000000",
  );
  cookie = "template_session=invalid";
  assert.equal((await (await request("/session")).json()).data, null);
  console.log(
    "Parcours HTTP OK : inscription, session privée, contrôle d’origine, profil, photo, déconnexion et reconnexion.",
  );
} finally {
  if (created) {
    const response = await fetch(`${backend}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const envelope = await response.json();
    assert.equal(response.status, 200, "Connexion de nettoyage impossible");
    const deleted = await fetch(
      `${backend}/api/user/${encodeURIComponent(username)}`,
      {
        method: "DELETE",
        headers: { Authorization: `Bearer ${envelope.data.token}` },
      },
    );
    assert.equal(
      deleted.status,
      200,
      "Suppression du compte temporaire impossible",
    );
    console.log("Compte temporaire et photo supprimés.");
  }
}
