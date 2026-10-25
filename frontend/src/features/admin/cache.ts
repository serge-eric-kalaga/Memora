import type { QueryClient } from "@tanstack/react-query";
import type { AdminAction, AccessItem, RoleDetail } from "./api";
import type { Page } from "@/lib/api/pagination";

/** Mettre à jour les objets connus et ne relire que les droits effectivement impactés. */
export async function updateAdminCache(
  client: QueryClient,
  identity: string,
  action: AdminAction,
  result: unknown,
) {
  const base = ["admin", identity];
  const ownAccess = () =>
    client.invalidateQueries({ queryKey: ["access", identity], exact: true });
  const userAccess = () =>
    client.invalidateQueries({ queryKey: [...base, "user"] });
  if (action.kind === "user" || action.kind === "role") {
    await client.invalidateQueries({
      queryKey: [...base, action.kind === "user" ? "users" : "roles"],
    });
    return;
  }
  if (action.kind === "update") {
    const item = result as AccessItem;
    client.setQueriesData<Page<AccessItem>>(
      { queryKey: [...base, action.resource] },
      (page) =>
        page && {
          ...page,
          items: page.items.map((row) => (row.id === item.id ? item : row)),
        },
    );
    if (action.resource === "roles") {
      client.setQueryData<RoleDetail>(
        [...base, "role", item.id],
        (role) => role && { ...role, ...item },
      );
    } else {
      client.setQueriesData<RoleDetail>(
        { queryKey: [...base, "role"] },
        (role) =>
          role && {
            ...role,
            permissions: role.permissions.map((permission) =>
              permission.id === item.id ? item : permission,
            ),
          },
      );
    }
    await Promise.all([userAccess(), ownAccess()]);
    return;
  }
  const parts = action.path.split("/");
  if (parts[0] === "users") {
    const username = decodeURIComponent(parts[1]);
    await Promise.all([
      client.invalidateQueries({
        queryKey: [...base, "user", username],
        exact: true,
      }),
      ...(username === identity ? [ownAccess()] : []),
    ]);
    return;
  }
  const roleId = Number(parts[1]),
    permissionId = Number(parts[3]);
  const permission = client
    .getQueriesData<Page<AccessItem>>({ queryKey: [...base, "permissions"] })
    .flatMap(([, page]) => page?.items || [])
    .find((item) => item.id === permissionId);
  if (!action.enabled || permission) {
    client.setQueryData<RoleDetail>([...base, "role", roleId], (role) => {
      if (!role) return role;
      const permissions = role.permissions.filter(
        (item) => item.id !== permissionId,
      );
      if (action.enabled && permission) permissions.push(permission);
      return {
        ...role,
        permissions: permissions.sort((a, b) => a.name.localeCompare(b.name)),
      };
    });
    // Les catalogues ne changent pas lors d’une attribution. Marquer seulement ce détail périmé.
    await client.invalidateQueries({
      queryKey: [...base, "role", roleId],
      exact: true,
      refetchType: "none",
    });
  } else {
    await client.invalidateQueries({
      queryKey: [...base, "role", roleId],
      exact: true,
    });
  }
  await Promise.all([userAccess(), ownAccess()]);
}
