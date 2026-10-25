import { keepPreviousData, queryOptions } from "@tanstack/react-query";
import { z } from "zod";
import { apiRequest } from "./client";

/** Même contrat que ListParams de FastAPI ; les valeurs invalides sont refusées. */
export const listQuerySchema = z.object({
  page: z.coerce.number().int().min(1).max(1_000_000).default(1),
  page_size: z.coerce.number().int().min(1).max(100).default(20),
  q: z.string().max(100).default(""),
  sort: z.string().min(1).max(50).default("id"),
  order: z.enum(["asc", "desc"]).default("asc"),
});
export type ListQuery = z.infer<typeof listQuerySchema>;
export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

/** Revenir à la première page quand les critères changent. */
export function updateListQuery(
  current: ListQuery,
  changes: Partial<ListQuery>,
): ListQuery {
  const reset = ["q", "sort", "order", "page_size"].some(
    (key) =>
      key in changes &&
      changes[key as keyof ListQuery] !== current[key as keyof ListQuery],
  );
  return listQuerySchema.parse({
    ...current,
    ...changes,
    page: changes.page ?? (reset ? 1 : current.page),
  });
}

/** Options pour useQuery : critères dans la clé, annulation et page précédente conservée.
 * Inclure l’identité du compte dans key pour une liste propre à un utilisateur.
 */
export function paginatedQuery<T>(
  key: readonly unknown[],
  path: string,
  params: Partial<ListQuery> = {},
) {
  const query = listQuerySchema.parse(params);
  const search = new URLSearchParams(
    Object.entries(query).map(([name, value]) => [name, String(value)]),
  );
  return queryOptions({
    queryKey: [...key, query],
    queryFn: ({ signal }) => apiRequest<Page<T>>(`${path}?${search}`, { signal }),
    placeholderData: keepPreviousData,
  });
}
