"""Run acceptance on disposable loopback services; never touch demo databases/PIDs.

Requires the existing backend venv, a completed standalone frontend build and
existing local models. No dependency/model download, public listener or external SMTP.
Ollama inference and model caches are shared: their resource usage is not isolated.
"""

import argparse
import errno
import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "backend/.venv/bin/python"
MODEL_KEYS = (
    "MEMORA_ASR_ENGINE",
    "MEMORA_LIVE_ASR_ENGINE",
    "MEMORA_ASR_MODEL",
    "MEMORA_MODEL",
    "MEMORA_MODEL_DIR",
    "MEMORA_MLX_MODEL_PATH",
    "MEMORA_MLX_FR_MODEL_PATH",
    "MEMORA_FRENCH_ASR_ENGINE",
    "MEMORA_PARAKEET_MODEL_PATH",
    "MEMORA_OLLAMA_KEEP_ALIVE",
    "MEMORA_DIARIZATION_MODEL_DIR",
    "MEMORA_DIARIZATION_ENGINE",
    "MEMORA_ECAPA_MODEL_DIR",
    "MEMORA_DIARIZATION_CPU_THREADS",
)


def local_models():
    # Read only model choices from the local configuration. Never import its keys,
    # databases, SMTP destinations or account credentials into the test instance.
    selected = {
        "MEMORA_ASR_ENGINE": "faster-whisper",
        "MEMORA_ASR_MODEL": "base",
        "MEMORA_MODEL": "gemma4:e4b",
        "MEMORA_MODEL_DIR": str(ROOT / ".memora/models"),
    }
    path = ROOT / ".memora/backend.env"
    if path.is_file():
        for line in path.read_text().splitlines():
            key, separator, value = line.partition("=")
            if separator and key in MODEL_KEYS:
                selected[key] = value.strip().strip("\"'")
    selected.update({key: os.environ[key] for key in MODEL_KEYS if key in os.environ})
    return selected


def ensure_ports_free(ports):
    if len(set(ports)) != len(ports):
        raise RuntimeError("Isolated service ports must be distinct")
    for port in ports:
        if port in (3000, 8080, 1025, 8025, 11434) or not 1024 <= port <= 65535:
            raise RuntimeError(
                "A test port overlaps a protected/main service or is invalid"
            )
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", port))
            except OSError as exc:
                if exc.errno in (errno.EACCES, errno.EPERM):
                    raise RuntimeError(
                        "Loopback binding permission denied by the environment; no service was launched"
                    ) from None
                raise RuntimeError(
                    f"Isolated port {port} is occupied; no service will be stopped"
                ) from None


def apply_asr_policy(env, primary=None, french="inherit"):
    """Explicit test overrides, preserving the independently configured live engine."""
    allowed = {"inherit", "disabled", "mlx-whisper", "parakeet-mlx", "faster-whisper"}
    if french not in allowed:
        raise ValueError("Unknown isolated French ASR override")
    if primary:
        env["MEMORA_ASR_ENGINE"] = primary
    if french != "inherit":
        env["MEMORA_FRENCH_ASR_ENGINE"] = "" if french == "disabled" else french


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-port", type=int, default=18080)
    parser.add_argument("--ui-port", type=int, default=13000)
    parser.add_argument("--smtp-port", type=int, default=11025)
    parser.add_argument("--inbox-port", type=int, default=18025)
    parser.add_argument(
        "--timeout", type=int, default=2400, help="Overall bound in seconds (60..7200)"
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--api-only",
        action="store_true",
        help="Run the real API acceptance only, without browser recipes",
    )
    modes.add_argument(
        "--browser-only",
        action="store_true",
        help="Run browser and UI audit only on new isolated services, without repeating API acceptance",
    )
    modes.add_argument(
        "--ui-audit-only",
        action="store_true",
        help="Run the isolated UI audit only, with synthetic fixture preparation when needed",
    )
    modes.add_argument(
        "--smoke-only",
        action="store_true",
        help="Start isolated services and verify authenticated proxy; skip AI/browser recipes",
    )
    parser.add_argument(
        "--asr-engine", choices=["faster-whisper", "mlx-whisper", "parakeet-mlx"]
    )
    parser.add_argument(
        "--french-asr-engine",
        default="inherit",
        choices=[
            "inherit",
            "disabled",
            "mlx-whisper",
            "parakeet-mlx",
            "faster-whisper",
        ],
        help="Override final explicit-French routing only; disabled clears the optional policy",
    )
    args = parser.parse_args()
    if not 60 <= args.timeout <= 7200:
        parser.error("timeout must be between 60 and 7200 seconds")
    ensure_ports_free([args.api_port, args.ui_port, args.smtp_port, args.inbox_port])
    standalone = ROOT / "frontend/.next/standalone"
    if (
        not (standalone / "server.js").is_file()
        or not (ROOT / "frontend/.next/static").is_dir()
    ):
        raise RuntimeError(
            "Build frontend with npm run build:memora before isolated verification"
        )
    node = shutil.which("node")
    if not node or not PYTHON.is_file():
        raise RuntimeError("Existing Node runtime and backend venv are required")
    logs = ROOT / "agents/logs"
    logs.mkdir(parents=True, exist_ok=True)
    children, handles = [], []
    deadline = time.monotonic() + args.timeout
    started = time.monotonic()
    stages = []
    success = False

    def remaining():
        value = deadline - time.monotonic()
        if value <= 0:
            raise RuntimeError("Overall isolated verification timeout reached")
        return value

    def launch(label, command, env, cwd):
        handle = (logs / ("isolated-" + label + ".log")).open("w")
        handles.append(handle)
        child = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        children.append(child)
        return child

    def stop(child):
        if child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGTERM)
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=3)
            except ProcessLookupError:
                pass

    def step(label, command, env, cwd):
        child = launch(label, command, env, cwd)
        try:
            code = child.wait(timeout=remaining())
        except subprocess.TimeoutExpired:
            stop(child)
            raise RuntimeError(f"{label} exceeded the bounded test duration") from None
        if code:
            raise RuntimeError(
                f"{label} failed; inspect agents/logs/isolated-{label}.log"
            )
        stages.append(label)
        print("PASS", label, flush=True)

    def wait_http(url, process):
        end = time.monotonic() + min(90, remaining())
        with httpx.Client(trust_env=False, timeout=2) as client:
            while time.monotonic() < end:
                if process.poll() is not None:
                    raise RuntimeError(
                        "Isolated service stopped during startup; inspect isolated service logs"
                    )
                try:
                    if client.get(url).status_code < 400:
                        return
                except httpx.HTTPError:
                    pass
                time.sleep(0.25)
        raise RuntimeError("Isolated service readiness timeout")

    temporary = tempfile.TemporaryDirectory(prefix="memora-isolated-")
    try:
        temp = Path(temporary.name)
        os.chmod(temp, 0o700)
        api_url = f"http://127.0.0.1:{args.api_port}"
        ui_url = f"http://127.0.0.1:{args.ui_port}"
        mail_dir = temp / "mail"
        credentials = temp / "credentials.json"
        account = {
            "username": "isolated_" + secrets.token_hex(6),
            "password": secrets.token_urlsafe(32) + "aA1!",
        }
        credentials.write_text(json.dumps(account))
        credentials.chmod(0o600)
        isolation_marker = temp / "isolation-marker.json"
        isolation_marker.write_text(
            json.dumps(
                {"api_url": api_url, "credentials_path": str(credentials.resolve())}
            )
        )
        isolation_marker.chmod(0o600)
        env = {
            key: os.environ[key]
            for key in (
                "PATH",
                "HOME",
                "TMPDIR",
                "LANG",
                "LC_ALL",
                "PLAYWRIGHT_CHROMIUM_EXECUTABLE",
            )
            if key in os.environ
        }
        # Database/inference-service connection secrets are intentionally absent
        # from this allowlist: this verifier owns SQLite stores and native ASR.
        env.update(local_models())
        apply_asr_policy(env, args.asr_engine, args.french_asr_engine)
        env.update(
            APP_NAME="Memora isolated verification",
            ADMINS_EMAIL="synthetic@example.com",
            SECRET_KEY=secrets.token_urlsafe(48),
            JWT_SECRET=secrets.token_urlsafe(48),
            ALGORITHM="HS256",
            DATABASE_URL="sqlite:///" + str(temp / "accounts.sqlite3"),
            INITIALISE_DATABASE="false",
            CACHE_ENABLED="false",
            RATE_LIMIT_ENABLED="false",
            EMAIL_VERIFICATION_ENABLED="false",
            PROFILE_PHOTO_DIR=str(temp / "photos"),
            MEMORA_DATA_DIR=str(temp / "data"),
            MEMORA_OLLAMA_URL="http://127.0.0.1:11434",
            HF_HUB_OFFLINE="1",
            TRANSFORMERS_OFFLINE="1",
            FRONTEND_URL=ui_url,
            EMAIL_HOST="127.0.0.1",
            EMAIL_PORT=str(args.smtp_port),
            EMAIL_DOMAIN="memora@localhost",
            MEMORA_SMTP_HOST="127.0.0.1",
            MEMORA_SMTP_PORT=str(args.smtp_port),
            MEMORA_INBOX_PORT=str(args.inbox_port),
            MEMORA_MAIL_DIR=str(mail_dir),
            MEMORA_TEST_MAIL_DIR=str(mail_dir),
            MEMORA_TEST_API_URL=api_url,
            MEMORA_UI_URL=ui_url,
            MEMORA_TEST_UI_URL=ui_url,
            MEMORA_TEST_CREDENTIALS=str(credentials),
            MEMORA_TEST_ARTIFACT_PREFIX="isolated-",
            MEMORA_TEST_ISOLATED="1",
            MEMORA_TEST_ISOLATION_MARKER=str(isolation_marker),
            MEMORA_TEST_HANDOFF_DIR=str(ROOT / "agents/handoffs"),
            MEMORA_TEST_LOG_DIR=str(logs),
            MEMORA_LOCAL="1",
            NEXT_TELEMETRY_DISABLED="1",
            SESSION_COOKIE_SECURE="false",
            BACKEND_URL=api_url,
            HOSTNAME="127.0.0.1",
            PORT=str(args.ui_port),
            PYTHONPATH=str(ROOT / "backend"),
            MEMORA_EXPECTED_AUTH_DB=str(temp / "accounts.sqlite3"),
        )
        # This code refuses any DB outside this freshly allocated temporary run.
        migrate = (
            "from pathlib import Path; import os; from api.database import Base,engine; from alembic import command; from alembic.config import Config; assert Path(engine.url.database).resolve()==Path(os.environ['MEMORA_EXPECTED_AUTH_DB']).resolve(); c=Config("
            + repr(str(ROOT / "backend/alembic.ini"))
            + ");\nwith engine.begin() as db:\n Base.metadata.create_all(db); c.attributes['connection']=db; command.upgrade(c,'head'); command.check(c)"
        )
        step("migrations", [str(PYTHON), "-c", migrate], env, temp)
        capture = launch(
            "mail",
            [str(PYTHON), str(ROOT / "scripts/memora-mail-capture.py")],
            env,
            temp,
        )
        wait_http(f"http://127.0.0.1:{args.inbox_port}", capture)
        api = launch(
            "backend",
            [
                str(PYTHON),
                "-m",
                "uvicorn",
                "run:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(args.api_port),
                "--no-access-log",
            ],
            env,
            temp,
        )
        wait_http(api_url + "/api/healthcheck/", api)
        with httpx.Client(base_url=api_url, trust_env=False, timeout=20) as client:
            registered = client.post(
                "/api/auth/register",
                json={**account, "email": "isolated-synthetic@example.com"},
            )
            if registered.status_code != 200:
                raise RuntimeError("Isolated synthetic account registration failed")
        promote = "import os,json; from pathlib import Path; from api.database import engine,User; from sqlalchemy.orm import Session; assert Path(engine.url.database).resolve()==Path(os.environ['MEMORA_EXPECTED_AUTH_DB']).resolve(); name=json.loads(Path(os.environ['MEMORA_TEST_CREDENTIALS']).read_text())['username'];\nwith Session(engine) as db:\n user=User.get(db=db,username=name); assert user.account_uid; user.is_superuser=True; db.commit()"
        step("synthetic-admin", [str(PYTHON), "-c", promote], env, temp)
        ui = temp / "frontend"
        shutil.copytree(
            standalone,
            ui,
            ignore=shutil.ignore_patterns("node_modules", ".env*", "logs", "cache"),
        )
        (ui / "node_modules").symlink_to(
            standalone / "node_modules", target_is_directory=True
        )
        shutil.copytree(
            ROOT / "frontend/.next/static", ui / ".next/static", dirs_exist_ok=True
        )
        if (ROOT / "frontend/public").is_dir():
            shutil.copytree(ROOT / "frontend/public", ui / "public", dirs_exist_ok=True)
        frontend = launch("frontend", [node, str(ui / "server.js")], env, ui)
        wait_http(ui_url + "/connexion", frontend)
        # Prove BFF points to the new backend, rather than merely loading HTML.
        with httpx.Client(base_url=ui_url, trust_env=False, timeout=20) as client:
            logged = client.post(
                "/api/auth/login", headers={"Origin": ui_url}, json=account
            )
            if logged.status_code != 200:
                raise RuntimeError("Isolated frontend authenticated proxy failed")
            profile = client.get("/api/session")
            if profile.status_code != 200 or account["username"] not in profile.text:
                raise RuntimeError("Frontend did not return the isolated account")
        stages.append("isolated-authenticated-proxy")
        print("PASS isolated-authenticated-proxy", flush=True)
        if not args.smoke_only:
            if not args.browser_only and not args.ui_audit_only:
                step(
                    "api",
                    [str(PYTHON), str(ROOT / "scripts/memora-e2e-api.py")],
                    env,
                    temp,
                )
            if not args.api_only:
                if not args.ui_audit_only:
                    step(
                        "browser",
                        [node, str(ROOT / "frontend/tests/memora-e2e.mjs")],
                        env,
                        temp,
                    )
                step(
                    "ui-audit",
                    [node, str(ROOT / "frontend/tests/memora-ui-audit.mjs")],
                    env,
                    temp,
                )
        success = True
        print(
            "SUCCESS isolated verification",
            len(stages),
            "stages",
            round(time.monotonic() - started, 2),
            "seconds",
            flush=True,
        )
    finally:
        for child in reversed(children):
            stop(child)
        for handle in handles:
            handle.close()
        temporary.cleanup()
        (logs / "isolated-summary.json").write_text(
            json.dumps(
                {
                    "status": "passed" if success else "failed",
                    "stages_passed": stages,
                    "elapsed_seconds": round(time.monotonic() - started, 2),
                    "ollama_shared": True,
                    "demo_data_touched": False,
                    "smoke_only": args.smoke_only,
                    "api_only": args.api_only,
                    "browser_only": args.browser_only,
                    "ui_audit_only": args.ui_audit_only,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 -- sanitize all boundary errors without credentials
        # Exceptions never include response bodies, env, tokens or credentials.
        print(
            "FAILED",
            str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__,
            flush=True,
        )
        sys.exit(1)
