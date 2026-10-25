import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import ts from "typescript";
import { QueryClient, QueryObserver } from "@tanstack/react-query";

const source = readFileSync(
  new URL("../src/features/admin/cache.ts", import.meta.url),
  "utf8",
);
const code = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText;
const { updateAdminCache } = await import(
  `data:text/javascript;base64,${Buffer.from(code).toString("base64")}`
);
const page = (items) => ({
  items,
  total: items.length,
  page: 1,
  page_size: 20,
  pages: 1,
});
const permission = {
  id: 8,
  name: "reports.export",
  description: "Export",
  is_active: true,
};
const role = {
  id: 3,
  name: "editor",
  description: "Editor",
  is_active: true,
  permissions: [permission],
};
function setup() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: Infinity, gcTime: Infinity },
    },
  });
  const counts = new Map(),
    stops = [];
  function watch(key, data) {
    client.setQueryData(key, data);
    const name = JSON.stringify(key);
    const observer = new QueryObserver(client, {
      queryKey: key,
      queryFn: async () => {
        counts.set(name, (counts.get(name) || 0) + 1);
        return data;
      },
      staleTime: Infinity,
    });
    stops.push(observer.subscribe(() => {}));
    return () => counts.get(name) || 0;
  }
  function close() {
    stops.forEach((stop) => stop());
    client.clear();
  }
  return { client, watch, close };
}

test("retirer une permission actualise le rôle sans recharger les catalogues ni les autres rôles", async () => {
  const { client, watch, close } = setup();
  try {
    const roles = watch(
      ["admin", "admin", "roles", { page: 1, q: "" }],
      page([role]),
    );
    const permissions = watch(
      ["admin", "admin", "permissions", { page: 1, q: "" }],
      page([permission]),
    );
    const detail = watch(["admin", "admin", "role", 3], role);
    const other = watch(["admin", "admin", "role", 7], { ...role, id: 7 });
    const rights = watch(["access", "admin"], {
      permissions: [permission.name],
    });
    await updateAdminCache(
      client,
      "admin",
      { kind: "link", path: "roles/3/permissions/8", enabled: false },
      null,
    );
    assert.deepEqual(
      client.getQueryData(["admin", "admin", "role", 3]).permissions,
      [],
    );
    assert.equal(roles(), 0);
    assert.equal(permissions(), 0);
    assert.equal(detail(), 0);
    assert.equal(other(), 0);
    assert.equal(rights(), 1);
    await updateAdminCache(
      client,
      "admin",
      { kind: "link", path: "roles/3/permissions/8", enabled: true },
      null,
    );
    assert.deepEqual(
      client.getQueryData(["admin", "admin", "role", 3]).permissions,
      [permission],
    );
    assert.equal(roles(), 0);
    assert.equal(permissions(), 0);
  } finally {
    close();
  }
});

test("modifier une description remplace la ligne concernée en préservant la page et les autres rôles", async () => {
  const { client, watch, close } = setup();
  try {
    const second = { ...role, id: 7, name: "viewer" };
    const count = watch(["admin", "admin", "roles", { page: 2, q: "" }], {
      ...page([role, second]),
      page: 2,
      pages: 2,
    });
    watch(["admin", "admin", "role", 3], role);
    const updated = { ...role, description: "Updated" };
    await updateAdminCache(
      client,
      "admin",
      {
        kind: "update",
        resource: "roles",
        id: 3,
        data: { description: "Updated", is_active: true },
      },
      updated,
    );
    const data = client.getQueryData([
      "admin",
      "admin",
      "roles",
      { page: 2, q: "" },
    ]);
    assert.equal(data.page, 2);
    assert.equal(data.items[0].description, "Updated");
    assert.equal(data.items[1], second);
    assert.equal(count(), 0);
    assert.deepEqual(
      client.getQueryData(["admin", "admin", "role", 3]).permissions,
      [permission],
    );
  } finally {
    close();
  }
});

test("une attribution directe ne relit que le compte cible", async () => {
  const { client, watch, close } = setup();
  try {
    const target = watch(["admin", "admin", "user", "alex"], {
      username: "alex",
    });
    const other = watch(["admin", "admin", "user", "camille"], {
      username: "camille",
    });
    const roles = watch(["admin", "admin", "roles", { page: 1 }], page([role]));
    const own = watch(["access", "admin"], { username: "admin" });
    await updateAdminCache(
      client,
      "admin",
      { kind: "link", path: "users/alex/permissions/8", enabled: true },
      null,
    );
    assert.equal(target(), 1);
    assert.equal(other(), 0);
    assert.equal(roles(), 0);
    assert.equal(own(), 0);
  } finally {
    close();
  }
});
