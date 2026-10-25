# Frontend Next.js

Next.js App Router, TypeScript et Tailwind CSS. Node.js 24 requis (`.nvmrc`).

```bash
npm ci
npm run dev
```

Ouvrir http://localhost:3000. Les commandes npm chargent le fichier `.env.dev` à la racine du projet, sans fichier env dans `frontend/`. FastAPI doit être accessible à `BACKEND_URL` côté serveur (défaut `http://127.0.0.1:8080`). Compose configure `http://backend:80`.

## Parcours

- `/` : accueil et navigation selon la session.
- `/inscription` : création de compte puis confirmation par e-mail si l’option est active ; sinon connexion automatique.
- `/connexion` : authentification avec validation des champs.
- `/profil` : téléphone, photo, dernière connexion, adresse privée de récupération et changement de mot de passe. L’identifiant reste en lecture seule.
- `/mot-de-passe-oublie` : demande de lien par e-mail avec réponse générique.
- `/reinitialiser-mot-de-passe` : définition d’un nouveau mot de passe à partir du lien reçu.
- Navbar : photo du compte, menu accessible au clavier, profil et déconnexion.

Photos JPEG, PNG ou WebP, maximum 5 Mio. FastAPI valide et convertit les images en WebP. La dernière connexion correspond à la dernière authentification réussie, enregistrée en UTC.

## Architecture réutilisable

| Emplacement | Responsabilité |
|---|---|
| `src/lib/api/client.ts` | Transport navigateur commun, JSON/FormData, erreurs et annulation |
| `src/lib/api/server.ts` | Transport serveur vers FastAPI, cookie, origine et limite des corps |
| `src/app/api/[...path]/route.ts` | Routes Next.js explicitement autorisées |
| `src/features/auth/api.ts` | Service métier typé |
| `src/features/auth/hooks.ts` | Requêtes et mutations TanStack Query |
| `src/features/auth/schemas.ts` | Validation Zod partagée entre formulaires et serveur |
| `src/components/providers.tsx` | QueryClient, expiration et synchronisation entre onglets |
| `src/components/ui` | Champs et avatar réutilisables |

Pour une nouvelle fonctionnalité, définir types et service HTTP, autoriser ses routes côté Next.js, puis créer des hooks avec des clés Query dédiées. Invalider les données concernées après mutation. TanStack Query gère les données serveur et React Hook Form l’état des formulaires ; Redux n’est pas nécessaire pour ces usages.

## Session et configuration

Ces variables sont définies dans `.env.dev` à la racine. `APP_ORIGIN=http://localhost:3000` correspond à l’adresse du navigateur en développement ; adapter cette valeur si l’application est ouverte depuis une autre origine.

Le JWT reste dans le cookie `template_session`, HttpOnly et SameSite=Lax ; il n’est transmis ni au JavaScript navigateur ni au stockage local. FastAPI conserve les contrôles d’accès. Les réponses privées utilisent `no-store`, les mutations vérifient `Origin`, et les changements de compte purgent le cache privé et synchronisent les onglets via BroadcastChannel.

- `BACKEND_URL` : URL interne du backend, uniquement côté serveur (`http://127.0.0.1:8080` sur l’hôte ; Compose la remplace par `http://backend:80`).
- `APP_ORIGIN` : origine publique exacte, à définir derrière un proxy, par exemple `https://app.example.com`. Sinon comparaison avec le protocole et le Host de la requête.
- `NEXT_TELEMETRY_DISABLED=1` : désactive la télémétrie Next.js.
- `SESSION_COOKIE_SECURE` : Secure activé par défaut en production. `false` sert uniquement aux essais locaux HTTP d’un build de production.

La déconnexion retire le cookie et le cache privé ; elle ne révoque pas un JWT déjà émis côté API, valable jusqu’à son expiration. Aucun secret ne doit porter le préfixe `NEXT_PUBLIC_`.

Sur une base existante, appliquer les migrations backend avec `alembic upgrade head`, notamment `0002_password_recovery` : voir le README racine.

## Vérifications

```bash
npm run lint
npm run typecheck
npm run build
npm audit
# Frontend et backend démarrés :
npm run test:api
npm run test:passwords
```

Le test HTTP vérifie session, cookie, refus d’origine, profil, photo privée, déconnexion et reconnexion avec un compte temporaire supprimé en fin de test. Adresses personnalisables via `FRONTEND_TEST_URL` et `BACKEND_TEST_URL`.

Le Dockerfile sert au développement : `docker compose up --build frontend` depuis la racine. Après modification des dépendances, synchroniser aussi le volume avec `docker compose run --rm --no-deps frontend npm ci`.

## Dépendance transitive ESLint

Un override ciblé remplace `fast-glob` par `tinyglobby@0.2.17` uniquement dans `@next/eslint-plugin-next`. Cela supprime la chaîne vulnérable `micromatch` / `braces` (GHSA-vfj7-8cjw-p6xm), sans rétrograder Next.js ni désactiver ses règles ESLint. Le plugin utilise uniquement `globSync` avec `onlyDirectories`, pris en charge par cette alternative. Réévaluer cet override lorsqu’un correctif amont sera publié.

## Surveillance en développement

L’import Tailwind de `src/app/globals.css` limite la détection des classes à `src` avec `source("..")`. Conserver cette limite : une détection depuis la racine du frontend inclut des fichiers techniques générés et peut entraîner des recompilations et rechargements répétés. Après modification de ce périmètre, redémarrer le service frontend pour réinitialiser ses dépendances de surveillance.

## Ajouter une fonctionnalité avec les services API et TanStack Query

Le flux de référence est : **composant → hook Query → service métier → client HTTP → route Next.js → FastAPI**. Les composants ne lisent jamais le JWT et ne construisent pas l’URL interne du backend.

Exemple pour un module de projets (les routes `/projects` ci-dessous sont des exemples à implémenter, elles ne sont pas fournies par le template) :

1. Créer les modèles, schémas et routes FastAPI, avec authentification et autorisations sur les projets. Si le schéma change, générer et appliquer une migration Alembic.
2. Ajouter explicitement les branches `GET /api/projects` et `POST /api/projects` à `src/app/api/[...path]/route.ts`. Utiliser `requireSession(request)`, `createBackendClient(token)`, la fonction SDK générée et `backendRequired` pour extraire la réponse côté serveur. La vérification d’origine est déjà appliquée aux écritures ; utiliser `readJson` et valider le corps avant de transmettre la demande. Aucun proxy vers une URL arbitraire.
3. Définir un service typé dans `src/features/projects/api.ts` :

```ts
import { apiRequest } from "@/lib/api/client";
export type Project = { id: number; name: string };
export const projectsApi = {
  list: (signal?: AbortSignal) => apiRequest<Project[]>("/projects", { signal }),
  create: (body: { name: string }) =>
    apiRequest<Project>("/projects", { method: "POST", body }),
};
```

4. Ajouter des hooks dans `src/features/projects/hooks.ts` :

```ts
"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSession } from "@/features/auth/hooks";
import { projectsApi } from "./api";

const projectKeys = { all: ["projects"] as const };
export function useProjects() {
  const session = useSession();
  return useQuery({
    queryKey: [...projectKeys.all, session.data?.username],
    queryFn: ({ signal }) => projectsApi.list(signal),
    enabled: !!session.data,
  });
}
export function useCreateProject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: projectsApi.create,
    onSuccess: () => client.invalidateQueries({ queryKey: projectKeys.all }),
  });
}
```

5. Dans un composant client, appeler `useProjects()` et afficher explicitement chargement, erreur, liste vide et résultat. Pour un formulaire, réutiliser `Field`, React Hook Form et un schéma Zod, puis déclencher `useCreateProject().mutate(values)`. Désactiver la soumission pendant l’écriture ; afficher les erreurs et la confirmation dans un élément accessible (`role="alert"` / `role="status"`).

Les clés Query identifient les données et leurs filtres : ajouter l’identifiant du compte, la pagination et les filtres à la clé si nécessaires. Ne pas copier les résultats Query dans `useState`. Après mutation, invalider les listes concernées ou remplacer un détail avec `setQueryData`. Les changements de compte et la déconnexion purgent déjà les requêtes autres que `session` ; les permissions restent contrôlées côté API.

| Type d’état | Outil et exemple |
|---|---|
| Données serveur | TanStack Query : session, projets, listes paginées |
| Valeurs et erreurs de formulaire | React Hook Form + Zod |
| État local éphémère | React `useState` : ouverture d’un panneau |
| Préférences d’interface | i18next pour la langue, next-themes pour le thème |

Une nouvelle route protégée doit gérer l’absence de session comme `/profil` et continuer à vérifier les droits dans FastAPI. Ne pas utiliser une redirection client comme seule protection.

## Internationalisation (français / anglais)

Le sélecteur de la navbar change la langue sans navigation. `LanguageProvider` crée une instance i18next par arbre React ; le rendu initial est français, puis la préférence du navigateur est restaurée après hydratation. Les routes restent `/connexion`, `/inscription` et `/profil` dans toutes les langues : cette version traduit l’interface, sans routes SEO localisées.

Les catalogues `src/lib/i18n/locales/fr.json` et `en.json` utilisent les phrases françaises comme clés (`keySeparator: false`, `nsSeparator: false`). Conserver exactement les mêmes clés et variables d’interpolation dans chaque langue. Exemple dans un composant client :

```tsx
"use client";
import { useI18n } from "@/lib/i18n/use-i18n";

export function FeatureIntro() {
  const { t } = useI18n();
  return <p>{t("Une nouvelle fonctionnalité à traduire.")}</p>;
}
```

Utiliser `useI18n` dans les composants : cet adaptateur conserve un snapshot français pendant l’hydratation de chaque segment, puis applique la préférence restaurée sans divergence serveur/client. Ajouter le texte aux deux catalogues avant utilisation. Pour une valeur dynamique : `t("Bonjour, {{username}}", { username })`, sans concaténer une phrase à traduire. Traduire également les libellés accessibles et les messages de validation ; les messages Zod restent des clés et sont traduits lors de l’affichage. Les erreurs connues du proxy sont traduites côté interface ; une nouvelle erreur métier doit recevoir une traduction dans les catalogues. Les réponses backend restent dans leur langue d’origine.

Pour ajouter une troisième langue, créer son catalogue, l’enregistrer dans `LanguageProvider`, étendre `supportedLanguages` / `isLanguage`, ajouter l’option dans `Preferences` et adapter le formatage dans `lib/date.ts`. La préférence `fullstack-language-v1` est mémorisée dans localStorage et synchronisée entre onglets. Si le stockage est bloqué, le sélecteur continue de fonctionner dans l’onglet courant. L’attribut HTML `lang`, le titre de l’onglet et les dates suivent la langue sélectionnée ; les métadonnées initiales restent françaises.

## Thèmes clair, sombre et système

Le sélecteur de la navbar utilise next-themes. Le choix est mémorisé dans `fullstack-theme-v1` et synchronisé entre onglets ; par défaut, le thème suit les préférences système. Le script de next-themes applique `data-theme` sur `<html>` avant l’hydratation. `suppressHydrationWarning` est limité à cet élément dont les attributs sont modifiés par les préférences.

Pour un nouveau composant, utiliser les variables `--background`, `--surface`, `--ink`, `--muted`, `--line`, `--green` et `--soft`. Le thème sombre redéfinit cette palette dans `globals.css`. Éviter les fonds ou textes blancs/noirs fixes ; vérifier les états de focus, erreur, désactivation, menu et formulaire dans les deux thèmes. Les préférences d’affichage ne déclenchent pas d’appel API et ne sont pas effacées à la déconnexion.

```bash
npm run test:i18n
```

Ce contrôle vérifie la parité des catalogues, les interpolations et le formatage localisé des dates. Compléter par une recette navigateur pour le changement de langue, le thème système, la persistance au rechargement, l’accessibilité clavier et l’affichage mobile.

Références : [react-i18next](https://react.i18next.com/latest/using-with-hooks), [next-themes](https://github.com/pacocoursey/next-themes).

## Étendre les parcours des identifiants

Les composants `security.tsx` et `recovery.tsx` réutilisent `Field`, `PasswordField`, React Hook Form et les schémas Zod de `features/auth/schemas.ts`. Les confirmations sont validées dans le formulaire et dans le proxy Next.js ; seul le nouveau mot de passe est transmis au backend avec la preuve nécessaire (mot de passe actuel ou jeton). L’inscription conserve l’e-mail facultatif lorsque `EMAIL_VERIFICATION_ENABLED=false` ; il devient obligatoire lorsque la confirmation est activée.

Les services `authApi.changePassword`, `changeEmail`, `forgotPassword` et `resetPassword` passent par `apiRequest`, puis par les branches explicitement autorisées de `/api/[...path]`. Utiliser `useCredentialChange` pour une mutation qui révoque les identifiants : elle purge le cache privé, met la session à `null` et prévient les autres onglets. Son callback facultatif prépare le message de reconnexion avant la purge ; le garde du profil effectue ensuite la redirection. Ne pas stocker les mots de passe ou les jetons dans un état global persistant.

Le lien de récupération utilise `#token=…` pour éviter son passage dans les requêtes de page et les logs d’accès. Le composant le lit une seule fois, efface le fragment de l’entrée d’historique courante puis le transmet uniquement dans le corps du POST de confirmation. Recharger cette page après effacement du fragment demande de rouvrir le lien reçu par e-mail. La page définit une politique `no-referrer` et n’est pas indexée. Un lien invalide, expiré ou déjà utilisé permet de demander un nouveau lien. Aucun login automatique n’est effectué après une réinitialisation.

Les secrets des mutations ont une durée de cache nulle après détachement de leur observateur (`gcTime: 0`) et les champs sont effacés après succès. Le compte courant peut afficher son adresse ; les réponses publiques/listes d’utilisateurs du backend l’excluent. Le changement d’adresse requiert le mot de passe actuel et révoque également les sessions et liens existants.

Les messages et validations de ces parcours sont présents dans les deux catalogues ; `Accept-Language` transmet la langue choisie aux e-mails de récupération et de notification. Les préférences de langue/thème restent conservées lors d’une révocation de session.

`npm run test:passwords` vérifie les routes HTTP de réauthentification, la confirmation, les cookies, l’invalidation d’une ancienne session et la confidentialité de l’adresse. Il utilise un compte temporaire et ne déclenche aucun e-mail réel. Les tests backend capturent les e-mails et couvrent le parcours valide de bout en bout, l’expiration, le rejeu et les requêtes concurrentes. Voir le README racine pour `FRONTEND_URL`, le SMTP et les limites de demandes.

### Vérifier l’e-mail à l’inscription

Activer `EMAIL_VERIFICATION_ENABLED=true` dans **`.env.dev` à la racine**, configurer le SMTP et `FRONTEND_URL`, appliquer `0003_email_verification`, puis recréer le service backend. `authApi.config()` lit le réglage public ; TanStack Query partage cette donnée et le formulaire rend l’e-mail obligatoire. Le backend demeure l’autorité même si un client contourne le formulaire.

`authApi.register()` retourne un profil connecté en mode classique ou `null` avec un statut HTTP `202` si le compte attend une confirmation. `useAuthenticate` purge alors la session et le formulaire affiche `ResendVerification`, également accessible via `/confirmer-email`. `authApi.resendVerification(email, language)` réutilise le proxy et normalise les erreurs. Les réponses de renvoi ne révèlent pas l’existence du compte.

La page `/confirmer-email` lit le fragment du lien, l’efface de l’URL et attend un clic explicite avant `authApi.verifyEmail(token)`. Aucun effet React ne consomme le jeton et aucun secret n’est persisté. La mutation `useCredentialChange` purge les données privées et synchronise les onglets, puis invite à se connecter manuellement. Les textes sont fournis en FR/EN et suivent les thèmes existants. Un changement d’adresse depuis le profil peut exiger une nouvelle confirmation : le message de reconnexion le précise.


### Contrôles automatiques des pull requests

Le workflow racine `.github/workflows/ci.yml` installe les dépendances avec `npm ci`, exécute ESLint, TypeScript et les tests de traduction, puis construit Next.js. Les tests `npm run test:api` et `npm run test:passwords` s’exécutent sur ce **build de production**, avec une API et une base SQLite jetables. Aucune variable locale ni aucun fichier `.env` de sous-répertoire n’est nécessaire. Voir la section intégration continue du README racine pour les contrôles backend, les migrations et la reproduction locale.


## Client API TypeScript généré

Le contrat FastAPI est exporté dans `backend/openapi.json`. **Hey API** (`@hey-api/openapi-ts`, version verrouillée dans `package-lock.json`) génère les modèles TypeScript, les fonctions du SDK et son transport Fetch dans `src/lib/api/generated/`. Le générateur est une dépendance de développement ; le runtime généré est du code source compilé avec Next.js. Aucun service hébergé ni compte Hey API n’est nécessaire.

Le parcours reste :

```text
Composant → hook TanStack Query → authApi / apiRequest
          → proxy Next.js → SDK généré → FastAPI
```

Les composants, les services navigateur de `features/auth/api.ts`, les hooks et les formulaires Zod sont conservés. Le SDK remplace les appels HTTP backend écrits à la main dans le proxy. Les corps, réponses et paramètres de chemin sont désormais inférés depuis les contrats FastAPI. Le type `CurrentUser` est une projection explicite du modèle généré ; `browserUser` sélectionne et normalise les champs exposés au navigateur.

### Régénérer après un changement backend

1. Ajouter/modifier le schéma Pydantic et la route FastAPI. Déclarer un `response_model` précis et un `operation_id` unique et stable (par exemple `listProjects`). Un identifiant stable évite de renommer inutilement les fonctions du SDK lorsqu’on réorganise les fonctions Python. Enregistrer tout nouveau routeur dans l’application.
2. Exporter le contrat puis régénérer le SDK.
3. Adapter les appels signalés par TypeScript, conserver la validation Zod des formulaires/du proxy et ajouter explicitement les nouvelles branches autorisées du proxy.
4. Versionner le contrat et **tout** le dossier généré avec les modifications backend et frontend.

Depuis la racine, avec Docker :

```bash
# Une fois après intégration du montage OpenAPI dans Compose, si le frontend tourne déjà :
docker compose up -d --no-deps frontend

# Après chaque changement de route ou de schéma :
docker compose exec -T backend uv run --frozen python scripts/export_openapi.py
docker compose exec -T frontend npm run api:generate

# Vérifier le résultat :
docker compose exec -T backend uv run --frozen python scripts/export_openapi.py --check
docker compose exec -T frontend npm run api:check
docker compose exec -T frontend npm run typecheck
```

Sans Docker, après `uv sync --frozen` dans `backend/` et `npm ci` dans `frontend/` :

```bash
(cd backend && uv run --frozen python scripts/export_openapi.py)
(cd frontend && npm run api:generate && npm run api:check && npm run typecheck)
```

L’export est déterministe : il utilise une configuration dédiée au processus, un titre fixe et aucun serveur actif. `createApp(..., initialise_database=False)` enregistre les mêmes routes sans appeler l’initialisation SQL ; aucun accès SQL, Redis ou SMTP n’est requis. Il ne charge ni ne crée de fichier `.env`. Le montage en lecture seule `backend/openapi.json` donne au conteneur frontend uniquement le contrat public nécessaire à la génération.

`api:generate` utilise `openapi-ts.config.mjs`. **Ne pas modifier les fichiers générés** : la commande peut remplacer leur contenu. Les corrections appartiennent aux schémas/routes, à la configuration ou aux adaptateurs. Les contraintes comme les longueurs ou formats ne deviennent pas toutes des validations JavaScript : garder Zod côté formulaire/proxy et Pydantic côté API.

### Appeler une nouvelle route depuis le proxy

Après génération d’une route FastAPI avec `operation_id="listProjects"`, sa fonction peut s’utiliser ainsi dans la branche correspondante du proxy :

```ts
import { listProjects } from "@/lib/api/generated/sdk.gen";
import {
  backendRequired,
  createBackendClient,
  jsonData,
  requireSession,
} from "@/lib/api/server";

const token = requireSession(request);
const client = createBackendClient(token);
const projects = backendRequired(await listProjects({ client }));
return jsonData(projects);
```

Le nom exact est celui produit dans `sdk.gen.ts`. Pour une écriture, valider d’abord `readJson(request)` avec le schéma Zod de la fonctionnalité, puis passer le corps typé au SDK. La protection d’origine du proxy reste appliquée. Ensuite, ajouter le service navigateur avec `apiRequest('/projects')` et son hook TanStack Query, comme les modules existants. La génération n’expose jamais automatiquement une route FastAPI dans le proxy.

### Transport et confidentialité

`createBackendClient(token)` crée une instance par requête ; **ne jamais appeler `setConfig` sur le singleton généré pour y mettre un JWT**. Le module `generated-runtime.ts`, importé par le SDK, porte la barrière `server-only`. Ses fonctions ne peuvent donc pas entrer dans un composant client. Les imports `import type` depuis `generated/types.gen.ts` restent utilisables partout, sans runtime ni jeton.

Le transport conserve `BACKEND_URL` côté serveur, `cache: no-store`, le délai de dix secondes et les erreurs normalisées. Les redirections backend sont refusées. `backendData` extrait une enveloppe dont la donnée peut être nulle ; `backendRequired` exige une donnée non nulle, tandis que `backendResult` prend en charge les réponses brutes comme les photos. Les uploads sont bornés avant décodage multipart, puis sérialisés par le SDK. Les cookies HttpOnly, le contrôle d’origine, la liste des routes autorisées et la projection du profil sont conservés.

### Contrôles automatiques

La CI exécute les deux vérifications :

- `python scripts/export_openapi.py --check` détecte une divergence entre les routes/schémas Python et `backend/openapi.json`.
- `npm run api:check` régénère le SDK dans un dossier temporaire et compare la liste et le contenu des fichiers, sans modifier le dossier versionné.

Un oubli de régénération fait échouer la PR. `tests/api-contracts.ts`, inclus dans `npm run typecheck`, vérifie notamment que les champs obligatoires et les secrets `writeOnly` restent présents dans les entrées, que les corps inconnus sont refusés et que les paramètres de chemin sont requis. `npm run test:generated-api` couvre l’intégration HTTP, les erreurs multipart et l’isolation de deux comptes lors de vingt requêtes concurrentes. Les tests de parcours existants continuent à couvrir l’authentification, le profil et les photos.

Les fichiers générés sont exclus d’ESLint, mais restent contrôlés par la génération et TypeScript. L’override npm ciblé de `js-yaml` dans le parseur Hey API corrige sa dépendance vulnérable ; le conserver jusqu’à ce que le parseur dépende lui-même d’une version corrigée. Références : [génération FastAPI](https://fastapi.tiangolo.com/fr/advanced/generate-clients/) et [instances personnalisées Hey API](https://heyapi.dev/docs/openapi/typescript/clients/fetch/#createclient).


## Nom de l’application

`NEXT_PUBLIC_APP_NAME`, défini dans `.env.dev` à la racine, personnalise la navbar, le pied de page, le lien d’accueil accessible et les titres des pages. La valeur par défaut est `Fullstack`. Elle est publique et intégrée au build Next.js ; ne pas y mettre de secret. Relancer le serveur de développement ou reconstruire le frontend après modification.

La commande racine `python3 scripts/init_project.py --name "Ma Boutique"` prépare ce nom ainsi que la configuration backend, les secrets et les paramètres des services. Voir le README racine pour ses options et le démarrage Docker avec `--env-file .env.dev`.

## Production

Le fichier `Dockerfile.prod` construit une image Next.js standalone exécutée avec l’utilisateur `node`. Le déploiement utilise le Compose de production et `.env.prod` à la racine ; voir [Production](../README.md#production). Seul `NEXT_PUBLIC_APP_NAME` est transmis au build. `BACKEND_URL`, `APP_ORIGIN` et les cookies sécurisés sont configurés au démarrage.
