# Troubleshooting

- Exit 3: install the named missing executable.
- Exit 4: run `gh auth status`, then `gh auth login` if necessary.
- Exit 5: inspect disk space, repository reachability, and full-history fetch.
- Exit 6: review `reports/warnings.csv`; extraction did not complete safely.
- Exit 7: inspect `reports/validation.json`; do not use a failed run.
- Existing run: `--resume` reuses only a validated run with unchanged inputs
  or preserves an incomplete attempt before starting cleanly. Use `--force`
  only when intentionally replacing that exact run directory.

Never place tokens in YAML. GoBugMiner relies on the GitHub CLI credential
store.
