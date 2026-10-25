# Scripts Memora

Ces scripts servent au fonctionnement, à l’installation et à la validation de l’application. Ils ne sont pas des fichiers de mémoire d’un agent de code et restent versionnés.

## Usage quotidien

Depuis la racine du projet :

```sh
./scripts/memora-start.sh
./scripts/memora-status.sh
./scripts/memora-stop.sh
```

Ces trois commandes délèguent aux scripts `memora-docker-*`. Ceux-ci préparent la configuration privée, vérifient la base PostgreSQL importée, gèrent les cinq services Docker (dont le worker indépendant) et démarrent le compagnon IA natif. `memora-docker-bridge.py`, `memora-inference-host.py` et `memora-postgres-check.py` sont donc nécessaires au fonctionnement actuel sur ce Mac. L’arrêt conserve les volumes et les données.

## Installation et maintenance ponctuelles

| Scripts | Utilité |
|---|---|
| `memora-install.sh`, `memora-env.py` | Préparer les dépendances natives, les modèles et la configuration initiale. |
| `memora-docker-env.py` | Générer la configuration Docker privée sans remplacer les identités applicatives existantes. |
| `memora-import-postgres.py` | Importer les SQLite dans un PostgreSQL vide, avec sauvegardes et comparaison des données. Ne pas relancer pour un démarrage normal. |
| `memora-migrate.py`, `memora-bind-owners.py` | Préparer ou mettre à niveau un ancien stockage SQLite avant import ; également utiles au bootstrap et aux tests. |
| `memora-download-*`, `memora-prepare-*` | Préparer des modèles ou des corpus de test précis ; suivre le guide avant utilisation. |
| `memora-demo.py` | Préparer le compte synthétique de démonstration, avec identifiants privés. |

## Tests et diagnostics

| Scripts | Utilité |
|---|---|
| `memora-test.py` | Exécuter les tests backend avec bases et stockage jetables. |
| `memora-verify-postgres.py` | Tester PostgreSQL et l’import sur deux bases synthétiques temporaires, puis les supprimer. |
| `memora-verify-docker.py` | Vérifier l’application complète dans une stack Docker isolée, avec microphone factice. Option `--ui-audit-only` pour l’audit d’interface. |
| `memora-verify-isolated.py` | Recette native avec SQLite, utile pour comparer et diagnostiquer indépendamment de Docker. |
| `memora-verify-worker-resume.py`, `memora-resilience.py` | Vérifier les reprises et interruptions sur une instance de test dédiée. |
| `memora-mail-capture.py` | Capture SMTP des recettes natives ; le fonctionnement Docker utilise Mailpit. |
| `memora-e2e-api.py`, `memora-qa-*` | Contrôles fonctionnels ou IA ciblés ; certains exigent une instance isolée et des fixtures préparées. |
| `memora-benchmark-*`, `memora-compare-*`, `memora-parakeet-experimental.py` | Mesurer ou comparer les moteurs et leurs limites. Outils optionnels, hors démarrage quotidien. Certains dépendent de résultats locaux ou d’un environnement expérimental à préparer. |

Les scripts de diagnostic ne sont pas tous autonomes : lire leur en-tête et le [guide Memora](../docs/MEMORA.md) avant de les lancer. Les tests utilisent des données synthétiques ; les outils d’analyse privée exigent une autorisation explicite pour l’enregistrement désigné. Aucun microphone réel ni email extérieur ne doit être utilisé pour une recette automatisée.

Les journaux et comptes rendus sont locaux dans `.agents/`, ignorés par Git et créés au besoin par les lanceurs. Les données, modèles, secrets et sauvegardes restent dans `.memora/`, également hors Git.
