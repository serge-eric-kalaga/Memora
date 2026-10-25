#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python3 scripts/memora-env.py
set -a
. ./.memora/backend.env
set +a
cd backend
exec .venv/bin/python -m uvicorn run:app --host 127.0.0.1 --port 8080 --no-access-log
