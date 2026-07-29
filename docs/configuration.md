# Configuration

The schema is strict: unknown fields fail. Repository identifiers must be
`owner/name`; bug labels cannot be empty; dates are ISO 8601; paths containing
`..` are rejected. The exact submitted and effective YAML files are copied to
each run.

`selection.max_prs` is only for bounded sampling/debugging and does not create
a complete repository dataset. `privacy.include_author_emails` defaults to
false and is not implemented as an export path. `offline` accepts a
local Git fixture and controlled PR response. See `examples/configs` and the
offline fixture template.

`mining.szz_path_scope` accepts `production_go` (the default) or
`all_changed`. The default submits only paths accepted by the shared Go source
policy to candidate extraction. `mining.exclude_tests: false` enables
`_test.go` paths, and `mining.include_generated_files: true` enables generated
Go paths. `all_changed` intentionally analyzes every changed path with a
resolvable path and records that broader methodological choice in provenance.

Batch YAML replaces `project` with a non-empty `projects` list. Selection,
mining, cache, execution, and privacy sections are shared. Each project may
set `repository`, `bug_labels`, an optional `output_dir`, and optional offline
paths. If omitted, its output is `<paths.output_dir>/<owner>__<name>`. Resolved
output directories must be unique.

CLI values override YAML; YAML overrides built-in defaults. Each batch run
retains the complete submitted batch file and writes its project-specific
effective configuration.
