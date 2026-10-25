"""Vérifier les métriques HTTP sans réutiliser le registre global d’un autre test."""

import os
from pathlib import Path
import subprocess
import sys
import textwrap


def test_monitoring_excludes_probes_and_supports_slow_requests(tmp_path):
    """Les scrapes et sondes n’alimentent pas le trafic ; le p95 couvre aussi les appels lents."""
    source = textwrap.dedent("""
        from fastapi.testclient import TestClient
        from prometheus_client.parser import text_string_to_metric_families
        from api import createApp, SETTINGS

        config = SETTINGS()
        config.CACHE_ENABLED = False
        app = createApp(config, initialise_database=False)
        with TestClient(app) as client:
            assert client.get('/api/healthcheck/').status_code == 200
            assert client.get('/api/auth/config').status_code == 200
            assert client.get('/metrics').status_code == 200
            response = client.get('/metrics')
            assert response.status_code == 200
            samples = [sample for family in text_string_to_metric_families(response.text) for sample in family.samples]
            requests = [s for s in samples if s.name == 'api_http_requests_total']
            assert requests and sum(s.value for s in requests) == 1
            assert {s.labels['handler'] for s in requests} == {'/api/auth/config'}
            buckets = [s for s in samples if s.name == 'api_http_request_duration_seconds_bucket']
            assert any(float(s.labels['le']) == 10 for s in buckets)
    """)
    environment = {**os.environ, "DATABASE_URL": "sqlite:///:memory:"}
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    result = subprocess.run(
        [sys.executable, "-c", source],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
