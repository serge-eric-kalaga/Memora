#!/bin/sh
set -eu
cd "$(dirname "$0")/../frontend"
export MEMORA_LOCAL=1
export BACKEND_URL=http://127.0.0.1:8080
export NEXT_PUBLIC_APP_NAME=Memora
if [ "${MEMORA_MODE:-dev}" = production ]; then
  mkdir -p .next/standalone/.next/static
  cp -R .next/static/. .next/standalone/.next/static/
  if [ -d public ]; then
    mkdir -p .next/standalone/public
    cp -R public/. .next/standalone/public/
  fi
  export HOSTNAME=127.0.0.1
  export PORT=3000
  exec node .next/standalone/server.js
fi
exec node node_modules/next/dist/bin/next dev --webpack --hostname 127.0.0.1 --port 3000
