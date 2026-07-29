# Contributing

Use a focused branch and include tests, documentation, and provenance-impact
notes with each change. Never add mined private data, access tokens, full study
datasets, or machine-learning experiments.

```bash
uv sync --all-groups
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest --cov=gobugminer --cov-report=term-missing
uv build
./scripts/reproduce_offline.sh
```

Target repositories are untrusted data: changes must not execute their code,
hooks, builds, dependencies, or tests.
