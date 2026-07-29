# Provenance

Every run records submitted/effective configuration, repository revision,
GoBugMiner/schema versions, Python/OS, Git/GitHub CLI versions, timestamps,
stage state, warnings, exclusions, a manifest, and SHA-256 checksums.

`logs/events.jsonl` contains structured stage, warning, and lifecycle events.
`provenance/stage-inputs.json` stores a run fingerprint over the effective
configuration, exact software/schema versions, resolved repository revision,
selected PR evidence, and dependency lock, plus a hash chain for completed
stages. Restart-safe rerun handling verifies these hashes. A changed input is
rejected; an
unchanged incomplete attempt is moved to a timestamped sibling before a clean,
idempotent restart, preserving the failed evidence.

Commit author emails are never exported. Public commit messages are optional
and disabled by default because they can contain user-generated or personally
identifying text. Local absolute source paths are not written to the
normalized research tables.
