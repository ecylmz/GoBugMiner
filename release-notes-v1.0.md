# GoBugMiner 1.0

GoBugMiner 1.0 is the initial public release of the configurable research
software used to construct multi-granularity Go defect datasets.

## Highlights

- Discovers bug-labeled merged pull requests and resolves fix revisions.
- Derives candidate bug-introducing commits with last-modified-line analysis.
- Extracts commit-, file-, and method-level metrics and labels.
- Preserves evidence, candidate relations, measurements, and derived labels as
  separate schema-versioned records.
- Provides strict YAML and CLI configuration, single-project and batch
  execution, provenance, checksums, validation, restart-safe execution, and
  privacy defaults.
- Restricts SZZ candidate evidence to the configured production-Go source
  policy by default, with an explicit `all_changed` comparison mode.
- Preserves GitHub merge evidence separately from the ancestry-verified
  revision used for analysis when merge strategy requires a safe fallback.
- Includes a credential-free deterministic offline fixture and a retained,
  privacy-safe `gin-gonic/gin` validation snapshot.
- Documents the relationship to the peer-reviewed GoBug dataset study while
  excluding the dataset, machine-learning experiments, and
  publication-specific analyses.

## Verification

The release passed Ruff linting and formatting, strict mypy, the full pytest
suite with coverage enforcement, package building, CFF and CodeMeta
validation, two-run offline reproduction, the Linux/macOS Python 3.11--3.13
CI matrix, package checks, and CodeQL.

The retained live snapshot selected
<https://github.com/gin-gonic/gin/pull/11>, resolved one fix revision and one
candidate BIC, produced 2 commit, 7 file, and 92 method metric and label rows,
reported no warnings, and passed validation.

## Known limitations

Version 1.0 supports public Go repositories through GitHub CLI authentication.
Project bug labels are conventions rather than verified truth, candidate BICs
are uncertain under history and refactoring effects, and repository-history
acquisition and analysis can be expensive.
