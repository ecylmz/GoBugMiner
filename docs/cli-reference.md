# CLI reference

- `gobugminer init [--output PATH] [--force]`: write an example YAML file.
- `gobugminer mine --config PATH`: run one project or every project in a batch
  file.
- `gobugminer mine --repo OWNER/NAME --bug-label LABEL ...`: run without a
  configuration file. `--bug-label` is repeatable.
- Mining overrides are `--levels commit,file,method`, `--output`,
  `--cache-dir`, `--resume`, `--force`, `--log-level`,
  `--since`, `--until`, `--max-prs`, `--keep-api-cache`, and
  `--keep-repository-cache`. `--offline` selects controlled local inputs
  declared in YAML. `--max-prs` is sampling/debugging only.
- `gobugminer validate RUN`: verify files, checksums, duplicates, relation
  integrity, and ordering.
- `gobugminer inspect RUN`: print the recorded summary without modifying
  research data.
- `gobugminer schema [--format json|markdown] [--output PATH]`: export schema
  documentation.
- `gobugminer version`: print software, Python, and schema versions.

Exit codes are 0 success, 2 configuration/usage, 3 missing dependency, 4
GitHub/authentication, 5 Git/repository, 6 extraction, 7 validation, 8 partial
or interrupted execution, and 10 unexpected internal error. `--debug` exposes
tracebacks; expected failures otherwise remain concise.

Precedence is CLI override, then YAML, then built-in default. Project-specific
repository, label, and output overrides are rejected for batch files because a
single value would be ambiguous.

`--resume` provides validated completed-run reuse and restart-safe failed-run
preservation. It does not continue within an interrupted stage.
