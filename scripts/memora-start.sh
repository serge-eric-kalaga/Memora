#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
exec ./scripts/memora-docker-start.sh "$@"
