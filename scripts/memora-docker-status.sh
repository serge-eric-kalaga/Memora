#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
docker compose --env-file .memora/docker/compose.env -f docker-compose.yml ps
python3 scripts/memora-docker-bridge.py status
