#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
memora_root="$(pwd)"
# Validate both executable and working directory to avoid stopping a reused PID.
for name in frontend backend mail; do
  pidfile=".memora/pids/$name"
  if [ ! -f "$pidfile" ]; then continue; fi
  pid="$(cat "$pidfile")"
  command="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  if command -v lsof >/dev/null 2>&1; then
    actual_cwd="$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p')"
  else
    actual_cwd="$(readlink "/proc/$pid/cwd" 2>/dev/null || true)"
  fi
  case "$actual_cwd" in
    "$memora_root"|"$memora_root/backend"|"$memora_root/frontend"|"$memora_root/frontend/.next/standalone")
      case "$name:$command" in
        frontend:*next-server*|frontend:*"next dev"*|frontend:*".next/standalone/server.js"*|backend:*"uvicorn run:app"*|mail:*"memora-mail-capture.py"*) kill "$pid" 2>/dev/null || true ;;
        *) echo "$name : commande différente, aucun arrêt effectué." ;;
      esac ;;
    *) echo "$name : PID absent ou répertoire différent, aucun arrêt effectué." ;;
  esac
  rm -f "$pidfile"
done
