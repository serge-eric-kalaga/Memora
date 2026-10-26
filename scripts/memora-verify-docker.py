"""Real Docker/PostgreSQL/browser acceptance on disposable synthetic services only."""

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "backend/.venv/bin/python"
LOGS = ROOT / ".agents/logs"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ui-audit-only", action="store_true")
    parser.add_argument(
        "--diarization-engine",
        choices=["resemblyzer", "ecapa-tdnn", "ecapa-segmented"],
        help="Override only the disposable acceptance stack, never the active app",
    )
    args = parser.parse_args()
    LOGS.mkdir(parents=True, exist_ok=True)
    for port in (13000, 18080, 18025, 15433, 18091):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
    (ROOT / ".memora/qa").mkdir(exist_ok=True)
    folder = Path(
        tempfile.mkdtemp(prefix="memora-isolated-docker-", dir=ROOT / ".memora/qa")
    )
    project = "memora-qa-" + secrets.token_hex(4)
    database = "memora_test_" + secrets.token_hex(8)
    token = secrets.token_urlsafe(48)
    password = secrets.token_urlsafe(32)
    folder.chmod(0o700)
    log = (LOGS / "docker-acceptance-services.log").open("w")
    children = []
    env = {}
    steps = []
    dc = ["docker", "compose", "-p", project, "-f", str(folder / "compose.json")]

    def command(args):
        subprocess.run(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)

    def pass_step(label):
        steps.append(label)
        print("PASS", label, flush=True)

    try:
        config = json.loads(
            subprocess.check_output(
                [
                    "docker",
                    "compose",
                    "--env-file",
                    ".memora/docker/compose.env",
                    "config",
                    "--format",
                    "json",
                ],
                cwd=ROOT,
            )
        )
        config["name"] = project
        config["volumes"] = {"postgres_data": {}, "mail_data": {}}
        config["networks"] = {"default": {}}
        native = {
            k: v
            for k, v in dotenv_values(ROOT / ".memora/backend.env").items()
            if k.startswith("MEMORA_") and v is not None
        }
        native.pop("MEMORA_DATABASE_URL", None)
        native.pop("MEMORA_INFERENCE_URL", None)
        if args.diarization_engine:
            native["MEMORA_DIARIZATION_ENGINE"] = args.diarization_engine
        data = folder / "data"
        data.mkdir()
        photos = folder / "uploads"
        photos.mkdir()
        backend_logs = folder / "logs"
        backend_logs.mkdir()
        native.update(
            APP_NAME="Memora synthetic inference",
            ADMINS_EMAIL="synthetic@example.test",
            SECRET_KEY=secrets.token_urlsafe(48),
            JWT_SECRET=secrets.token_urlsafe(48),
            ALGORITHM="HS256",
            DATABASE_URL="sqlite://",
            MEMORA_DATA_DIR=str(data),
            MEMORA_INFERENCE_TOKEN=token,
            MEMORA_INFERENCE_PORT="18091",
        )
        bridge_env = folder / "native.env"
        bridge_env.write_text(
            "\n".join(f"{k}={json.dumps(v)}" for k, v in native.items()) + "\n"
        )
        bridge_env.chmod(0o600)
        empty_env = folder / "empty.env"
        empty_env.touch(mode=0o600)
        env = dict(native)
        env.update(
            APP_NAME="Memora Docker acceptance",
            ADMINS_EMAIL="synthetic@example.test",
            SECRET_KEY=secrets.token_urlsafe(48),
            JWT_SECRET=secrets.token_urlsafe(48),
            ALGORITHM="HS256",
            DATABASE_URL=f"postgresql+psycopg://memora:{password}@postgres:5432/{database}",
            MEMORA_DATABASE_URL=f"postgresql://memora:{password}@postgres:5432/{database}",
            MEMORA_INFERENCE_URL="http://host.docker.internal:18091",
            MEMORA_OLLAMA_URL="http://host.docker.internal:11434",
            INITIALISE_DATABASE="false",
            MEMORA_DISABLE_WORKER="1",
            MEMORA_DOCKER_LOCAL="1",
            CACHE_ENABLED="false",
            RATE_LIMIT_ENABLED="false",
            EMAIL_VERIFICATION_ENABLED="false",
            EMAIL_HOST="mailpit",
            EMAIL_PORT="1025",
            EMAIL_DOMAIN="localhost",
            MEMORA_SMTP_CAPTURE_ONLY="1",
            MEMORA_SMTP_HOST="mailpit",
            FRONTEND_URL="http://127.0.0.1:13000",
        )
        services = config["services"]
        for service in services.values():
            service.pop("build", None)
            service.pop("restart", None)
            service.pop("env_file", None)
        services["postgres"]["environment"] = {
            "POSTGRES_DB": database,
            "POSTGRES_USER": "memora",
            "POSTGRES_PASSWORD": password,
        }
        services["postgres"]["ports"] = [
            {
                "target": 5432,
                "published": "15433",
                "host_ip": "127.0.0.1",
                "protocol": "tcp",
            }
        ]
        services["postgres"]["healthcheck"]["test"] = [
            "CMD-SHELL",
            f"pg_isready -U memora -d {database}",
        ]
        services["mailpit"]["ports"] = [
            {
                "target": 8025,
                "published": "18025",
                "host_ip": "127.0.0.1",
                "protocol": "tcp",
            }
        ]
        services["backend"]["environment"] = env
        services["backend"]["volumes"] = [
            {"type": "bind", "source": str(data), "target": str(data)},
            {"type": "bind", "source": str(photos), "target": "/app/static/uploads"},
            {"type": "bind", "source": str(backend_logs), "target": "/app/logs"},
        ]
        services["backend"]["ports"] = [
            {
                "target": 8000,
                "published": "18080",
                "host_ip": "127.0.0.1",
                "protocol": "tcp",
            }
        ]
        # Isolate every process: never let the worker inherit production mounts
        # or credentials from the source Compose configuration.
        services["worker"]["environment"] = dict(env)
        services["worker"]["volumes"] = list(services["backend"]["volumes"])
        services["worker"]["ports"] = []
        services["frontend"]["environment"].update(APP_ORIGIN="http://127.0.0.1:13000")
        services["frontend"]["ports"] = [
            {
                "target": 3000,
                "published": "13000",
                "host_ip": "127.0.0.1",
                "protocol": "tcp",
            }
        ]
        (folder / "compose.json").write_text(json.dumps(config))
        (folder / "compose.json").chmod(0o600)
        command(dc + ["up", "-d", "--wait", "postgres", "mailpit"])
        command(
            dc
            + ["run", "--rm", "--no-deps", "backend", "python", "-m", "scripts.migrate"]
        )
        bridge = subprocess.Popen(
            [
                str(PYTHON),
                str(ROOT / "scripts/memora-inference-host.py"),
                "--env-file",
                str(bridge_env),
                "--bridge-env",
                str(empty_env),
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            cwd=ROOT,
            start_new_session=True,
        )
        children.append(bridge)
        with httpx.Client(trust_env=False, timeout=5) as client:
            for _ in range(120):
                if bridge.poll() is not None:
                    raise RuntimeError("Synthetic native inference companion failed")
                try:
                    if client.get("http://127.0.0.1:18091/health").status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.5)
            else:
                raise RuntimeError("Synthetic bridge timeout")
        command(dc + ["up", "-d", "--wait", "backend", "worker", "frontend"])
        pass_step("Docker API/frontend/PostgreSQL/Mailpit isolated and healthy")
        account = {
            "username": "synthetic_docker_qa",
            "password": secrets.token_urlsafe(24),
            "email": "docker@example.org",
        }
        with httpx.Client(
            base_url="http://127.0.0.1:18080", trust_env=False, timeout=20
        ) as client:
            response = client.post(
                "/api/auth/register", json={**account, "telephone": ""}
            )
            print("Synthetic registration HTTP", response.status_code, flush=True)
            response.raise_for_status()
        command(
            dc
            + [
                "exec",
                "-T",
                "backend",
                "python",
                "-c",
                'from api.database import engine,User; from sqlalchemy.orm import Session; db=Session(engine); u=db.query(User).filter_by(username="synthetic_docker_qa").one(); u.is_superuser=True; db.commit(); db.close()',
            ]
        )
        credentials = folder / "credentials.json"
        credentials.write_text(json.dumps(account))
        credentials.chmod(0o600)
        browser_env = dict(os.environ)
        browser_env.update(
            MEMORA_UI_URL="http://127.0.0.1:13000",
            MEMORA_TEST_UI_URL="http://127.0.0.1:13000",
            MEMORA_TEST_API_URL="http://127.0.0.1:18080",
            MEMORA_TEST_CREDENTIALS=str(credentials),
            MEMORA_TEST_ARTIFACT_PREFIX="docker-",
            MEMORA_TEST_ISOLATED="1",
            MEMORA_DIARIZATION_ENGINE=native.get(
                "MEMORA_DIARIZATION_ENGINE", "resemblyzer"
            ),
            MEMORA_FRENCH_ASR_ENGINE=native.get("MEMORA_FRENCH_ASR_ENGINE", ""),
        )
        # The existing audit imports only repository synthetic WAVs, then verifies
        # report/transcript/chat/UI/versions/sharing/downloads through the real BFF.
        browser_scripts = (
            ("memora-ui-audit.mjs", "memora-realtime-browser.mjs")
            if args.ui_audit_only
            else (
                "memora-e2e.mjs",
                "memora-ui-audit.mjs",
                "memora-realtime-browser.mjs",
            )
        )
        for script in browser_scripts:
            with (LOGS / ("docker-" + script + ".log")).open("w") as output:
                subprocess.run(
                    ["node", str(ROOT / "frontend/tests" / script)],
                    env=browser_env,
                    cwd=ROOT / "frontend",
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    check=True,
                )
            pass_step(script)
        with httpx.Client(trust_env=False, timeout=10) as capture:
            for _ in range(40):
                inbox = capture.get("http://127.0.0.1:18025/api/v1/messages")
                inbox.raise_for_status()
                if inbox.json().get("total", 0) > 0:
                    break
                time.sleep(0.5)
            else:
                raise RuntimeError("No synthetic report notification received locally")
        pass_step("Synthetic report email received by local Mailpit")
        command(dc + ["restart", "backend"])
        command(dc + ["up", "-d", "--wait", "backend"])
        with httpx.Client(
            base_url="http://127.0.0.1:18080", trust_env=False, timeout=20
        ) as client:
            login = client.post("/api/auth/login", json=account)
            login.raise_for_status()
            result = client.get(
                "/api/memora/meetings",
                headers={"Authorization": "Bearer " + login.json()["data"]["token"]},
            )
            result.raise_for_status()
            assert result.json(), "Synthetic meetings lost after restart"
        pass_step("PostgreSQL persistence after backend container restart")
        print("SUCCESS", len(steps), "Docker acceptance stages", flush=True)
    finally:
        captured = subprocess.run(
            dc + ["logs", "--no-color", "backend"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        for value in (
            password,
            token,
            env.get("SECRET_KEY", ""),
            env.get("JWT_SECRET", ""),
        ):
            if value:
                captured = captured.replace(value, "[redacted]")
        (LOGS / "docker-acceptance-backend.log").write_text(captured)
        subprocess.run(
            dc + ["down", "--volumes"],
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
        for child in children:
            child.terminate()
            try:
                child.wait(timeout=20)
            except subprocess.TimeoutExpired:
                raise RuntimeError("Synthetic inference process did not stop")
        log.close()
        shutil.rmtree(folder)
        (LOGS / "docker-acceptance-summary.json").write_text(
            json.dumps(
                {"stages": steps, "synthetic_only": True, "main_data_touched": False},
                indent=2,
            )
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("FAILED Docker acceptance:", type(exc).__name__, flush=True)
        sys.exit(1)
