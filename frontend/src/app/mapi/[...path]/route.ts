import { NextRequest, NextResponse } from "next/server";
import { proxyTimeoutMs } from "./timeout";
import {
  BackendError,
  checkOrigin,
  readBody,
  SESSION_COOKIE,
} from "@/lib/api/server";
async function handle(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  try {
    if (!["GET", "HEAD"].includes(request.method)) checkOrigin(request);
    const parts = (await context.params).path;
    if (
      !parts.length ||
      parts.some((p) => !/^[a-zA-Z0-9_:-]+$/.test(p)) ||
      ![
        "meetings",
        "share",
        "settings",
        "notifications",
        "health",
        "mail",
        "events",
      ].includes(parts[0])
    )
      return NextResponse.json(
        { message: "Route introuvable" },
        { status: 404 },
      );
    const isEvents = request.method === "GET" && parts.length === 1 && parts[0] === "events";
    const headers = new Headers();
    for (const name of [
      "content-type",
      "x-share-token",
      "x-share-password",
      "x-guest-session",
      "x-chunk-digest",
      "range",
    ]) {
      const v = request.headers.get(name);
      if (v) headers.set(name, v);
    }
    const token = request.cookies.get(SESSION_COOKIE)?.value;
    if (token) headers.set("authorization", `Bearer ${token}`);
    const body = ["GET", "HEAD"].includes(request.method)
      ? undefined
      : await readBody(
          request,
          parts.includes("chunks") ? 8 * 1024 * 1024 : 2 * 1024 * 1024,
        );
    const response = await fetch(
      `${process.env.BACKEND_URL || "http://127.0.0.1:8080"}/api/memora/${parts.map(encodeURIComponent).join("/")}${request.nextUrl.search}`,
      {
        method: request.method,
        headers,
        body,
        cache: "no-store",
        redirect: "error",
        signal: isEvents ? request.signal : AbortSignal.timeout(
          proxyTimeoutMs(
            request.method,
            parts,
            process.env.MEMORA_CHAT_TIMEOUT_MS,
          ),
        ),
      },
    );
    const output = new Headers({
      "cache-control": "private, no-store",
      "x-content-type-options": "nosniff",
    });
    if (isEvents) output.set("x-accel-buffering", "no");
    for (const name of [
      "content-type",
      "content-length",
      "content-range",
      "accept-ranges",
      "content-disposition",
      "retry-after",
    ]) {
      const v = response.headers.get(name);
      if (v) output.set(name, v);
    }
    return new NextResponse(response.body, {
      status: response.status,
      headers: output,
    });
  } catch (error) {
    const timedOut = error instanceof Error && error.name === "TimeoutError";
    return NextResponse.json(
      {
        message: timedOut
          ? "La réponse n’a pas pu être reçue dans le délai autorisé. Votre réunion est conservée ; le traitement peut encore se terminer. Consultez l’historique avant de réessayer."
          : error instanceof BackendError
            ? error.message
            : "Le service est indisponible. Réessayez.",
      },
      {
        status: timedOut
          ? 504
          : error instanceof BackendError
            ? error.status
            : 502,
      },
    );
  }
}
export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
