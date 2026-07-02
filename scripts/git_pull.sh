#!/usr/bin/env bash
# Sync code from GitHub without getting blocked on generated figure PNGs.
#
# Figures under outputs/figures/ are gitignored and machine-specific.
# Older repo commits tracked PNGs; pulling onto PHI can fail if those files
# were modified locally. This script discards figure diffs, fast-forwards main,
# then reminds you to regenerate figures via the pipeline.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Fetching origin/main"
git fetch origin main

# Drop local diffs to tracked PNGs (legacy) so fast-forward can apply.
if git ls-files outputs/figures/*.png 2>/dev/null | grep -q .; then
  echo "==> Removing legacy tracked figure PNGs from git index (local files kept if present)"
  git ls-files outputs/figures/*.png 2>/dev/null | while IFS= read -r f; do
    git rm --cached -f "$f" 2>/dev/null || true
  done
fi

if ! git diff --quiet -- outputs/figures 2>/dev/null; then
  echo "==> Discarding local git diffs under outputs/figures/"
  git restore --staged --worktree outputs/figures 2>/dev/null \
    || git checkout -- outputs/figures 2>/dev/null \
    || true
fi

echo "==> Fast-forwarding main to origin/main"
git merge --ff-only origin/main

echo ""
echo "Done. Code is synced. Figures are NOT in git — regenerate on this machine:"
echo "  python3 scripts/run_full_pipeline.py          # PHI"
echo "  python3 scripts/run_full_pipeline.py -synthetic  # local de-ID"
