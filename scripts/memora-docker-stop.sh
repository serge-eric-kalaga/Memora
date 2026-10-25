#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
# stop conserve les volumes, les données PostgreSQL et les emails de test.
docker compose --env-file .memora/docker/compose.env -f docker-compose.yml stop
python3 scripts/memora-docker-bridge.py stop
