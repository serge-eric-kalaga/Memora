# Interface Memora

Next.js, React et TypeScript. L’interface utilise la même palette pour les pages publiques, les comptes, les réunions, les rapports et le chat, en français et en anglais, avec thèmes clair et sombre.

## Démarrage local

Le démarrage principal utilise Docker Compose depuis la racine du dépôt. La configuration, l’import PostgreSQL et les commandes sont décrits dans le [README du projet](../README.md) et le [guide Memora](../docs/MEMORA.md).

Le frontend conteneurisé accède à l’API par `BACKEND_URL=http://backend:8000`. Aucun secret PostgreSQL, JWT ou IA n’est transmis au frontend. `Dockerfile.prod` construit l’application avec `npm run build:memora`, puis exécute le serveur standalone avec l’utilisateur `node`.

Pour travailler uniquement sur l’interface avec une API locale déjà démarrée :

```bash
npm ci
MEMORA_LOCAL=1 NEXT_PUBLIC_APP_NAME=Memora BACKEND_URL=http://127.0.0.1:8080 npm run dev -- --hostname 127.0.0.1
```

## Vérifications

```bash
npm run lint
npm run typecheck
npm run api:check
npm run test:i18n
npm run test:admin-cache
npm run build:memora
```

Le contrat OpenAPI est maintenu dans `../backend/openapi.json`. Après un changement du contrat, exécuter `npm run api:generate`, puis `npm run api:check` et la vérification TypeScript. Ne pas éditer manuellement `src/lib/api/generated/`.

Les tests HTTP (`test:api`, `test:passwords`, `test:generated-api`) créent et modifient des comptes : utiliser exclusivement des services et une base de test isolés. Les recettes navigateur Memora et les prérequis des modèles locaux sont documentés dans le guide du projet et `../agents/testing.md`. Les tests d’interface simulés ne prouvent pas la qualité de la transcription ou de l’analyse IA.
