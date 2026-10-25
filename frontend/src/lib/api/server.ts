import "server-only";
import { NextRequest, NextResponse } from "next/server";
import { createClient } from "./generated/client";
import type { CurrentUserModel } from "./generated/types.gen";
import type { CurrentUser } from "./types";

export const SESSION_COOKIE = "template_session";
export class BackendError extends Error {
  constructor(
    public status: number,
    message: string,
    public retryAfter?: string | null,
  ) {
    super(message);
  }
}

/** Une instance par requête : aucun JWT n’est conservé dans le singleton généré. */
export function createBackendClient(token?: string) {
  return createClient({
    baseUrl: process.env.BACKEND_URL || "http://127.0.0.1:8080",
    headers: {
      Accept: "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    fetch: (request) =>
      fetch(request, {
        cache: "no-store",
        redirect: "error",
        signal: AbortSignal.timeout(10_000),
      }),
  });
}

/** Normaliser les erreurs HTTP/réseau du SDK sans modifier le contrat du proxy navigateur. */
export function backendResult<T>(result: {
  data?: T;
  error?: unknown;
  response?: Response;
}): T {
  if (!result.response)
    throw new BackendError(
      502,
      "Le service est temporairement indisponible. Réessayez dans un instant.",
    );
  if (!result.response.ok) {
    const error = result.error;
    const rawMessage =
      error && typeof error === "object" && "message" in error
        ? String(error.message)
        : "";
    // Une permission insuffisante ne doit pas déconnecter un compte encore valide.
    const expiredSession = [
      "Token Invalide",
      "Session expirée",
      "Session expirée ; reconnectez-vous",
    ].includes(rawMessage);
    const status =
      result.response.status === 403 && expiredSession
        ? 401
        : result.response.status;
    const message =
      status === 401
        ? "Identifiant ou mot de passe incorrect, ou session expirée."
        : status >= 500
          ? "Le service est temporairement indisponible."
          : error &&
              typeof error === "object" &&
              "message" in error &&
              typeof error.message === "string"
            ? error.message
            : "Vérifiez les informations saisies.";
    throw new BackendError(
      status,
      message,
      result.response.headers.get("Retry-After"),
    );
  }
  if (result.data === undefined)
    throw new BackendError(502, "Réponse du service invalide.");
  return result.data;
}

/** Extraire une enveloppe FastAPI, avec les types de réponse inférés par le SDK. */
export function backendData<T>(result: {
  data?: { data?: T };
  error?: unknown;
  response?: Response;
}): T {
  const envelope = backendResult(result);
  if (
    !envelope ||
    typeof envelope !== "object" ||
    !("data" in envelope) ||
    envelope.data === undefined
  )
    throw new BackendError(502, "Réponse du service invalide.");
  return envelope.data;
}

/** Les lectures de profil, de configuration et de login exigent une donnée non nulle. */
export function backendRequired<T>(result: {
  data?: { data?: T };
  error?: unknown;
  response?: Response;
}): NonNullable<T> {
  const value = backendData(result);
  if (value === null || value === undefined)
    throw new BackendError(502, "Réponse du service invalide.");
  return value;
}

export function jsonData(data: unknown, status = 200) {
  return NextResponse.json(
    { data },
    { status, headers: { "Cache-Control": "private, no-store" } },
  );
}

export function setSession(
  response: NextResponse,
  token: string,
  maxAge = 8 * 60 * 60,
) {
  response.cookies.set(SESSION_COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge,
    secure:
      process.env.SESSION_COOKIE_SECURE === "true" ||
      (process.env.NODE_ENV === "production" &&
        process.env.SESSION_COOKIE_SECURE !== "false"),
  });
}

export function requireSession(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) throw new BackendError(401, "Connectez-vous pour continuer.");
  return token;
}

export function checkOrigin(request: NextRequest) {
  // Next peut exposer son adresse d’écoute interne dans request.url en Docker.
  // Host correspond à l’autorité visitée par le navigateur ; aucun X-Forwarded-Host implicite.
  const authority = request.headers.get("host") || request.nextUrl.host;
  const expected = new URL(
    process.env.APP_ORIGIN || `${request.nextUrl.protocol}//${authority}`,
  ).origin;
  if (request.headers.get("origin") !== expected)
    throw new BackendError(403, "Origine de la requête non autorisée.");
}

/** Lecture bornée : empêcher les corps JSON et les fichiers démesurés au niveau du proxy. */
export async function readBody(request: NextRequest, limit: number) {
  if (Number(request.headers.get("content-length")) > limit)
    throw new BackendError(
      413,
      "Le fichier ou la demande est trop volumineux.",
    );
  const reader = request.body?.getReader();
  if (!reader)
    throw new BackendError(400, "Le contenu de la demande est manquant.");
  const chunks: Uint8Array[] = [];
  let length = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    length += value.byteLength;
    if (length > limit) {
      await reader.cancel();
      throw new BackendError(
        413,
        "Le fichier ou la demande est trop volumineux.",
      );
    }
    chunks.push(value);
  }
  const body = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return body;
}

export async function readJson(request: NextRequest) {
  if (!request.headers.get("content-type")?.startsWith("application/json"))
    throw new BackendError(415, "Un contenu JSON est attendu.");
  const data = await readBody(request, 16 * 1024);
  try {
    return JSON.parse(new TextDecoder().decode(data));
  } catch {
    throw new BackendError(400, "Le contenu JSON est invalide.");
  }
}

export function browserUser(user: CurrentUserModel): CurrentUser {
  const version = user.profile_photo_url
    ? new URL(user.profile_photo_url, "http://backend").searchParams.get("v")
    : null;
  return {
    username: user.username,
    email: user.email ?? null,
    email_verified_at: user.email_verified_at ?? null,
    telephone: user.telephone ?? null,
    last_login_at: user.last_login_at ?? null,
    profile_photo_url: user.profile_photo_url
      ? `/api/profile/photo${version ? `?v=${encodeURIComponent(version)}` : ""}`
      : null,
  };
}
