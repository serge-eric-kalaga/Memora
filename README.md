# Memora — réunions, transcription et analyse IA locales

Application FastAPI + Next.js : enregistrement/import → transcription → rapport → chat sourcé → partage et exports versionnés.

## Démarrer

```sh
./scripts/memora-start.sh
# équivalent : ./scripts/memora-docker-start.sh
```

Application : [127.0.0.1:3000](http://127.0.0.1:3000) · API : [127.0.0.1:8080/docs](http://127.0.0.1:8080/docs) · Emails capturés : [127.0.0.1:8025](http://127.0.0.1:8025).

```sh
./scripts/memora-status.sh
./scripts/memora-stop.sh
```

Docker Compose exécute PostgreSQL16, FastAPI, Next.js optimisé et Mailpit. Les données PostgreSQL sont persistantes. Sur ce Mac Apple Silicon, MLX/ECAPA restent dans un compagnon natif local protégé ; Ollama existant reste sur l’hôte. Aucun de ces services n’est publié sur Internet.

La première installation et l’import SQLite → PostgreSQL sont décrits dans le [guide Memora](docs/MEMORA.md). Le lancement refuse une installation dont l’import n’a pas été validé. Ne pas supprimer les volumes Docker ni les fichiers privés `.memora/`.

- [Guide, modèles, configuration et limites](docs/MEMORA.md)
- [Tests et preuves](agents/testing.md)
- [Traçabilité des exigences](agents/requirements.md)
- [Mémoire de reprise](agents/README.md)

Les secrets et identifiants de démonstration restent dans `.memora/`, exclus de Git. Le fonctionnement local vérifié ne constitue pas une qualification pour la production.
