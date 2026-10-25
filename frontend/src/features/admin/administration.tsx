"use client";

import {
  useEffect,
  useState,
  useId,
  type FormEvent,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import {
  Users,
  Shield,
  KeyRound,
  ChevronRight,
  Plus,
  Search,
  UserRound,
  LockKeyhole,
} from "lucide-react";
import styles from "./administration.module.css";
import { useQuery } from "@tanstack/react-query";
import { useSession } from "@/features/auth/hooks";
import { Field } from "@/components/ui/field";
import { useI18n } from "@/lib/i18n/use-i18n";
import {
  adminApi,
  type AdminAction,
  type AccessItem,
  type AdminUser,
} from "./api";
import { useAdminMutation, useMyAccess } from "./hooks";

/** Trois espaces indépendants ; chaque attribution affiche explicitement sa cible. */
export function Administration() {
  const { t } = useI18n();
  const router = useRouter();
  const session = useSession();
  const access = useMyAccess();
  const mutation = useAdminMutation();
  const [tab, setTab] = useState<"users" | "roles" | "permissions">("users");
  const [selectedUser, setSelectedUser] = useState("");
  const [selectedRole, setSelectedRole] = useState<number | null>(null);
  const [selectedPermission, setSelectedPermission] =
    useState<AccessItem | null>(null);
  const [notice, setNotice] = useState<{
    error: boolean;
    message: string;
  } | null>(null);
  const can = (permission: string) =>
    !!access.data &&
    (access.data.is_superuser || access.data.permissions.includes(permission));
  const canRead = can("access.read"),
    canManage = can("access.manage"),
    canCreate = can("users.create");
  const identity = session.data?.username;
  const userAccess = useQuery({
    queryKey: ["admin", identity, "user", selectedUser],
    queryFn: ({ signal }) => adminApi.user(selectedUser, signal),
    enabled: !!selectedUser && canRead,
    retry: false,
  });
  const roleAccess = useQuery({
    queryKey: ["admin", identity, "role", selectedRole],
    queryFn: ({ signal }) => adminApi.role(selectedRole!, signal),
    enabled: selectedRole !== null && canRead,
    retry: false,
  });
  useEffect(() => {
    if (session.isSuccess && !session.data) router.replace("/connexion");
  }, [session.isSuccess, session.data, router]);
  async function run(action: AdminAction, form?: HTMLFormElement) {
    setNotice(null);
    try {
      const result = await mutation.mutateAsync(action);
      if (action.kind === "update" && action.resource === "permissions")
        setSelectedPermission(result as AccessItem);
      if (action.kind !== "update") form?.reset();
      setNotice({ error: false, message: "Modification enregistrée." });
    } catch (error) {
      setNotice({
        error: true,
        message:
          error instanceof Error ? error.message : "La modification a échoué.",
      });
    } finally {
      const password = form?.querySelector<HTMLInputElement>(
        'input[type="password"]',
      );
      if (password) password.value = "";
      mutation.reset();
    }
  }
  const busy = mutation.isPending;
  if (session.isError || access.isError)
    return (
      <main className={`${styles.root} page-shell admin-page`}>
        <p role="alert">{t("Impossible de charger les droits.")}</p>
        <button
          className="button button-quiet"
          onClick={() => {
            void session.refetch();
            void access.refetch();
          }}
        >
          {t("Réessayer")}
        </button>
      </main>
    );
  if (!session.data || access.isPending)
    return (
      <main className={`${styles.root} page-shell admin-page`} aria-busy="true">
        {t("Chargement…")}
      </main>
    );
  if (!canRead && !canManage && !canCreate)
    return (
      <main className={`${styles.root} page-shell admin-page`}>
        <h1>{t("Accès réservé")}</h1>
      </main>
    );
  const badge = (item: AccessItem) => (
    <span className={`admin-status ${item.is_active ? "" : "is-inactive"}`}>
      {t(item.is_active ? "Actif" : "Désactivé")}
    </span>
  );
  const permissionChoice = (
    permission: AccessItem,
    target: "user" | "role",
  ) => {
    const forUser = target === "user";
    const data = forUser ? userAccess : roleAccess;
    const checked = forUser
      ? userAccess.data?.direct_permissions.includes(permission.name)
      : roleAccess.data?.permissions.some((p) => p.id === permission.id);
    const inherited =
      forUser &&
      userAccess.data?.permissions.includes(permission.name) &&
      !checked;
    return (
      <label className="admin-permission admin-check">
        <input
          type="checkbox"
          checked={!!checked}
          disabled={
            !canManage ||
            busy ||
            !data.data ||
            data.isFetching ||
            (!permission.is_active && !checked)
          }
          onChange={(e) =>
            void run({
              kind: "link",
              path: forUser
                ? `users/${encodeURIComponent(selectedUser)}/permissions/${permission.id}`
                : `roles/${selectedRole}/permissions/${permission.id}`,
              enabled: e.target.checked,
            })
          }
        />
        <span>
          <strong>{permission.name}</strong>
          <small>{permission.description}</small>
          {inherited && <small>{t("Héritée d’un rôle")}</small>}
        </span>
        {badge(permission)}
      </label>
    );
  };
  return (
    <main className={`${styles.root} page-shell admin-page`}>
      <div className="admin-topbar">
        <span>
          <Shield size={16} aria-hidden="true" />
          {t("Administration")}
        </span>
        <ChevronRight size={14} aria-hidden="true" />
        <span>{t("Gestion des accès")}</span>
        {access.data?.is_superuser && (
          <span className="admin-badge">
            <span className="admin-dot" />
            {t("Super administrateur")}
          </span>
        )}
      </div>
      <div className="admin-layout">
        <aside className="admin-sidebar">
          <p className="admin-nav-label">{t("ESPACE DE GESTION")}</p>
          <nav className="admin-tabs" aria-label={t("Administration")}>
            {(
              [
                ["users", "Utilisateurs", Users],
                ["roles", "Rôles", Shield],
                ["permissions", "Permissions", KeyRound],
              ] as const
            ).map(([key, label, Icon]) => (
              <button
                key={key}
                className={tab === key ? "is-selected" : ""}
                aria-current={tab === key ? "page" : undefined}
                onClick={() => {
                  setTab(key);
                  setNotice(null);
                }}
              >
                <Icon size={18} aria-hidden="true" />
                <span>{t(label)}</span>
                <ChevronRight
                  size={14}
                  className="admin-nav-arrow"
                  aria-hidden="true"
                />
              </button>
            ))}
          </nav>
          <div className="admin-sidebar-note">
            <LockKeyhole size={18} aria-hidden="true" />
            <strong>{t("Contrôle des accès")}</strong>
            <p>
              {t("Les droits sont vérifiés par le serveur à chaque opération.")}
            </p>
          </div>
        </aside>
        <div className="admin-content">
          <header className="admin-heading">
            <div>
              <h1>
                {t(
                  tab === "users"
                    ? "Utilisateurs"
                    : tab === "roles"
                      ? "Rôles"
                      : "Permissions",
                )}
              </h1>
              <p>
                {t(
                  tab === "users"
                    ? "Gérez les comptes et les accès de votre équipe."
                    : tab === "roles"
                      ? "Organisez les droits de votre application par rôle."
                      : "Consultez les droits disponibles dans votre application.",
                )}
              </p>
            </div>
            {tab === "users" && canCreate && (
              <details className="admin-create">
                <summary>
                  <Plus size={16} aria-hidden="true" />
                  {t("Créer un utilisateur")}
                </summary>
                <form
                  className="admin-card"
                  onSubmit={(event: FormEvent<HTMLFormElement>) => {
                    event.preventDefault();
                    const form = event.currentTarget,
                      values = new FormData(form);
                    void run(
                      {
                        kind: "user",
                        data: {
                          username: String(values.get("username")),
                          email: String(values.get("email") || "") || undefined,
                          telephone: String(values.get("telephone") || ""),
                          password: String(values.get("password")),
                        },
                      },
                      form,
                    );
                  }}
                >
                  <h2>{t("Créer un utilisateur")}</h2>
                  <Field
                    id="admin-username"
                    name="username"
                    label={t("Nom d’utilisateur")}
                    required
                    minLength={3}
                    maxLength={64}
                    autoComplete="off"
                  />
                  <Field
                    id="admin-email"
                    name="email"
                    label={t("Adresse e-mail")}
                    type="email"
                    maxLength={254}
                  />
                  <Field
                    id="admin-phone"
                    name="telephone"
                    label={t("Téléphone")}
                    maxLength={32}
                  />
                  <Field
                    id="admin-password"
                    name="password"
                    label={t("Mot de passe")}
                    type="password"
                    autoComplete="new-password"
                    required
                    minLength={8}
                    maxLength={128}
                  />
                  <p className="field-hint">
                    {t(
                      "Un compte créé ici est un utilisateur normal. La confirmation d’e-mail suit la configuration de l’application.",
                    )}
                  </p>
                  <button className="button button-primary" disabled={busy}>
                    {t("Créer le compte")}
                  </button>
                </form>
              </details>
            )}
            {tab === "roles" && canManage && (
              <details className="admin-create">
                <summary>
                  <Plus size={16} aria-hidden="true" />
                  {t("Créer un rôle")}
                </summary>
                <NameForm
                  kind="role"
                  title={t("Créer un rôle")}
                  busy={busy}
                  run={run}
                />
              </details>
            )}
          </header>
          {notice && (
            <p
              className={`notice ${notice.error ? "notice-error" : "notice-success"}`}
              role={notice.error ? "alert" : "status"}
            >
              {t(notice.message)}
            </p>
          )}
          {tab === "users" && (
            <>
              <div className="admin-workspace">
                <aside>
                  {canRead && (
                    <Catalogue<AdminUser>
                      resource="users"
                      identity={identity!}
                      title={t("Utilisateurs")}
                      render={(user) => (
                        <button
                          className={`admin-select ${selectedUser === user.username ? "is-selected" : ""}`}
                          aria-pressed={selectedUser === user.username}
                          onClick={() => setSelectedUser(user.username)}
                        >
                          <span className="admin-avatar" aria-hidden="true">
                            {user.username.slice(0, 2).toUpperCase()}
                          </span>
                          <span className="admin-identity">
                            <strong>{user.username}</strong>
                            <span>
                              {user.email || t("Aucune adresse e-mail")}
                            </span>
                          </span>
                          <span
                            className={`admin-status ${user.is_superuser ? "is-admin" : "is-neutral"}`}
                          >
                            {t(
                              user.is_superuser
                                ? "Super administrateur"
                                : "Utilisateur",
                            )}
                          </span>
                          <ChevronRight
                            size={16}
                            className="admin-row-arrow"
                            aria-hidden="true"
                          />
                        </button>
                      )}
                    />
                  )}
                </aside>
                <section
                  className="admin-detail"
                  aria-label={t("Droits du compte")}
                >
                  {selectedUser ? (
                    <>
                      <header className="admin-card admin-user-heading">
                        <span className="admin-avatar" aria-hidden="true">
                          {selectedUser.slice(0, 2).toUpperCase()}
                        </span>
                        <div>
                          <h2>{selectedUser}</h2>
                          <p>{t("Droits du compte")}</p>
                        </div>
                        {userAccess.isError && (
                          <p role="alert">
                            {t("Impossible de charger les droits.")}
                          </p>
                        )}
                      </header>
                      {userAccess.data?.is_superuser ? (
                        <p className="admin-card">
                          {t("Accès complet, y compris aux futurs privilèges.")}
                        </p>
                      ) : (
                        <>
                          <Catalogue<AccessItem>
                            resource="roles"
                            identity={identity!}
                            title={t("Rôles attribués")}
                            render={(role) => {
                              const checked =
                                userAccess.data?.roles.includes(role.name) ??
                                false;
                              return (
                                <label className="admin-permission admin-check">
                                  <input
                                    type="checkbox"
                                    checked={checked}
                                    disabled={
                                      !canManage ||
                                      busy ||
                                      !userAccess.data ||
                                      userAccess.isFetching ||
                                      (!role.is_active && !checked)
                                    }
                                    onChange={(e) =>
                                      void run({
                                        kind: "link",
                                        path: `users/${encodeURIComponent(selectedUser)}/roles/${role.id}`,
                                        enabled: e.target.checked,
                                      })
                                    }
                                  />
                                  <strong>{role.name}</strong>
                                  {badge(role)}
                                </label>
                              );
                            }}
                          />
                          <Catalogue<AccessItem>
                            resource="permissions"
                            identity={identity!}
                            title={t("Permissions directes")}
                            render={(permission) =>
                              permissionChoice(permission, "user")
                            }
                          />
                        </>
                      )}
                    </>
                  ) : (
                    <div className="admin-empty">
                      <span className="admin-empty-icon">
                        <UserRound size={24} aria-hidden="true" />
                      </span>
                      <h2>{t("Sélectionnez un utilisateur")}</h2>
                      <p>
                        {t(
                          "Consultez et ajustez ses rôles et permissions directes.",
                        )}
                      </p>
                    </div>
                  )}
                </section>
              </div>
            </>
          )}
          {tab === "roles" && (
            <>
              <div className="admin-workspace">
                <aside>
                  {canRead && (
                    <Catalogue<AccessItem>
                      resource="roles"
                      identity={identity!}
                      title={t("Rôles")}
                      render={(role) => (
                        <button
                          className={`admin-select ${selectedRole === role.id ? "is-selected" : ""}`}
                          aria-pressed={selectedRole === role.id}
                          onClick={() => setSelectedRole(role.id)}
                        >
                          <span className="admin-resource-icon">
                            <Shield size={17} aria-hidden="true" />
                          </span>
                          <span className="admin-identity">
                            <strong>{role.name}</strong>
                            <span>
                              {role.description || t("Aucune description")}
                            </span>
                          </span>
                          {badge(role)}
                          <ChevronRight
                            size={15}
                            className="admin-row-arrow"
                            aria-hidden="true"
                          />
                        </button>
                      )}
                    />
                  )}
                </aside>
                <section
                  className="admin-detail"
                  aria-label={t("Détails du rôle")}
                >
                  {roleAccess.isError ? (
                    <p role="alert">{t("Impossible de charger les droits.")}</p>
                  ) : roleAccess.data ? (
                    <>
                      <MetadataForm
                        key={`${roleAccess.data.id}:${roleAccess.data.description}:${roleAccess.data.is_active}`}
                        item={roleAccess.data}
                        resource="roles"
                        busy={busy}
                        canManage={canManage}
                        run={run}
                      />
                      <Catalogue<AccessItem>
                        resource="permissions"
                        identity={identity!}
                        title={t("Permissions du rôle")}
                        render={(permission) =>
                          permissionChoice(permission, "role")
                        }
                      />
                    </>
                  ) : (
                    <div className="admin-empty">
                      <span className="admin-empty-icon">
                        <Shield size={24} aria-hidden="true" />
                      </span>
                      <h2>{t("Sélectionnez un rôle")}</h2>
                      <p>
                        {t(
                          "Modifiez sa description, son statut et ses permissions.",
                        )}
                      </p>
                    </div>
                  )}
                </section>
              </div>
            </>
          )}
          {tab === "permissions" && (
            <>
              <p className="admin-info">
                {t(
                  "Les permissions correspondent à des contrôles déclarés dans le backend. Leur code est stable ; leur création se fait côté serveur.",
                )}
              </p>
              <div className="admin-workspace">
                <aside>
                  {canRead && (
                    <Catalogue<AccessItem>
                      resource="permissions"
                      identity={identity!}
                      title={t("Permissions")}
                      render={(permission) => (
                        <button
                          className={`admin-select ${selectedPermission?.id === permission.id ? "is-selected" : ""}`}
                          aria-pressed={
                            selectedPermission?.id === permission.id
                          }
                          onClick={() => setSelectedPermission(permission)}
                        >
                          <span className="admin-resource-icon">
                            <KeyRound size={17} aria-hidden="true" />
                          </span>
                          <span className="admin-identity">
                            <strong>{permission.name}</strong>
                            <span>
                              {permission.description ||
                                t("Aucune description")}
                            </span>
                          </span>
                          {badge(permission)}
                          <ChevronRight
                            size={15}
                            className="admin-row-arrow"
                            aria-hidden="true"
                          />
                        </button>
                      )}
                    />
                  )}
                </aside>
                <section
                  className="admin-detail"
                  aria-label={t("Détails de la permission")}
                >
                  {selectedPermission ? (
                    <MetadataForm
                      key={selectedPermission.id}
                      item={selectedPermission}
                      resource="permissions"
                      busy={busy}
                      canManage={canManage}
                      run={run}
                    />
                  ) : (
                    <div className="admin-empty">
                      <span className="admin-empty-icon">
                        <KeyRound size={24} aria-hidden="true" />
                      </span>
                      <h2>{t("Sélectionnez une permission")}</h2>
                      <p>
                        {t(
                          "Consultez son code et modifiez sa description ou son statut.",
                        )}
                      </p>
                    </div>
                  )}
                </section>
              </div>
            </>
          )}
        </div>
      </div>
    </main>
  );
}

/** Le code métier reste immuable ; les attributions survivent à la désactivation. */
function MetadataForm({
  item,
  resource,
  busy,
  canManage,
  run,
}: {
  item: AccessItem;
  resource: "roles" | "permissions";
  busy: boolean;
  canManage: boolean;
  run: (action: AdminAction, form?: HTMLFormElement) => Promise<void>;
}) {
  const { t } = useI18n();
  return (
    <form
      className="admin-card"
      onSubmit={(event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const values = new FormData(form);
        void run(
          {
            kind: "update",
            resource,
            id: item.id,
            data: {
              description: String(values.get("description")),
              is_active: values.get("is_active") === "on",
            },
          },
          form,
        );
      }}
    >
      <h2>{item.name}</h2>
      <p className="field-hint">
        {t(
          "Le code est utilisé dans les contrôles backend et ne peut pas être renommé ici.",
        )}
      </p>
      <Field
        key={`description:${item.id}`}
        id={`description-${resource}`}
        name="description"
        label={t("Description")}
        defaultValue={item.description}
        maxLength={500}
        disabled={!canManage || busy}
      />
      <label className="admin-check">
        <input
          type="checkbox"
          name="is_active"
          defaultChecked={item.is_active}
          disabled={!canManage || busy}
        />
        {t("Actif")}
      </label>
      <p className="field-hint">
        {t(
          "Désactiver suspend les droits sans supprimer les attributions. La réactivation les rétablit. Le super administrateur conserve son accès complet.",
        )}
      </p>
      {canManage && (
        <button className="button button-primary" disabled={busy}>
          {t("Enregistrer les modifications")}
        </button>
      )}
    </form>
  );
}

function NameForm({
  kind,
  title,
  busy,
  run,
}: {
  kind: "role";
  title: string;
  busy: boolean;
  run: (action: AdminAction, form?: HTMLFormElement) => Promise<void>;
}) {
  const { t } = useI18n();
  return (
    <form
      className="admin-card"
      onSubmit={(event) => {
        event.preventDefault();
        const form = event.currentTarget;
        void run({ kind, name: String(new FormData(form).get("name")) }, form);
      }}
    >
      <h2>{title}</h2>
      <Field
        id={`admin-${kind}-name`}
        name="name"
        label={t("Code")}
        required
        pattern="[a-z][a-z0-9_.:\-]{0,99}"
        maxLength={100}
        placeholder="editor"
      />
      <button className="button button-primary" disabled={busy}>
        {t("Créer")}
      </button>
    </form>
  );
}

/** Catalogue borné et recherchable : les droits au-delà de la première page restent accessibles. */
function Catalogue<T extends AdminUser | AccessItem>({
  resource,
  identity,
  title,
  render,
}: {
  resource: "users" | "roles" | "permissions";
  identity: string;
  title: string;
  render: (item: T) => ReactNode;
}) {
  const { t } = useI18n();
  const searchId = useId();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const query = useQuery({
    queryKey: ["admin", identity, resource, { page, q }],
    queryFn: ({ signal }) => adminApi.list<T>(resource, page, q, signal),
    retry: false,
  });
  return (
    <div className="admin-card admin-catalogue">
      <div className="admin-catalogue-title">
        <h2>{title}</h2>
        {query.data && <span className="admin-count">{query.data.total}</span>}
      </div>
      <div className="admin-search">
        <Search size={16} aria-hidden="true" />
        <Field
          id={`admin-search-${resource}-${searchId}`}
          type="search"
          label={t("Rechercher")}
          placeholder={t("Rechercher…")}
          value={q}
          maxLength={100}
          onChange={(event) => {
            setQ(event.target.value);
            setPage(1);
          }}
        />
      </div>
      {query.isError ? (
        <div role="alert">
          <p>{t("Le chargement a échoué.")}</p>
          <button
            className="button button-quiet"
            onClick={() => void query.refetch()}
          >
            {t("Réessayer")}
          </button>
        </div>
      ) : query.isPending ? (
        <p role="status">{t("Chargement…")}</p>
      ) : (
        <>
          <ul className="admin-list">
            {query.data.items.map((item) => (
              <li key={"username" in item ? item.username : item.id}>
                {render(item)}
              </li>
            ))}
          </ul>
          {query.data.total === 0 && <p>{t("Aucun résultat.")}</p>}
          <div className="admin-pagination">
            <button
              className="button button-quiet"
              disabled={page === 1 || query.isFetching}
              onClick={() => setPage(page - 1)}
            >
              {t("Précédent")}
            </button>
            <span>
              {t("Page {{page}} sur {{pages}}", {
                page,
                pages: Math.max(1, query.data.pages),
              })}
            </span>
            <button
              className="button button-quiet"
              disabled={page >= query.data.pages || query.isFetching}
              onClick={() => setPage(page + 1)}
            >
              {t("Suivant")}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
