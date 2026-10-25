#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p .memora
if command -v uv >/dev/null 2>&1; then
  memora_uv=uv
else
  python3 -m venv .memora/tooling
  .memora/tooling/bin/python -m pip install 'uv==0.13.5'
  memora_uv="$PWD/.memora/tooling/bin/uv"
fi
"$memora_uv" sync --project backend --python 3.12 --frozen
(cd frontend && npm ci)
python3 scripts/memora-env.py
backend/.venv/bin/python scripts/memora-migrate.py
memora_asr_engine=$(backend/.venv/bin/python -c 'from dotenv import dotenv_values; print(dotenv_values(".memora/backend.env").get("MEMORA_ASR_ENGINE", "faster-whisper"))')
memora_french_asr_engine=$(backend/.venv/bin/python -c 'import os; from dotenv import dotenv_values; print(os.environ.get("MEMORA_FRENCH_ASR_ENGINE") or dotenv_values(".memora/backend.env").get("MEMORA_FRENCH_ASR_ENGINE") or "")')
memora_parakeet_path=$(backend/.venv/bin/python -c 'import os; from pathlib import Path; from dotenv import dotenv_values; print(os.environ.get("MEMORA_PARAKEET_MODEL_PATH") or dotenv_values(".memora/backend.env").get("MEMORA_PARAKEET_MODEL_PATH") or Path(".memora/models/parakeet-v3").resolve())')
if [ "$memora_asr_engine" = "parakeet-mlx" ] || [ "$memora_french_asr_engine" = "parakeet-mlx" ]; then
  backend/.venv/bin/python -c 'import platform,sys; sys.exit(0 if sys.platform == "darwin" and platform.machine() == "arm64" else "Parakeet MLX nécessite macOS Apple Silicon.")'
fi
case "$memora_asr_engine" in
  mlx-whisper)
    memora_mlx_path=$(backend/.venv/bin/python -c 'from pathlib import Path; from dotenv import dotenv_values; print(dotenv_values(".memora/backend.env").get("MEMORA_MLX_MODEL_PATH") or Path(".memora/models/mlx-large-v3-turbo").resolve())')
    MEMORA_MLX_MODEL_PATH="$memora_mlx_path" backend/.venv/bin/python scripts/memora-download-mlx.py
    memora_mlx_fr_path=$(backend/.venv/bin/python -c 'import os; from dotenv import dotenv_values; print(os.environ.get("MEMORA_MLX_FR_MODEL_PATH") or dotenv_values(".memora/backend.env").get("MEMORA_MLX_FR_MODEL_PATH") or "")')
    if [ -n "$memora_mlx_fr_path" ]; then
      MEMORA_MLX_MODEL_PATH="$memora_mlx_path" backend/.venv/bin/python scripts/memora-download-large-v3.py --target "$memora_mlx_fr_path"
    fi
    ;;
  parakeet-mlx)
    backend/.venv/bin/python scripts/memora-download-parakeet.py --target "$memora_parakeet_path"
    ;;
  faster-whisper)
    backend/.venv/bin/python -c 'from pathlib import Path; from dotenv import dotenv_values; from faster_whisper import WhisperModel; values=dotenv_values(".memora/backend.env"); model=values.get("MEMORA_ASR_MODEL") or "base"; WhisperModel(model,device="cpu",compute_type="int8",download_root=values.get("MEMORA_MODEL_DIR") or str(Path(".memora/models").resolve())); print("Modèle Faster Whisper configuré prêt.")'
    ;;
  *)
    echo "Moteur ASR non reconnu dans .memora/backend.env." >&2
    exit 1
    ;;
esac

case "$memora_french_asr_engine" in
  "") ;;
  parakeet-mlx)
    if [ "$memora_asr_engine" != "parakeet-mlx" ]; then
      backend/.venv/bin/python scripts/memora-download-parakeet.py --target "$memora_parakeet_path"
    fi
    ;;
  *)
    echo "Moteur français optionnel non reconnu ; aucune substitution automatique." >&2
    exit 1
    ;;
esac

# Optional local speaker clustering is prepared offline from the pinned package.
# It is currently installed/tested only on native Apple Silicon.
if backend/.venv/bin/python -c 'import importlib.util,sys; sys.exit(0 if importlib.util.find_spec("resemblyzer") else 1)'; then
  backend/.venv/bin/python scripts/memora-prepare-diarization.py
fi
