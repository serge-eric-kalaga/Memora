import "server-only";
import { NextRequest } from "next/server";
import { z } from "zod";
import { registerSchema } from "@/features/auth/schemas";
import { listQuerySchema } from "@/lib/api/pagination";
import {
  BackendError,
  backendData,
  backendRequired,
  createBackendClient,
  jsonData,
  readJson,
} from "@/lib/api/server";
import {
  getMyAccess,
  listAdminUsers,
  adminCreateUser,
  listRoles,
  createRole,
  getRole,
  listPermissions,
  updateRole,
  updatePermission,
  getUserAccess,
  grantUserRole,
  revokeUserRole,
  grantUserPermission,
  revokeUserPermission,
  grantRolePermission,
  revokeRolePermission,
} from "@/lib/api/generated/sdk.gen";

/** Liste blanche d’opérations d’administration ; le backend reste l’autorité des droits. */
export async function adminProxy(
  request: NextRequest,
  path: string,
  token: string,
) {
  const client = createBackendClient(token);
  const method = request.method;
  if (method === "GET" && path === "admin/me")
    return jsonData(backendRequired(await getMyAccess({ client })));
  if (
    method === "GET" &&
    ["admin/users", "admin/roles", "admin/permissions"].includes(path)
  ) {
    const parsed = listQuerySchema.safeParse(
      Object.fromEntries(request.nextUrl.searchParams),
    );
    if (!parsed.success)
      throw new BackendError(422, "Paramètres de liste invalides.");
    const options = { client, query: parsed.data };
    if (path === "admin/users")
      return jsonData(backendRequired(await listAdminUsers(options)));
    if (path === "admin/roles")
      return jsonData(backendRequired(await listRoles(options)));
    return jsonData(backendRequired(await listPermissions(options)));
  }
  if (method === "POST" && path === "admin/users") {
    const input = registerSchema.strict().safeParse(await readJson(request));
    if (!input.success)
      throw new BackendError(400, "Vérifiez les informations saisies.");
    return jsonData(
      backendRequired(
        await adminCreateUser({
          client,
          body: {
            ...input.data,
            email: input.data.email || null,
            language: request.headers.get("accept-language")?.startsWith("en")
              ? "en"
              : "fr",
          },
        }),
      ),
    );
  }
  if (method === "POST" && path === "admin/roles") {
    const input = z
      .object({ name: z.string().regex(/^[a-z][a-z0-9_.:-]{0,99}$/) })
      .strict()
      .safeParse(await readJson(request));
    if (!input.success)
      throw new BackendError(400, "Nom de rôle ou permission invalide.");
    const result = await createRole({ client, body: input.data });
    return jsonData(backendRequired(result));
  }
  const metadata = /^admin\/(roles|permissions)\/([1-9]\d*)$/.exec(path);
  if (method === "PATCH" && metadata) {
    const input = z
      .object({ description: z.string().max(500), is_active: z.boolean() })
      .strict()
      .safeParse(await readJson(request));
    if (!input.success)
      throw new BackendError(400, "Vérifiez les informations saisies.");
    const id = Number(metadata[2]);
    return jsonData(
      backendRequired(
        metadata[1] === "roles"
          ? await updateRole({
              client,
              path: { role_id: id },
              body: input.data,
            })
          : await updatePermission({
              client,
              path: { permission_id: id },
              body: input.data,
            }),
      ),
    );
  }
  const role = /^admin\/roles\/([1-9]\d*)$/.exec(path);
  if (method === "GET" && role)
    return jsonData(
      backendRequired(
        await getRole({ client, path: { role_id: Number(role[1]) } }),
      ),
    );
  const user = /^admin\/users\/([^/]+)$/.exec(path);
  if (method === "GET" && user)
    return jsonData(
      backendRequired(
        await getUserAccess({ client, path: { username: user[1] } }),
      ),
    );
  const userLink =
    /^admin\/users\/([^/]+)\/(roles|permissions)\/([1-9]\d*)$/.exec(path);
  if (["PUT", "DELETE"].includes(method) && userLink) {
    const username = userLink[1],
      id = Number(userLink[3]);
    if (userLink[2] === "roles") {
      const options = { client, path: { username, role_id: id } };
      backendData(
        method === "PUT"
          ? await grantUserRole(options)
          : await revokeUserRole(options),
      );
    } else {
      const options = { client, path: { username, permission_id: id } };
      backendData(
        method === "PUT"
          ? await grantUserPermission(options)
          : await revokeUserPermission(options),
      );
    }
    return jsonData(null);
  }
  const roleLink = /^admin\/roles\/([1-9]\d*)\/permissions\/([1-9]\d*)$/.exec(
    path,
  );
  if (["PUT", "DELETE"].includes(method) && roleLink) {
    const options = {
      client,
      path: {
        role_id: Number(roleLink[1]),
        permission_id: Number(roleLink[2]),
      },
    };
    backendData(
      method === "PUT"
        ? await grantRolePermission(options)
        : await revokeRolePermission(options),
    );
    return jsonData(null);
  }
  throw new BackendError(404, "Route introuvable.");
}
