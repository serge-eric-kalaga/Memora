"""Protéger les secrets monitoring et le routage des alertes externes."""

import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from init_monitoring import initialize  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "render_alertmanager", ROOT / "monitoring/alertmanager/render.py"
)
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


def values(path):
    return {
        line.split("=", 1)[0]: json.loads(line.split("=", 1)[1])
        for line in path.read_text().splitlines()
        if line and not line.startswith("#")
    }


class MonitoringTests(unittest.TestCase):
    """Vérifier l’idempotence, l’isolation des secrets et les notifications désactivées."""

    def test_preserves_existing_credentials_and_isolates_production(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docker-compose.monitoring.yml").touch()
            dev = root / ".env.grafana"
            dev.write_text(
                'GF_SECURITY_ADMIN_USER="admin"\nGF_SECURITY_ADMIN_PASSWORD="existing-password"\n'
            )
            initialize(root)
            original = dev.read_bytes()
            self.assertEqual(initialize(root), [])
            self.assertEqual(dev.read_bytes(), original)
            self.assertEqual(
                values(dev)["GF_SECURITY_ADMIN_PASSWORD"], "existing-password"
            )
            initialize(root, True)
            prod = values(root / ".env.grafana.prod")
            self.assertNotEqual(
                prod["MYSQL_MONITORING_PASSWORD"],
                values(dev)["MYSQL_MONITORING_PASSWORD"],
            )
            self.assertEqual(prod["MONITORING_ENV"], "prod")
            self.assertEqual(prod["BACKEND_LOG_SOURCE"], "backend_logs")
            self.assertEqual(dev.stat().st_mode & 0o777, 0o600)

    def test_empty_existing_password_is_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docker-compose.monitoring.yml").touch()
            path = root / ".env.grafana"
            original = 'GF_SECURITY_ADMIN_PASSWORD=""\n'
            path.write_text(original)
            with self.assertRaises(ValueError):
                initialize(root)
            self.assertEqual(path.read_text(), original)

    def test_symlink_is_rejected_without_touching_target(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docker-compose.monitoring.yml").touch()
            target = root / "private"
            target.write_text("unchanged")
            (root / ".env.grafana").symlink_to(target)
            with self.assertRaises(ValueError):
                initialize(root)
            self.assertEqual(target.read_text(), "unchanged")

    def test_notifications_are_opt_in_and_exclude_watchdog(self):
        config = renderer.configuration()
        self.assertEqual(config["receivers"], [{"name": "local"}])
        self.assertNotIn("routes", config["route"])
        enabled = renderer.configuration("https://example.com/alerts")
        self.assertEqual(
            enabled["route"]["routes"][0]["matchers"], ['severity=~"warning|critical"']
        )
        for url in (
            "file:///etc/passwd",
            "javascript:alert(1)",
            "ftp://example.com",
            "https://",
        ):
            with self.assertRaises(ValueError):
                renderer.configuration(url)
