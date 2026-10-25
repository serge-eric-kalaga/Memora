"use client";
import Link from "next/link";
import { CodeBlock } from "@/components/ui/code-block";
import { ArrowLeft, ArrowUpRight, BookOpen } from "lucide-react";
import { useI18n } from "@/lib/i18n/use-i18n";
import styles from "./documentation.module.css";
import { backendExamples } from "./backend-examples";

const sections = [
  {
    id: "api",
    nav: "Services API",
    title: "Un service par fonctionnalité",
    intro:
      "Les composants passent par un service métier. apiRequest ajoute /api, envoie les cookies et renvoie directement data. Voici le service de session utilisé par le template.",
    label: "frontend/src/features/auth/api.ts",
    code: 'import { apiRequest } from "@/lib/api/client";\nimport type { CurrentUser } from "@/lib/api/types";\n\nexport const authApi = {\n  session: (signal?: AbortSignal) =>\n    apiRequest<CurrentUser | null>("/session", { signal }),\n};',
    note: "Pour une nouvelle ressource, créez un service dans features/<fonctionnalité>/api.ts. Une nouvelle URL doit aussi être autorisée dans le proxy Next.js ; apiRequest ne crée aucune route. Les erreurs sont exposées avec ApiError et son statut HTTP.",
  },
  {
    id: "hooks",
    nav: "Hooks et état",
    title: "Lire et modifier sans recharger la page",
    intro:
      "TanStack Query gère les données reçues de l’API. Réutilisez les hooks du profil pour profiter aussi de la synchronisation entre onglets.",
    label: "frontend/src/features/account/profile-summary.tsx",
    code: '"use client";\nimport { useSession, useUpdateProfile } from "@/features/auth/hooks";\n\nexport function ProfileSummary() {\n  const session = useSession();\n  const update = useUpdateProfile();\n  if (session.isPending) return <p>Chargement…</p>;\n  if (session.isError) return <p>Impossible de charger le profil.</p>;\n  if (!session.data) return <p>Connectez-vous pour continuer.</p>;\n\n  return (\n    <form onSubmit={(event) => {\n      event.preventDefault();\n      const data = new FormData(event.currentTarget);\n      update.mutate({ telephone: String(data.get("telephone")) });\n    }}>\n      <label>Téléphone <input name="telephone" required\n        defaultValue={session.data.telephone ?? ""} /></label>\n      <button disabled={update.isPending}>Enregistrer</button>\n      {update.isError && <p role="alert">{update.error.message}</p>}\n      {update.isSuccess && <p role="status">Profil enregistré.</p>}\n    </form>\n  );\n}',
    note: "useUpdateProfile remplace la session en cache avec setQueryData : il ne recharge pas toutes les listes. Pour vos hooks, utilisez des clés précises, incluez l’identité du compte dans les données privées et transmettez signal aux lectures. Invalidez uniquement les listes réellement affectées. Traduisez les libellés de cet exemple avec useI18n avant de l’intégrer.",
  },
  {
    id: "proxy",
    nav: "Proxy et client généré",
    title: "Relier une nouvelle route au frontend",
    intro:
      "Le navigateur appelle Next.js, puis Next.js appelle FastAPI avec le client généré. Le JWT reste dans un cookie HttpOnly. Le proxy valide les entrées et autorise explicitement chaque route.",
    label: "Commandes · depuis la racine / Commands · from the repository root",
    code: "# Exporter le contrat FastAPI\n(cd backend && uv run --frozen python scripts/export_openapi.py)\n# Générer les types et les fonctions TypeScript\n(cd frontend && npm run api:generate && npm run typecheck)\n# Vérifier que les fichiers générés sont à jour\n(cd backend && uv run --frozen python scripts/export_openapi.py --check)\n(cd frontend && npm run api:check)",
    note: "Ajoutez un response_model et un operation_id stable à la route FastAPI, puis enregistrez son routeur. Après génération, branchez la fonction du SDK dans app/api/[...path]/route.ts, avec requireSession, checkOrigin pour les écritures et une validation Zod adaptée. Suivez les routes existantes ; ne modifiez pas generated/ à la main et ne transformez pas le proxy en relais ouvert.",
  },
  {
    id: "backend",
    nav: "Modules backend",
    title: "Protéger et mettre en cache une route",
    intro:
      "Cet exemple ajoute une route à un routeur FastAPI. Créez d’abord la permission reports.read et attribuez-la au rôle concerné. Déclarer un code de permission seul ne protège aucune route.",
    label: "Exemple · nouveau routeur / Example · new router",
    code: 'from fastapi import APIRouter, Depends\nfrom api.services.authorization import require_permissions\nfrom api.services.cache import cached_response\n\nrouter = APIRouter(prefix="/reports", tags=["REPORTS"])\n\n@router.get("/summary", dependencies=[\n    Depends(require_permissions("reports.read")),\n    Depends(cached_response("reports", ttl=60)),\n])\ndef summary():\n    return {"data": {"total": 0}, "message": "OK"}\n',
    note: 'Enregistrez ensuite ce routeur dans l’application. require_roles protège par rôle ; require_access combine rôles et permissions. Le cache est séparé par utilisateur par défaut. Utilisez Depends(invalidate_cache("reports")) sur les écritures concernées et validez la transaction avant de renvoyer la réponse. Conservez toujours la vérification des droits, même avec du cache.',
  },
  {
    id: "pagination",
    nav: "Listes paginées",
    title: "Partager les mêmes conventions de liste",
    intro:
      "Le frontend et le backend utilisent page, page_size, q, sort et order. Cet extrait backend s’insère dans un service qui dispose déjà de db et params (ListParams).",
    label: "api.services.pagination · api.database.User",
    code: 'from api.database import User\nfrom api.services.pagination import paginate\n\n# Restreindre le query aux données autorisées avant de paginer.\nresult = paginate(\n    db.query(User), params,\n    sort_columns={"id": User.id, "username": User.username},\n    search_columns=(User.username,),\n    tie_breaker=User.id,\n)\n# Sérialiser items avec votre schéma Pydantic public.\n# Retourner result dans data de Response[Page[VotreSchema]].',
    note: "Dans la route, recevez params avec Annotated[ListParams, Query()]. Ne sérialisez jamais directement un modèle utilisateur avec ses champs privés. Côté frontend, utilisez paginatedQuery depuis lib/api/pagination.ts dans useQuery ; updateListQuery remet la page à 1 quand les filtres changent. Les colonnes de tri autorisées restent définies côté serveur.",
  },
  {
    id: "tasks",
    nav: "Tâches en arrière-plan",
    title: "Confier un traitement au worker",
    intro:
      "Les tâches Celery utilisent RabbitMQ pour les messages et Redis pour les résultats. Cette fonction illustre le contrat ; remplacez son corps par votre traitement.",
    label: "backend/api/tasks/example.py · fichier à créer / file to create",
    code: 'from api.services.background import background_task\n\n@background_task(name="example.process")\ndef process_record(record_id: int):\n    # Traitement idempotent : une reprise ne doit pas le dupliquer.\n    return {"record_id": record_id}\n\n# Depuis une route async, après la transaction SQL :\n# task_id = await enqueue_async(process_record, record_id)\n# Import : from api.services.background import enqueue_async',
    note: "Ajoutez api.tasks.example à include dans services/background.py et redémarrez le worker. TransientTaskError déclenche les reprises automatiques limitées ; les autres erreurs échouent normalement. task_status permet de suivre une tâche après vérification des droits du demandeur. Une tâche peut être exécutée plusieurs fois : prévoyez un traitement idempotent.",
  },
  ...backendExamples,
] as const;

/** Exemples fondés sur les services du template ; aucune requête de démonstration. */
export default function Documentation() {
  const { t } = useI18n();
  return (
    <main className={`${styles.root} page-shell`}>
      <Link href="/" className={styles.back}>
        <ArrowLeft size={16} aria-hidden="true" />
        {t("Retour à l’accueil")}
      </Link>
      <header className={styles.hero}>
        <span className={styles.eyebrow}>
          <BookOpen size={16} aria-hidden="true" />
          {t("GUIDE DU TEMPLATE")}
        </span>
        <h1>{t("Ajouter une fonctionnalité, étape par étape.")}</h1>
        <p>
          {t(
            "Voici comment utiliser les services et les modules déjà présents, sans repartir de zéro. Les exemples indiquent les fichiers à consulter et ce qu’il faut adapter à votre projet.",
          )}
        </p>
        <div className={styles.flow}>
          Composant → Hook → Service API → Proxy Next.js → FastAPI
        </div>
      </header>
      <div className={styles.layout}>
        <nav
          className={styles.nav}
          aria-label={t("Sommaire de la documentation")}
        >
          <span>{t("DANS CE GUIDE")}</span>
          {sections.map((section, index) => (
            <a key={section.id} href={`#${section.id}`}>
              <small>0{index + 1}</small>
              {t(section.nav)}
            </a>
          ))}
          <Link href="/#modules">
            {t("Voir les modules inclus")}
            <ArrowUpRight size={14} aria-hidden="true" />
          </Link>
        </nav>
        <div className={styles.content}>
          <aside className={styles.setup}>
            <h2>{t("Avant de brancher ces exemples")}</h2>
            <p>
              {t(
                "Les routes d’exemple ne sont pas ajoutées à l’API par cette documentation. Créez les fichiers indiqués, ajoutez les schémas et permissions utiles, puis enregistrez le routeur dans createApp (backend/api/__init__.py). Tous les fichiers d’environnement restent à la racine ; redémarrez les services concernés après modification.",
              )}
            </p>
            <CodeBlock
              label="backend/api/__init__.py · dans createApp"
              language="python"
              code={
                'from api.views.examples.documents import router as documents_router\n\n# Après la création de app :\napp.include_router(documents_router, prefix="/api", tags=["DOCUMENTS"])\n# Créer aussi les fichiers __init__.py des nouveaux packages Python.'
              }
            />
            <p>
              {t(
                "Ajoutez response_model et operation_id selon le contrat de votre fonctionnalité, régénérez le client, puis autorisez la route dans le proxy Next.js avec sa validation et ses contrôles de session. Les téléchargements binaires doivent conserver leur réponse binaire. Testez avec des services isolés et des fichiers temporaires, jamais avec les données de développement.",
              )}
            </p>
          </aside>
          {sections.map((section, index) => (
            <section
              id={section.id}
              key={section.id}
              aria-labelledby={`${section.id}-title`}
              className={styles.section}
            >
              <span className={styles.eyebrow}>
                0{index + 1} / {t(section.nav)}
              </span>
              <h2 id={`${section.id}-title`}>{t(section.title)}</h2>
              <p>{t(section.intro)}</p>
              <CodeBlock
                code={section.code}
                label={section.label}
                language={
                  section.id === "api"
                    ? "typescript"
                    : section.id === "hooks"
                      ? "tsx"
                      : section.id === "proxy"
                        ? "bash"
                        : "python"
                }
              />
              {"examples" in section &&
                section.examples.map((example) => (
                  <CodeBlock
                    key={example.label}
                    code={example.code}
                    label={example.label}
                    language={example.language}
                  />
                ))}
              <p className={styles.note}>{t(section.note)}</p>
            </section>
          ))}
        </div>
      </div>
    </main>
  );
}
