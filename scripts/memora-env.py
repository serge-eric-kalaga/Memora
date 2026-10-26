"""Generate an isolated local environment; never print secrets."""

import platform
import secrets
import shlex
from pathlib import Path

root = Path(__file__).resolve().parents[1]
data = root / ".memora"
data.mkdir(exist_ok=True)
data.chmod(0o700)
env = data / "backend.env"
if not env.exists():
    native_mlx = platform.system() == "Darwin" and platform.machine() == "arm64"
    asr_engine = "mlx-whisper" if native_mlx else "faster-whisper"
    values = {
        "APP_NAME": "Memora",
        "ADMINS_EMAIL": "admin@example.test",
        "SECRET_KEY": secrets.token_urlsafe(48),
        "JWT_SECRET": secrets.token_urlsafe(48),
        "ALGORITHM": "HS256",
        "DATABASE_URL": "sqlite:///" + str(data / "accounts.sqlite3"),
        "INITIALISE_DATABASE": "true",
        "CACHE_ENABLED": "false",
        "RATE_LIMIT_ENABLED": "false",
        "EMAIL_VERIFICATION_ENABLED": "false",
        "FRONTEND_URL": "http://localhost:3000",
        "EMAIL_HOST": "127.0.0.1",
        "EMAIL_PORT": "1025",
        "EMAIL_DOMAIN": "memora@localhost",
        "MEMORA_DATA_DIR": str(data / "data"),
        "MEMORA_MODEL_DIR": str(data / "models"),
        "MEMORA_OLLAMA_URL": "http://127.0.0.1:11434",
        "MEMORA_MODEL": "gemma4:e4b",
        "MEMORA_DIARIZATION_ENGINE": "ecapa-segmented" if native_mlx else "resemblyzer",
        "MEMORA_ECAPA_MODEL_DIR": str(data / "models/ecapa-voxceleb"),
        "MEMORA_SEGMENTATION_MODEL_DIR": str(data / "models/segmentation-3.0"),
        "MEMORA_DIARIZATION_RECOVERY": "",
        "MEMORA_COMMUNITY_MODEL_DIR": str(data / "models/community-coreml"),
        "MEMORA_COMMUNITY_TOOL_DIR": str(data / "tooling/community-coreml"),
        "MEMORA_ASR_MODEL": "base",
        "MEMORA_ASR_ENGINE": asr_engine,
        "MEMORA_LIVE_ASR_ENGINE": asr_engine,
        "MEMORA_MLX_MODEL_PATH": str(data / "models/mlx-large-v3-turbo"),
        "MEMORA_FRENCH_ASR_ENGINE": "mlx-whisper" if native_mlx else "",
        "MEMORA_PARAKEET_MODEL_PATH": str(data / "models/parakeet-v3")
        if native_mlx
        else "",
    }
    env.write_text("\n".join(f"{k}={shlex.quote(v)}" for k, v in values.items()) + "\n")
    env.chmod(0o600)
print("Configuration locale prête dans .memora/backend.env (non versionnée).")
