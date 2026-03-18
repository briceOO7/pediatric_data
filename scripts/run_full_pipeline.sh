#!/usr/bin/env bash
# Full pipeline: default PHI/real data; use -synthetic for local de-ID + codebook
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Prefer an already-active venv. Otherwise bootstrap/use project .venv.
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  VENV_DIR="${MEDEVAC_VENV_DIR:-$ROOT/.venv}"
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    echo "==> Creating virtualenv: $VENV_DIR"
    python3 -m venv "$VENV_DIR"
  fi
  # shellcheck disable=SC1090
  source "$VENV_DIR/bin/activate"
fi

echo "==> Python: $(python -V)"
echo "==> Venv: ${VIRTUAL_ENV:-system}"
REQ_STAMP="${VIRTUAL_ENV:-$ROOT/.venv}/.requirements_installed.stamp"
if [[ ! -f "$REQ_STAMP" || requirements.txt -nt "$REQ_STAMP" ]]; then
  echo "==> Installing/updating Python dependencies"
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
  touch "$REQ_STAMP"
else
  echo "==> Requirements already up to date"
fi

exec python scripts/run_full_pipeline.py "$@"
