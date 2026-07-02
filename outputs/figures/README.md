# Generated figures (local only)

PNG files in this folder are **not** in git. Each machine regenerates them:

```bash
# PHI:
python3 scripts/run_full_pipeline.py

# Local / synthetic:
python3 scripts/run_full_pipeline.py -synthetic
```

If `git pull` complains about files here, run `bash scripts/git_pull.sh` from the repo root.
