#!/usr/bin/env bash
# Full pipeline: default PHI/real data; use -synthetic for local de-ID + codebook
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec python3 scripts/run_full_pipeline.py "$@"
