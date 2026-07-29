# Candidate BIC semantics

For each safely resolved analysis fix revision, GoBugMiner calls PyDriller's
`get_commits_last_modified_lines` separately for each accepted modification.
The implementation traces deleted/modified lines to prior revisions using Git
history. Each result records analysis fix SHA, candidate SHA, implicated path,
and engine.

## SZZ path scope

`mining.szz_path_scope` defaults to `production_go`. Candidate extraction then
uses the same source classifier and test/generated-file options as metric
extraction. Vendor and non-Go paths are excluded; `_test.go` and generated Go
files participate only when explicitly enabled. Excluded SZZ paths are
reported by category in the manifest and exclusion table.

`all_changed` deliberately submits every changed path with a resolvable path
to last-modified-line analysis. This compatibility/comparison mode can
associate revision labels with evidence outside production Go, so it must be
selected explicitly.

## Merge and fix-revision resolution

The reachable GitHub merge SHA is retained as evidence. If it supplies
analyzable accepted modifications, it is used directly. If a true merge
revision does not, GoBugMiner may analyze the reachable PR head only after Git
verifies its ancestry to the merge. If the merge is unavailable, the head
must be a reachable ancestor of the acquired target revision. Both identities,
the stable resolution policy, and its reason are retained. Unsafe cases emit a
structured warning and do not silently produce empty fix outputs.

These are candidates, not manually verified origins. Blame can be misleading
under refactoring, code movement, formatting, merges, renames, deletions,
generated/binary content, and missing history. Multiple candidates are
retained, duplicate relations are deterministically removed, and exceptions
become structured warnings. The acquired Git history must contain the
revisions and ancestry needed for fix resolution and last-modified-line
analysis; GoBugMiner does not claim that every remote or unreachable object
has been acquired.
