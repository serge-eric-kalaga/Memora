import type { ApiEnvelope } from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Point d’entrée des appels navigateur : même origine, erreurs normalisées et annulation. */
export async function apiRequest<T>(
  path: string,
  options: Omit<RequestInit, "body"> & { body?: unknown } = {},
): Promise<T> {
  const { body, ...init } = options;
  const form = body instanceof FormData;
  const headers = new Headers(init.headers);
  if (body !== undefined && !form)
    headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      headers,
      credentials: "same-origin",
      cache: "no-store",
      body: body === undefined ? undefined : form ? body : JSON.stringify(body),
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new ApiError(
      "Connexion impossible. Vérifiez votre réseau puis réessayez.",
      0,
    );
  }
  const envelope = (await response
    .json()
    .catch(() => null)) as ApiEnvelope<T> | null;
  if (!response.ok) {
    if (response.status === 401 && typeof window !== "undefined")
      window.dispatchEvent(new Event("session-expired"));
    throw new ApiError(
      envelope?.message || "La demande a échoué. Réessayez.",
      response.status,
    );
  }
  if (!envelope || !("data" in envelope))
    throw new ApiError("Réponse du serveur invalide.", 502);
  return envelope.data;
}
