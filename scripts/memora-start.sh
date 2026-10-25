#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p .memora/pids agents/logs
python3 scripts/memora-env.py
start() {
  name="$1"
  port="$2"
  shift 2
  if [ -f ".memora/pids/$name" ] && kill -0 "$(cat ".memora/pids/$name")" 2>/dev/null; then
    echo "$name est déjà lancé par Memora."
    return
  fi
  if python3 -c "import socket; s=socket.socket(); s.settimeout(1); result=s.connect_ex(('127.0.0.1',int('$port'))); s.close(); raise SystemExit(0 if result==0 else 1)"; then
    echo "$name : port $port déjà occupé ; aucun second service lancé. Vérifiez scripts/memora-status.sh."
    return
  fi
  python3 scripts/memora-launch.py "$name" "$port" "$@"
}
start mail 1025 backend/.venv/bin/python scripts/memora-mail-capture.py
start backend 8080 ./scripts/memora-backend.sh
start frontend 3000 ./scripts/memora-frontend.sh
printf '%s\n' 'Memora : http://localhost:3000' 'API : http://127.0.0.1:8080/docs' 'Emails locaux : http://127.0.0.1:8025' 'État : scripts/memora-status.sh'
