# Dependencies

- PyDriller: Git commit traversal, modified-file/method properties, OS-DMM
  metrics, and last-modified-line candidate analysis. PyDriller uses Lizard
  for NLOC, token, cyclomatic-complexity, and method properties.
- tree-sitter and tree-sitter-go: syntax-aware Go construct counts and parse
  status.
- PyYAML: strict configuration loading (strictness is applied by GoBugMiner).
- `git`: local revision/history inspection.
- `gh`: public GitHub API authentication and repository acquisition.
- Ruff, mypy, pytest, coverage, build, and cffconvert: development-only
  quality and metadata checks.

No numerical, notebook, plotting, machine-learning, resampling, tuning, or
statistics dependency is installed.
