"""Synthetic lifecycle tests; no native process, network or private data involved."""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "memora-docker-bridge.py"
spec = importlib.util.spec_from_file_location("bridge_lifecycle", SCRIPT)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class BridgeLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        for name, value in {
            "ROOT": root,
            "PRIVATE": root / ".memora/docker",
            "PID": root / ".memora/docker/inference.pid",
            "SCRIPT": root / "scripts/memora-inference-host.py",
        }.items():
            item = patch.object(bridge, name, value)
            item.start()
            self.addCleanup(item.stop)
        self.addCleanup(self.temporary.cleanup)

    def runtime(self):
        python = bridge.ROOT / "backend/.venv/bin/python"
        python.parent.mkdir(parents=True)
        python.touch()
        bridge.SCRIPT.parent.mkdir()
        bridge.SCRIPT.touch()

    def test_default_and_explicit_direct_start(self):
        self.runtime()
        for flags in [[], ["--unmanaged"]]:
            with (
                patch.object(sys, "argv", [str(SCRIPT), "start", *flags]),
                patch.object(bridge, "read_pid", return_value=None),
                patch.object(bridge, "listener", return_value=False),
                patch.object(bridge, "healthy", return_value=True),
                patch.object(bridge.subprocess, "Popen") as popen,
            ):
                popen.return_value.pid = 123
                popen.return_value.poll.return_value = None
                bridge.main()
            popen.assert_called_once()
            self.assertEqual(popen.call_args.args[0], bridge.host_command())
            self.assertEqual(
                (bridge.PRIVATE / "logs/inference.log").stat().st_mode & 0o777, 0o600
            )

    def test_existing_healthy_instance_is_not_restarted(self):
        with (
            patch.object(sys, "argv", [str(SCRIPT), "start"]),
            patch.object(bridge, "read_pid", return_value=123),
            patch.object(bridge, "process_matches", return_value=True),
            patch.object(bridge, "healthy", return_value=True),
            patch.object(bridge.subprocess, "Popen") as popen,
        ):
            bridge.main()
        popen.assert_not_called()

    def test_foreign_port_is_not_killed_or_adopted(self):
        with (
            patch.object(sys, "argv", [str(SCRIPT), "start"]),
            patch.object(bridge, "listener", return_value=True),
            patch.object(os, "kill") as kill,
            patch.object(bridge.subprocess, "Popen") as popen,
        ):
            with self.assertRaisesRegex(SystemExit, "Port8091"):
                bridge.main()
        kill.assert_not_called()
        popen.assert_not_called()

    def test_stop_never_kills_unconfirmed_process(self):
        bridge.PRIVATE.mkdir(parents=True)
        bridge.PID.write_text("123")
        with (
            patch.object(sys, "argv", [str(SCRIPT), "stop"]),
            patch.object(bridge, "process_matches", return_value=False),
            patch.object(bridge, "listener", return_value=True),
            patch.object(os, "kill") as kill,
        ):
            with self.assertRaisesRegex(SystemExit, "Identité"):
                bridge.main()
        kill.assert_not_called()

    def test_process_identity_requires_exact_script_and_project_env(self):
        command = " ".join(bridge.host_command())
        with patch.object(
            bridge.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, stdout=command, stderr=""),
        ):
            self.assertTrue(bridge.process_matches(123))
        with patch.object(
            bridge.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(
                [],
                0,
                stdout=command.replace(
                    str(bridge.SCRIPT), str(bridge.SCRIPT) + ".other"
                ),
                stderr="",
            ),
        ):
            self.assertFalse(bridge.process_matches(123))

    def test_start_failure_never_reports_ready(self):
        self.runtime()
        with (
            patch.object(sys, "argv", [str(SCRIPT), "start"]),
            patch.object(bridge, "listener", return_value=False),
            patch.object(bridge.subprocess, "Popen") as popen,
            patch("builtins.print") as output,
        ):
            popen.return_value.pid = 123
            popen.return_value.poll.return_value = 1
            with self.assertRaisesRegex(SystemExit, "n’a pas démarré"):
                bridge.main()
        output.assert_not_called()
        self.assertFalse(bridge.PID.exists())

    def test_health_requires_authenticated_endpoint(self):
        bridge.PRIVATE.mkdir(parents=True)
        bridge.PRIVATE.joinpath("bridge.env").write_text(
            "MEMORA_INFERENCE_TOKEN=synthetic-token"
        )
        health = BytesIO(b'{"service":"memora-native-inference"}')
        with patch.object(
            bridge.urllib.request,
            "urlopen",
            side_effect=[health, OSError("unavailable")],
        ) as request:
            self.assertFalse(bridge.healthy())
        self.assertEqual(request.call_count, 2)
        self.assertEqual(
            request.call_args.args[0].get_header("Authorization"),
            "Bearer synthetic-token",
        )

    def test_health_rejects_different_service_and_missing_credentials(self):
        self.assertFalse(bridge.healthy())
        bridge.PRIVATE.mkdir(parents=True)
        bridge.PRIVATE.joinpath("bridge.env").write_text(
            "MEMORA_INFERENCE_TOKEN=synthetic-token"
        )
        with patch.object(
            bridge.urllib.request,
            "urlopen",
            return_value=BytesIO(b'{"service":"other"}'),
        ):
            self.assertFalse(bridge.healthy())

    def test_pid_corruption_is_safe(self):
        bridge.PRIVATE.mkdir(parents=True)
        for content in ["broken", "0", "-1", "1"]:
            bridge.PID.write_text(content)
            self.assertIsNone(bridge.read_pid())


if __name__ == "__main__":
    unittest.main()
