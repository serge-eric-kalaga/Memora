"""Vérifier collecte, dashboards, logs et acheminement des alertes sans afficher de secret."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import time
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def read_credentials(path: Path) -> dict[str, str]:
    """Lire les variables Grafana, citées en JSON par les initialiseurs ou non citées."""
    values = {}
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if value.startswith('"'):
            value = json.loads(value)
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        values[key.strip()] = value
    return values


def get_json(url: str, authorization: str | None = None):
    """Limiter la durée d’une requête et garder les identifiants dans les en-têtes."""
    headers = {"Authorization": authorization} if authorization else {}
    with urlopen(Request(url, headers=headers), timeout=5) as response:
        return json.load(response)


def check(args, authorization: str):
    """Exiger des cibles saines, les séries métiers, les dashboards et des logs récents."""
    targets = get_json(args.prometheus + "/api/v1/targets")["data"]["activeTargets"]
    expected = {
        "backend",
        "http-probes",
        "mysql",
        "redis",
        "prometheus",
        "alertmanager",
        "grafana",
        "loki",
        "alloy",
    }
    jobs = {target["labels"]["job"] for target in targets}
    if not expected <= jobs or any(target["health"] != "up" for target in targets):
        return "collecte des cibles"
    for expression, minimum in (("mysql_up", 1), ("redis_up", 1), ("probe_success", 2)):
        result = get_json(
            args.prometheus + "/api/v1/query?" + urlencode({"query": expression})
        )["data"]["result"]
        if len(result) < minimum or any(
            float(item["value"][1]) != 1 for item in result
        ):
            return "disponibilité MySQL, Redis et sondes HTTP"
    metrics = get_json(
        args.prometheus
        + "/api/v1/query?"
        + urlencode({"query": 'api_http_requests_total{job="backend"}'})
    )
    if not metrics["data"]["result"]:
        return "métriques applicatives"
    search = get_json(args.grafana + "/api/search?type=dash-db", authorization)
    if not {
        "fullstack-overview",
        "fullstack-api",
        "fullstack-data",
        "fullstack-logs",
    } <= {item["uid"] for item in search}:
        return "provisioning des dashboards"
    for uid in ("fullstack-overview", "fullstack-api", "fullstack-data"):
        dashboard = get_json(
            args.grafana + "/api/dashboards/uid/" + uid, authorization
        )["dashboard"]
        for panel in dashboard["panels"]:
            for target in panel.get("targets", []):
                expression = target["expr"].replace("$__rate_interval", "5m")
                query = get_json(
                    args.prometheus
                    + "/api/v1/query?"
                    + urlencode({"query": expression})
                )
                if query.get("status") != "success":
                    return "requêtes des dashboards"
    alerts = get_json(args.alertmanager + "/api/v2/alerts")
    if not any(alert["labels"].get("alertname") == "Watchdog" for alert in alerts):
        return "réception des alertes"
    query = urlencode({"query": 'sum(count_over_time({service="backend"}[10m]))'})
    logs = get_json(
        args.grafana + "/api/datasources/proxy/uid/loki/loki/api/v1/query?" + query,
        authorization,
    )
    if not logs.get("data", {}).get("result"):
        return "collecte des logs backend"
    return None


def main():
    """Attendre un résultat fonctionnel, puis échouer sans exposer les réponses privées."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env.grafana"))
    parser.add_argument("--prometheus", default="http://127.0.0.1:9090")
    parser.add_argument("--grafana", default="http://127.0.0.1:3001")
    parser.add_argument("--alertmanager", default="http://127.0.0.1:9093")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    values = read_credentials(args.env_file)
    credentials = f"{values.get('GF_SECURITY_ADMIN_USER', 'admin')}:{values['GF_SECURITY_ADMIN_PASSWORD']}"
    authorization = "Basic " + base64.b64encode(credentials.encode()).decode()
    deadline = time.monotonic() + args.timeout
    pending = "démarrage des services"
    while time.monotonic() < deadline:
        try:
            pending = check(args, authorization)
            if pending is None:
                print(
                    "Monitoring OK : cibles, métriques, dashboards, logs et Alertmanager."
                )
                return
        except (URLError, OSError, ValueError, KeyError):
            pending = "disponibilité des API de monitoring"
        time.sleep(3)
    raise SystemExit(f"Monitoring non prêt : {pending}.")


if __name__ == "__main__":
    main()
