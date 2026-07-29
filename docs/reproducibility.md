# Reproducibility

Offline:

```bash
uv sync --all-groups
./scripts/reproduce_offline.sh
```

The script builds a bounded deterministic Git history, uses controlled PR
evidence, validates two runs, compares canonically ordered outputs byte for
byte, and generates `examples/paper/offline-reproduction-summary.json` from
the executed runs. Stable CSV columns, sorted rows, sorted JSON keys, and
explicit missing values make equivalent research outputs comparable.

## Restart-safe execution

A validated completed run is reused only when its input fingerprint and stage
input chain match. Changed inputs are rejected. An incomplete or failed run is
preserved with a timestamped name before a clean run starts, so partial rows
are never appended to a new result. This is restart-safe execution, not
continuation from the last completed internal stage.

Live:

```bash
gh auth login
uv run gobugminer mine --config examples/configs/single-project.yml
uv run gobugminer validate examples/configs/runs/consul
```

GitHub state can change. A live run therefore captures normalized API
evidence, the target revision, versions, and checksums. A live rerun is not
claimed byte-identical unless it uses the same cached API evidence and
revision.
