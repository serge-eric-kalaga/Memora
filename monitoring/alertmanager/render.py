"""Construire la configuration privée Alertmanager depuis les variables racine."""

import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit


def configuration(webhook: str = "") -> dict:
    """Activer les notifications warning/critical seulement si une URL est renseignée."""
    receivers = [{"name": "local"}]
    route = {
        "receiver": "local",
        "group_by": ["alertname", "job"],
        "group_wait": "30s",
        "group_interval": "5m",
        "repeat_interval": "4h",
    }
    if webhook:
        url = urlsplit(webhook)
        if url.scheme not in ("http", "https") or not url.hostname:
            raise ValueError("Le webhook doit être une URL HTTP(S) valide.")
        receivers.append(
            {
                "name": "webhook",
                "webhook_configs": [{"url": webhook, "send_resolved": True}],
            }
        )
        route["routes"] = [
            {"receiver": "webhook", "matchers": ['severity=~"warning|critical"']}
        ]
    return {
        "global": {"resolve_timeout": "5m"},
        "route": route,
        "receivers": receivers,
        "inhibit_rules": [
            {
                "source_matchers": ['severity="critical"'],
                "target_matchers": ['severity="warning"'],
                "equal": ["alertname", "job", "instance"],
            }
        ],
    }


def main():
    """Écrire sans afficher le webhook ; autoriser uniquement l’utilisateur Alertmanager."""
    try:
        values = configuration(os.environ.get("ALERTMANAGER_WEBHOOK_URL", ""))
    except ValueError:
        raise SystemExit(
            "Webhook Alertmanager invalide ; aucune configuration écrite."
        ) from None
    path = Path(sys.argv[1])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")
    path.chmod(0o600)
    os.chown(path, 65534, 65534)
    print("Configuration Alertmanager préparée sans affichage du webhook.")


if __name__ == "__main__":
    main()
