"""Real process-death checkpoint acceptance with synthetic isolated audio only.

Instrumentation pauses at durable boundaries; ASR and reports use actual local models.
Only worker subprocesses created by this invocation are killed/restarted.
"""

import importlib.util
import json
import os
import secrets
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "backend/.venv/bin/python"
LOGS = ROOT / ".agents/logs"


def child():
    from api.memora import ai, store, worker

    mode = os.environ["MEMORA_CHECKPOINT_MODE"]
    directory = Path(os.environ["MEMORA_CHECKPOINT_DIR"])
    if mode == "initialize":
        store.init()
        return
    actual_asr, actual_report, actual_process = ai.transcribe, ai.report, worker.process

    def count(kind):
        with (directory / (kind + ".calls")).open("a") as output:
            output.write("actual local call\n")
            output.flush()
            os.fsync(output.fileno())

    def transcribe(*args, **kwargs):
        count("asr")
        return actual_asr(*args, **kwargs)

    def report(*args, **kwargs):
        if mode == "before-report":
            (directory / "before-report.gate").write_text(
                "report phase has been committed"
            )
            while True:
                time.sleep(0.2)
        count("report")
        return actual_report(*args, **kwargs)

    def process(job):
        actual_process(job)
        if mode == "after-report":
            with store.db() as connection:
                phase = connection.execute(
                    "SELECT phase FROM jobs WHERE id=?", (job["id"],)
                ).fetchone()
            if phase and phase[0] == "complete":
                (directory / "after-report.gate").write_text(
                    "complete phase has been committed; loop has not marked done"
                )
                while True:
                    time.sleep(0.2)

    ai.transcribe, ai.report, worker.process = transcribe, report, process
    thread = worker.start()
    while thread.is_alive():
        time.sleep(0.2)
    raise RuntimeError("Isolated worker thread ended unexpectedly")


def main():
    LOGS.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location(
        "memora_isolated_runner", ROOT / "scripts/memora-verify-isolated.py"
    )
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    children, handles = [], []
    results = []
    deadline = time.monotonic() + 360
    started = time.monotonic()
    success = False

    def stop(process, hard=False):
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL if hard else signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=3)

    temporary = tempfile.TemporaryDirectory(prefix="memora-durable-real-")
    try:
        directory = Path(temporary.name)
        directory.chmod(0o700)
        data = directory / "data"
        database = data / "memora.sqlite3"
        env = {
            key: os.environ[key]
            for key in ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL")
            if key in os.environ
        }
        env.update(runner.local_models())
        env.update(
            APP_NAME="Memora synthetic durable test",
            ADMINS_EMAIL="synthetic@example.com",
            SECRET_KEY=secrets.token_urlsafe(48),
            JWT_SECRET=secrets.token_urlsafe(48),
            ALGORITHM="HS256",
            DATABASE_URL="sqlite:///" + str(directory / "unused-auth.sqlite3"),
            MEMORA_DATA_DIR=str(data),
            MEMORA_ASR_ENGINE="mlx-whisper",
            MEMORA_MODEL="gemma4:e4b",
            MEMORA_OLLAMA_URL="http://127.0.0.1:11434",
            HF_HUB_OFFLINE="1",
            TRANSFORMERS_OFFLINE="1",
            INITIALISE_DATABASE="false",
            PYTHONPATH=str(ROOT / "backend"),
            MEMORA_CHECKPOINT_DIR=str(directory),
        )

        def launch(label, mode):
            handle = (LOGS / ("durable-checkpoint-" + label + ".log")).open("w")
            handles.append(handle)
            process = subprocess.Popen(
                [str(PYTHON), str(Path(__file__).resolve()), "--worker-child"],
                cwd=directory,
                env={**env, "MEMORA_CHECKPOINT_MODE": mode},
                stdout=handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            children.append(process)
            return process

        initialized = launch("initialize", "initialize")
        if initialized.wait(timeout=30):
            raise RuntimeError("Checkpoint test store initialization failed")
        mid = secrets.token_hex(16)
        (data / mid).mkdir()
        shutil.copyfile(
            ROOT / "backend/test/fixtures/memora/mixed-native.wav",
            data / mid / "audio.bin",
        )
        with sqlite3.connect(database) as connection:
            config = json.loads(
                connection.execute("SELECT data FROM config WHERE id=1").fetchone()[0]
            )
            config["email_notifications"] = False
            meeting = {
                "id": mid,
                "owner_uid": "synthetic-durable-" + secrets.token_hex(16),
                "title": "Synthetic durable restart",
                "mode": "import",
                "created": time.time(),
                "updated": time.time(),
                "state": "queued",
                "version": 0,
                "report_version": None,
                "report_id": None,
                "settings": config,
                "duration": 11,
                "audio_expires_at": time.time() + 86400,
                "audio_expired": False,
                "archived": False,
                "email": None,
            }
            connection.execute(
                "INSERT INTO meetings VALUES(?,?,?)", (mid, 1, json.dumps(meeting))
            )

        def calls(kind):
            path = directory / (kind + ".calls")
            return len(path.read_text().splitlines()) if path.exists() else 0

        def snapshot(job_id):
            with sqlite3.connect(database, timeout=3) as connection:
                connection.row_factory = sqlite3.Row
                job = dict(
                    connection.execute(
                        "SELECT * FROM jobs WHERE id=?", (job_id,)
                    ).fetchone()
                )
                meeting = json.loads(
                    connection.execute(
                        "SELECT data FROM meetings WHERE id=?", (mid,)
                    ).fetchone()[0]
                )
                return {
                    "job_state": job["state"],
                    "phase": job["phase"],
                    "source_version": job["source_version"],
                    "result_report_id": job["result_report_id"],
                    "meeting_state": meeting["state"],
                    "version": meeting["version"],
                    "report_version": meeting["report_version"],
                    "transcripts": connection.execute(
                        "SELECT count(*) FROM transcripts WHERE meeting=?", (mid,)
                    ).fetchone()[0],
                    "reports": connection.execute(
                        "SELECT count(*) FROM reports WHERE meeting=?", (mid,)
                    ).fetchone()[0],
                    "notifications": connection.execute(
                        "SELECT count(*) FROM notifications WHERE meeting=?", (mid,)
                    ).fetchone()[0],
                    "asr_calls": calls("asr"),
                    "report_calls": calls("report"),
                }

        def wait_for(process, job_id, predicate, label):
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("Isolated worker exited before " + label)
                value = snapshot(job_id)
                if value["job_state"] == "failed":
                    raise RuntimeError("Actual local processing failed before " + label)
                if predicate(value):
                    return value
                time.sleep(0.1)
            raise RuntimeError("Checkpoint test overall duration exceeded")

        for number, kind in enumerate(("pipeline", "retranscribe"), start=1):
            job_id = secrets.token_hex(16)
            for gate in ("before-report.gate", "after-report.gate"):
                (directory / gate).unlink(missing_ok=True)
            with sqlite3.connect(database) as connection:
                connection.execute(
                    "INSERT INTO jobs(id,meeting,kind,version,state,error,created,finished) VALUES(?,?,?,?,'queued',NULL,?,NULL)",
                    (job_id, mid, kind, number - 1, time.time()),
                )
                meeting = json.loads(
                    connection.execute(
                        "SELECT data FROM meetings WHERE id=?", (mid,)
                    ).fetchone()[0]
                )
                meeting.update(state="queued", active_job_id=job_id)
                connection.execute(
                    "UPDATE meetings SET data=? WHERE id=?", (json.dumps(meeting), mid)
                )
            before = launch(kind + "-before-report", "before-report")
            published = wait_for(
                before,
                job_id,
                lambda value: (directory / "before-report.gate").exists(),
                "durable report phase",
            )
            assert (
                published["phase"] == "report" and published["job_state"] == "running"
            )
            assert (
                published["version"] == number and published["source_version"] == number
            )
            assert (
                published["transcripts"] == number
                and published["reports"] == number - 1
            )
            assert (
                published["asr_calls"] == number
                and published["report_calls"] == number - 1
            )
            stop(before, hard=True)
            print(
                "PASS",
                kind,
                "SIGKILL after actual ASR and durable report checkpoint",
                flush=True,
            )
            resumed = launch(kind + "-after-report", "after-report")
            committed = wait_for(
                resumed,
                job_id,
                lambda value: (directory / "after-report.gate").exists(),
                "durable completed report",
            )
            assert (
                committed["phase"] == "complete" and committed["job_state"] == "running"
            )
            assert (
                committed["meeting_state"] == "ready"
                and committed["report_version"] == number
            )
            assert committed["version"] == number and committed["transcripts"] == number
            assert (
                committed["reports"] == number and committed["notifications"] == number
            )
            assert (
                committed["asr_calls"] == number and committed["report_calls"] == number
            )
            assert committed["result_report_id"]
            stop(resumed, hard=True)
            print(
                "PASS",
                kind,
                "actual report resumed without second ASR; SIGKILL before done",
                flush=True,
            )
            final = launch(kind + "-complete-restart", "normal")
            done = wait_for(
                final,
                job_id,
                lambda value: value["job_state"] == "done",
                "completed idempotent restart",
            )
            assert done["phase"] == "complete" and done["meeting_state"] == "ready"
            assert done["result_report_id"] == committed["result_report_id"]
            assert done["version"] == number and done["transcripts"] == number
            assert done["reports"] == number and done["notifications"] == number
            assert done["asr_calls"] == number and done["report_calls"] == number
            stop(final)
            results.append(
                {
                    "kind": kind,
                    "after_asr_before_kill": published,
                    "after_report_before_second_kill": committed,
                    "after_final_restart": done,
                    "actual_sigkill_count": 2,
                }
            )
            print(
                "PASS",
                kind,
                "completed restart has no duplicate versions/reports/notifications",
                flush=True,
            )
        success = True
        print(
            "SUCCESS actual checkpoint restart pipeline and retranscribe",
            round(time.monotonic() - started, 2),
            "seconds",
            flush=True,
        )
    finally:
        for process in reversed(children):
            stop(process)
        for handle in handles:
            handle.close()
        temporary.cleanup()
        (LOGS / "worker-durable-real.json").write_text(
            json.dumps(
                {
                    "status": "passed" if success else "failed",
                    "synthetic_only": True,
                    "models": {"asr": "mlx-whisper", "report": "gemma4:e4b"},
                    "elapsed_seconds": round(time.monotonic() - started, 2),
                    "results": results,
                    "temporary_data_removed": True,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    try:
        child() if sys.argv[1:] == ["--worker-child"] else main()
    except Exception as exc:  # noqa: BLE001 -- boundary does not expose sources or secrets
        print(
            "FAILED",
            type(exc).__name__,
            str(exc)
            if isinstance(exc, RuntimeError)
            else "isolated checkpoint assertion or setup failed",
            flush=True,
        )
        sys.exit(1)
