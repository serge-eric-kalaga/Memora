#!/bin/sh
set -eu
for url in http://127.0.0.1:8080/api/healthcheck/ http://127.0.0.1:3000 http://127.0.0.1:8025 http://127.0.0.1:11434/; do
  curl --silent --output /dev/null --max-time 10 --write-out "HTTP %{http_code} $url\n" "$url" || true
done
