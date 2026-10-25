#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python3 scripts/memora-docker-env.py
if [ ! -f .memora/docker/import-complete.json ]; then
  echo 'Import PostgreSQL non validé. Importer et vérifier les données avant le démarrage de l’application.' >&2
  exit 1
fi
docker compose --env-file .memora/docker/compose.env -f docker-compose.yml config --quiet
docker compose --env-file .memora/docker/compose.env -f docker-compose.yml up -d --wait postgres
backend/.venv/bin/python scripts/memora-postgres-check.py
python3 scripts/memora-docker-bridge.py start
docker compose --env-file .memora/docker/compose.env -f docker-compose.yml up -d --wait "$@"
printf '%s\n' 'Memora : http://127.0.0.1:3000' 'API : http://127.0.0.1:8080/docs' 'Emails locaux : http://127.0.0.1:8025'
