"""Vérifier les configurations et leur protection sur des copies temporaires du template."""

import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "init_project.py"
spec = importlib.util.spec_from_file_location("init_project", SCRIPT)
initializer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(initializer)


def read_env(path):
    """Lire les valeurs JSON citées produites par l’outil, sans dépendance dotenv."""
    return {
        key: json.loads(value)
        for line in path.read_text().splitlines()
        if line and not line.startswith("#")
        for key, value in [line.split("=", 1)]
    }


class InitProjectTests(unittest.TestCase):
    """Exécutions indépendantes ; aucune configuration du dépôt de travail n’est touchée."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "backend").mkdir()
        (self.root / "frontend").mkdir()
        (self.root / "docker-compose.yml").touch()

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--directory", str(self.root), *args],
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_creates_private_coherent_configs_without_printing_secrets(self):
        result = self.run_cli(
            "--name", "Ma Boutique", "--admin-email", "admin@example.com"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        dev = read_env(self.root / ".env.dev")
        tests = read_env(self.root / ".env.test")
        grafana = read_env(self.root / ".env.grafana")
        self.assertEqual(dev["APP_NAME"], "Ma Boutique")
        self.assertEqual(dev["NEXT_PUBLIC_APP_NAME"], "Ma Boutique")
        self.assertEqual(dev["COMPOSE_PROJECT_NAME"], "ma-boutique")
        self.assertEqual(dev["MYSQL_DATABASE"], "ma_boutique")
        self.assertIn(
            f":{dev['MYSQL_PASSWORD']}@mysql:3306/ma_boutique", dev["DATABASE_URL"]
        )
        self.assertNotEqual(grafana["MYSQL_MONITORING_PASSWORD"], dev["MYSQL_PASSWORD"])
        self.assertEqual(tests["DATABASE_URL"], "sqlite:///.test.db")
        self.assertEqual(tests["CACHE_ENABLED"], "false")
        self.assertEqual(dev["EMAIL_VERIFICATION_ENABLED"], "false")
        values = [
            dev[key]
            for key in (
                "SECRET_KEY",
                "JWT_SECRET",
                "MYSQL_ROOT_PASSWORD",
                "MYSQL_PASSWORD",
            )
        ]
        values += [
            tests["SECRET_KEY"],
            tests["JWT_SECRET"],
            grafana["GF_SECURITY_ADMIN_PASSWORD"],
            grafana["MYSQL_MONITORING_PASSWORD"],
        ]
        self.assertEqual(len(values), len(set(values)))
        for value in values:
            self.assertRegex(value, r"^[0-9a-f]{64}$")
            self.assertNotIn(value, result.stdout + result.stderr)
        for name in initializer.ENV_FILES:
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE((self.root / name).stat().st_mode), 0o600)
        self.assertFalse(list((self.root / "backend").glob(".env*")))
        self.assertFalse(list((self.root / "frontend").glob(".env*")))

    def test_rerun_refuses_without_rotating_secrets(self):
        self.assertEqual(self.run_cli("--name", "Example").returncode, 0)
        before = {
            name: (self.root / name).read_bytes() for name in initializer.ENV_FILES
        }
        result = self.run_cli("--name", "Another Project")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(
            before,
            {name: (self.root / name).read_bytes() for name in initializer.ENV_FILES},
        )

    def test_one_existing_file_prevents_any_creation(self):
        (self.root / ".env.test").write_text("preserve")
        self.assertNotEqual(self.run_cli("--name", "Example").returncode, 0)
        self.assertFalse((self.root / ".env.dev").exists())
        self.assertFalse((self.root / ".env.grafana").exists())
        self.assertEqual((self.root / ".env.test").read_text(), "preserve")

    def test_existing_broken_symlink_is_not_followed(self):
        if not hasattr(os, "symlink"):
            self.skipTest("Symlinks non disponibles")
        (self.root / ".env.dev").symlink_to(self.root / "missing")
        self.assertNotEqual(self.run_cli("--name", "Example").returncode, 0)
        self.assertFalse((self.root / "missing").exists())
        self.assertTrue((self.root / ".env.dev").is_symlink())

    def test_dry_run_does_not_generate_or_write_secrets(self):
        with patch.object(
            initializer.secrets,
            "token_hex",
            side_effect=AssertionError("Aucun secret attendu"),
        ):
            self.assertEqual(
                initializer.main(
                    ["--directory", str(self.root), "--name", "Example", "--dry-run"]
                ),
                0,
            )
        self.assertFalse(list(self.root.glob(".env*")))

    def test_normalization_and_explicit_slug(self):
        self.assertEqual(
            initializer.project_identity("  École & Projets  "),
            ("École & Projets", "ecole-projets"),
        )
        self.assertEqual(
            initializer.project_identity("应用", "my-app"), ("应用", "my-app")
        )
        for slug in ("../bad", "Bad", "1bad", "a" * 49):
            with self.assertRaises(ValueError):
                initializer.project_identity("Example", slug)

    def test_invalid_inputs_do_not_write_files(self):
        for arguments in (
            ("--name", "${SECRET}"),
            ("--name", "bad\nname"),
            ("--name", "Example", "--admin-email", "bad\n@example.com"),
            ("--name", ""),
            (),
        ):
            self.assertNotEqual(self.run_cli(*arguments).returncode, 0)
        self.assertFalse(list(self.root.glob(".env*")))

    def test_invalid_directory_is_rejected(self):
        (self.root / "docker-compose.yml").unlink()
        self.assertNotEqual(self.run_cli("--name", "Example").returncode, 0)
        self.assertFalse(list(self.root.glob(".env*")))

    def test_write_failure_rolls_back_only_new_files(self):
        original = os.open
        calls = 0

        def fail_last(path, *args):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise PermissionError("simulated")
            return original(path, *args)

        configs = initializer.configurations(
            self.root, "Example", "example", "admin@example.com"
        )
        with patch.object(initializer.os, "open", side_effect=fail_last):
            with self.assertRaises(PermissionError):
                initializer.write_configurations(self.root, configs)
        self.assertFalse(list(self.root.glob(".env*")))


if __name__ == "__main__":
    unittest.main()
