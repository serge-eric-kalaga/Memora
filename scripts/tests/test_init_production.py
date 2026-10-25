"""Vérifier l’isolation des secrets et les protections de la configuration de production."""

import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from init_production import main, production_configuration  # noqa: E402


class ProductionTests(unittest.TestCase):
    def test_https_and_independent_secrets(self):
        first = production_configuration("Mon Projet", "mon-projet", "app.example.com", "admin@example.com")
        second = production_configuration("Mon Projet", "mon-projet", "app.example.com", "admin@example.com")
        self.assertEqual(first["APP_ORIGIN"], "https://app.example.com")
        self.assertEqual(first["FRONTEND_URL"], first["APP_ORIGIN"])
        self.assertEqual(first["COMPOSE_PROJECT_NAME"], "mon-projet-prod")
        self.assertEqual(first["INITIALISE_DATABASE"], "false")
        for key in ("SECRET_KEY", "JWT_SECRET", "MYSQL_PASSWORD", "MYSQL_ROOT_PASSWORD"):
            self.assertNotEqual(first[key], second[key])
            self.assertEqual(len(first[key]), 64)
        self.assertNotIn("BACKEND_URL", first)

    def test_invalid_domain_or_email(self):
        for domain in ("https://example.com", "localhost", "a.com/path", "a.com:443", "x\n.com", "*.example.com"):
            with self.assertRaises(ValueError):
                production_configuration("App", "app", domain, "admin@example.com")
        with self.assertRaises(ValueError):
            production_configuration("App", "app", "example.com", "a\nb@example.com")

    def test_create_without_modifying_development_or_existing_production(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "docker-compose.prod.yml").touch()
            (root / ".env.dev").write_text("unchanged")
            args = ["--name", "App", "--domain", "app.example.com", "--admin-email", "admin@example.com", "--directory", temporary]
            output = io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                self.assertEqual(main(args), 0)
                original = (root / ".env.prod").read_bytes()
                self.assertEqual(main(args), 1)
            self.assertEqual((root / ".env.prod").read_bytes(), original)
            self.assertEqual((root / ".env.dev").read_text(), "unchanged")
            self.assertNotIn('SECRET_KEY=', output.getvalue())
            self.assertEqual((root / ".env.prod").stat().st_mode & 0o777, 0o600)
