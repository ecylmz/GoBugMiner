# Validation

Validation checks the required run layout, SHA-256 content checksums, duplicate
fix/BIC keys, foreign-key membership, canonical relation order, revision-role
label policy, inherited file/method labels, and exact label-to-metric key
correspondence. It exits nonzero on any failure.

The pipeline writes normalized records, metrics, labels, provenance, and the
final summary before regenerating checksums and running final validation. The
validation report is then written. `RUN_COMPLETE` is created only after that
final validation succeeds; a failed final validation leaves no marker.

`RUN_COMPLETE`, `provenance/checksums.sha256`, and
`reports/validation.json` are excluded from the checksum list. The checksum
file cannot checksum itself, the completion marker is post-validation state,
and excluding the report avoids a self-referential report/checksum cycle.
Every other required output is checksum-covered.

Validation establishes structural integrity; it does not establish that a
GitHub label denotes a true bug or that an SZZ candidate is the actual
bug-introducing revision.
