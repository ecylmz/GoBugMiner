# Data model and labeling

GoBugMiner schema version 1 stores acquired evidence, candidate relations,
measurements, and derived labels as separate records. Derived tables never
overwrite the development evidence from which they were produced.

## Evidence and candidate relations

`raw/pull_requests.jsonl` retains the normalized GitHub pull-request response.
`normalized/pull_requests.csv` separates the GitHub merge SHA, PR head and
base SHAs, evidence fix SHA, analysis fix SHA, resolution policy and reason,
labels, timestamps, and URL.

## Merge and fix-revision resolution

The GitHub merge revision is retained as development evidence when reachable.
If it has analyzable accepted modifications, it is also the analysis fix
revision. A true merge commit may expose no useful modified-file list through
the analysis API; in that case a reachable, analyzable PR head is used only
after Git proves it is an ancestor of the merge evidence. When merge evidence
is unavailable, a reachable PR head must be an ancestor of the acquired
target revision. The evidence and analysis identities, stable policy, and
reason are all persisted. No fallback occurs silently; an unsafe or
unresolvable case produces a structured warning and no fix dataset rows.

`normalized/fix_commits.csv` links each selected pull request to its evidence
and analysis fix revisions. `normalized/bic_candidates.csv` contains the distinct revisions
reported by PyDriller last-modified-line analysis. These are candidate
bug-introducing commits (BICs), not verified bug origins or ground truth.
`normalized/fix_bic_relations.csv` preserves every distinct fix SHA,
candidate SHA, implicated path, and candidate engine. Multiple candidate
relations are retained and deterministically ordered.

## Measurements

The `metrics/commits.csv`, `metrics/files.csv`, and `metrics/methods.csv`
tables are generated after fix and candidate relations have been assembled.
Their `role` is `fix_revision` or `candidate_bic`; it is descriptive linkage
and does not replace the normalized evidence tables. Source exclusions,
metric-extraction exceptions, and parser limitations are retained in
`reports/exclusions.csv`, `reports/warnings.csv`, and explicit
`parse_failure` fields.

## Labeling policy

Label generation occurs after evidence, fix--BIC relations, and metric
extraction:

1. Each candidate BIC revision receives commit label `1`.
2. Each paired fix revision receives commit label `0`, unless the same
   revision is also a candidate BIC, in which case candidate label `1` takes
   precedence.
3. Every extracted file entity inherits its revision label.
4. Every extracted method entity inherits its revision label.

The resulting tables are `labels/commit_labels.csv`,
`labels/file_labels.csv`, and `labels/method_labels.csv`. File and method
records retain their commit SHA and entity identifier, so every label is
traceable to its metric row, revision role, candidate relation, and source
pull request. Validation rejects label rows without corresponding fix/BIC
evidence, file or method metric rows, and revision-label inheritance.

A `0` means “observed fix revision in this paired workflow”; it is the only
negative or non-defective-record policy in schema version 1. It does not prove
that the revision, file, or method is clean. A `1` means “entity extracted
from a revision identified as a candidate by last-modified-line analysis”; it
does not establish causal ground truth. Parse or extraction failures do not
create labels because no corresponding metric entity exists.

File- and method-level labels are revision-associated labels inherited from
the containing revision. They must not be interpreted as proof that a
specific file or method introduced the defect or as fine-grained causal
localization.

## Missing values and versioning

CSV uses UTF-8, LF newlines, stable columns, and sorted rows. JSON uses sorted
keys. Missing static metrics are empty CSV values (`null` in JSON contexts);
zero is emitted only for a measured zero. Parse failures have explicit flags.
Every run records the software version and schema version in its manifest,
summary, and versions record. Consumers should check the schema version before
joining tables.
