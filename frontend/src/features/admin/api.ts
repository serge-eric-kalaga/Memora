import { apiRequest } from "@/lib/api/client";
import type {
  AdminCreateUser,
  AdminUser,
  AccessItem,
  RoleDetail,
  UserAccess,
} from "@/lib/api/generated/types.gen";
import type { Page } from "@/lib/api/pagination";

export type { AdminUser, AccessItem, RoleDetail, UserAccess };
export type AdminAction =
  | { kind: "user"; data: AdminCreateUser }
  | { kind: "role"; name: string }
  | {
      kind: "update";
      resource: "roles" | "permissions";
      id: number;
      data: { description: string; is_active: boolean };
    }
  | { kind: "link"; path: string; enabled: boolean };

/** Les appels navigateur passent uniquement par la liste blanche du proxy Next.js. */
export const adminApi = {
  me: (signal?: AbortSignal) => apiRequest<UserAccess>("/admin/me", { signal }),
  list: <T>(
    resource: "users" | "roles" | "permissions",
    page: number,
    q: string,
    signal?: AbortSignal,
  ) =>
    apiRequest<Page<T>>(
      `/admin/${resource}?${new URLSearchParams({ page: String(page), page_size: "20", q })}`,
      { signal },
    ),
  user: (username: string, signal?: AbortSignal) =>
    apiRequest<UserAccess>(`/admin/users/${encodeURIComponent(username)}`, {
      signal,
    }),
  role: (id: number, signal?: AbortSignal) =>
    apiRequest<RoleDetail>(`/admin/roles/${id}`, { signal }),
  execute: async (action: AdminAction): Promise<unknown> => {
    if (action.kind === "update")
      return apiRequest<AccessItem>(`/admin/${action.resource}/${action.id}`, {
        method: "PATCH",
        body: action.data,
      });
    if (action.kind === "link")
      return apiRequest<null>(`/admin/${action.path}`, {
        method: action.enabled ? "PUT" : "DELETE",
      });
    if (action.kind === "user")
      return apiRequest<AdminUser>("/admin/users", {
        method: "POST",
        body: action.data,
      });
    if (action.kind === "role")
      return apiRequest<AccessItem>("/admin/roles", {
        method: "POST",
        body: { name: action.name },
      });
    throw new Error("Action inconnue");
  },
};
