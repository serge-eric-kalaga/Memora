import { adminProxy } from "@/features/admin/proxy";
import { listQuerySchema } from "@/lib/api/pagination";
import { NextRequest, NextResponse } from "next/server";
import {
  loginSchema,
  registerSchema,
  profileSchema,
  changePasswordSchema,
  changeEmailSchema,
  forgotPasswordSchema,
  resetPasswordSchema,
  confirmEmailSchema,
} from "@/features/auth/schemas";
import {
  BackendError,
  backendData,
  backendRequired,
  backendResult,
  createBackendClient,
  browserUser,
  checkOrigin,
  jsonData,
  readBody,
  readJson,
  requireSession,
  SESSION_COOKIE,
  setSession,
} from "@/lib/api/server";
import {
  authConfig,
  authRegister,
  authLogin,
  authForgotPassword,
  authResetPassword,
  authResendVerification,
  authVerifyEmail,
  getCurrentUser,
  listUsersPage,
  updateCurrentUser,
  changePassword,
  changeEmail,
  uploadProfilePhoto,
  getProfilePhoto,
} from "@/lib/api/generated/sdk.gen";

type Context = { params: Promise<{ path: string[] }> };

/** Proxy limité aux routes du compte ; aucune URL arbitraire ni jeton côté client. */
async function handle(request: NextRequest, context: Context) {
  const path = (await context.params).path.join("/");
  const method = request.method;
  try {
    if (method !== "GET") checkOrigin(request);
    if (path.startsWith("admin/"))
      return await adminProxy(request, path, requireSession(request));
    if (path === "auth/config" && method === "GET") {
      return jsonData(
        backendRequired(await authConfig({ client: createBackendClient() })),
      );
    }
    if (path === "auth/resend-verification" && method === "POST") {
      const input = forgotPasswordSchema.safeParse(await readJson(request));
      if (!input.success)
        throw new BackendError(400, "Adresse e-mail invalide.");
      backendData(
        await authResendVerification({
          client: createBackendClient(),
          body: {
            ...input.data,
            language: request.headers.get("accept-language")?.startsWith("en")
              ? "en"
              : "fr",
          },
        }),
      );
      return jsonData(null, 202);
    }
    if (path === "auth/verify-email" && method === "POST") {
      const input = confirmEmailSchema.safeParse(await readJson(request));
      if (!input.success)
        throw new BackendError(
          400,
          "Le lien de confirmation est invalide ou a expiré. Demandez un nouveau lien.",
        );
      backendData(
        await authVerifyEmail({
          client: createBackendClient(),
          body: input.data,
        }),
      );
      const response = jsonData(null);
      setSession(response, "", 0);
      return response;
    }
    if (path === "auth/logout" && method === "POST") {
      const response = jsonData(null);
      setSession(response, "", 0);
      return response;
    }
    if (
      (path === "auth/login" || path === "auth/register") &&
      method === "POST"
    ) {
      const input = await readJson(request);
      const parsed = (
        path === "auth/register" ? registerSchema : loginSchema
      ).safeParse(input);
      if (!parsed.success)
        throw new BackendError(
          400,
          parsed.error.issues[0]?.message ||
            "Vérifiez les informations saisies.",
        );
      if (path === "auth/register") {
        const registration = backendRequired(
          await authRegister({
            client: createBackendClient(),
            body: {
              ...parsed.data,
              language: request.headers.get("accept-language")?.startsWith("en")
                ? "en"
                : "fr",
              email:
                "email" in parsed.data && typeof parsed.data.email === "string"
                  ? parsed.data.email || null
                  : undefined,
            },
          }),
        );
        if (registration.verification_required) {
          const response = jsonData(null, 202);
          setSession(response, "", 0);
          return response;
        }
      }
      const login = backendRequired(
        await authLogin({
          client: createBackendClient(),
          body: {
            username: parsed.data.username,
            password: parsed.data.password,
          },
        }),
      );
      if (typeof login.token !== "string" || login.token.length > 4096)
        throw new BackendError(502, "Réponse de connexion invalide.");
      const user = backendRequired(
        await getCurrentUser({ client: createBackendClient(login.token) }),
      );
      const response = jsonData(browserUser(user));
      setSession(response, login.token);
      return response;
    }
    if (path === "auth/forgot-password" && method === "POST") {
      const body = await readJson(request);
      const input = forgotPasswordSchema.safeParse(body);
      if (!input.success)
        throw new BackendError(400, "Adresse e-mail invalide.");
      const language = request.headers.get("accept-language")?.startsWith("en")
        ? "en"
        : "fr";
      backendData(
        await authForgotPassword({
          client: createBackendClient(),
          body: { ...input.data, language },
        }),
      );
      return jsonData(null, 202);
    }
    if (path === "auth/reset-password" && method === "POST") {
      const input = resetPasswordSchema.safeParse(await readJson(request));
      if (!input.success)
        throw new BackendError(
          400,
          input.error.issues[0]?.message ||
            "Vérifiez les informations saisies.",
        );
      backendData(
        await authResetPassword({
          client: createBackendClient(),
          headers: {
            "Accept-Language": request.headers.get("accept-language") || "fr",
          },
          body: {
            token: input.data.token,
            new_password: input.data.new_password,
          },
        }),
      );
      const response = jsonData(null);
      setSession(response, "", 0);
      return response;
    }
    if (
      (path === "profile/password" && method === "PUT") ||
      (path === "profile/email" && method === "PATCH")
    ) {
      const token = requireSession(request);
      const password = path === "profile/password";
      const input = (
        password ? changePasswordSchema : changeEmailSchema
      ).safeParse(await readJson(request));
      if (!input.success)
        throw new BackendError(
          400,
          input.error.issues[0]?.message ||
            "Vérifiez les informations saisies.",
        );
      const client = createBackendClient(token);
      const headers = {
        "Accept-Language": request.headers.get("accept-language") || "fr",
      };
      if ("new_password" in input.data) {
        backendData(
          await changePassword({
            client,
            headers,
            body: {
              current_password: input.data.current_password,
              new_password: input.data.new_password,
            },
          }),
        );
      } else {
        backendData(await changeEmail({ client, headers, body: input.data }));
      }
      const response = jsonData(null);
      setSession(response, "", 0);
      return response;
    }
    if (path === "users" && method === "GET") {
      const token = requireSession(request);
      const params = listQuerySchema.safeParse(
        Object.fromEntries(request.nextUrl.searchParams),
      );
      if (!params.success)
        throw new BackendError(422, "Paramètres de liste invalides.");
      return jsonData(
        backendRequired(
          await listUsersPage({
            client: createBackendClient(token),
            query: params.data,
          }),
        ),
      );
    }
    if (path === "session" && method === "GET") {
      const token = request.cookies.get(SESSION_COOKIE)?.value;
      if (!token) return jsonData(null);
      try {
        return jsonData(
          browserUser(
            backendRequired(
              await getCurrentUser({ client: createBackendClient(token) }),
            ),
          ),
        );
      } catch (error) {
        if (
          error instanceof BackendError &&
          [401, 404].includes(error.status)
        ) {
          const response = jsonData(null);
          setSession(response, "", 0);
          return response;
        }
        throw error;
      }
    }
    if (path === "profile" && method === "PATCH") {
      const token = requireSession(request);
      const input = profileSchema.safeParse(await readJson(request));
      if (!input.success)
        throw new BackendError(
          400,
          "Le téléphone doit contenir au maximum 32 caractères.",
        );
      const user = backendRequired(
        await updateCurrentUser({
          client: createBackendClient(token),
          body: { telephone: input.data.telephone || null },
        }),
      );
      return jsonData(browserUser(user));
    }
    if (path === "profile/photo" && method === "PUT") {
      const token = requireSession(request);
      const type = request.headers.get("content-type") || "";
      if (!type.startsWith("multipart/form-data;"))
        throw new BackendError(415, "Sélectionnez une photo à téléverser.");
      const body = await readBody(request, 6 * 1024 * 1024);
      let form: FormData;
      try {
        form = await new Response(body, {
          headers: { "Content-Type": type },
        }).formData();
      } catch {
        throw new BackendError(400, "Sélectionnez une photo à téléverser.");
      }
      const photo = form.get("photo");
      if (!(photo instanceof File))
        throw new BackendError(400, "Sélectionnez une photo à téléverser.");
      const client = createBackendClient(token);
      backendData(await uploadProfilePhoto({ client, body: { photo } }));
      return jsonData(
        browserUser(backendRequired(await getCurrentUser({ client }))),
      );
    }
    if (path === "profile/photo" && method === "GET") {
      const token = requireSession(request);
      const user = backendRequired(
        await getCurrentUser({ client: createBackendClient(token) }),
      );
      if (!user.profile_photo_url)
        throw new BackendError(404, "Aucune photo de profil.");
      const photo = backendResult(
        await getProfilePhoto({
          client: createBackendClient(token),
          path: { username: user.username },
          parseAs: "blob",
        }),
      );
      if (!(photo instanceof Blob))
        throw new BackendError(502, "Photo indisponible.");
      return new NextResponse(photo, {
        headers: {
          "Content-Type": "image/webp",
          "Cache-Control": "private, no-store",
          "X-Content-Type-Options": "nosniff",
        },
      });
    }
    return NextResponse.json(
      { message: "Route introuvable." },
      { status: 404 },
    );
  } catch (error) {
    const status = error instanceof BackendError ? error.status : 500;
    const response = NextResponse.json(
      {
        message:
          error instanceof BackendError
            ? error.message
            : "Une erreur est survenue. Réessayez.",
      },
      { status, headers: { "Cache-Control": "private, no-store" } },
    );
    if (error instanceof BackendError && error.retryAfter)
      response.headers.set("Retry-After", error.retryAfter);
    if (status === 401) setSession(response, "", 0);
    return response;
  }
}
export const GET = handle;
export const POST = handle;
export const PATCH = handle;
export const PUT = handle;
export const DELETE = handle;
