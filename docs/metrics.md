# Metric definitions

Definitions follow the metric-extraction workflow used in the GoBug study and
the PyDriller API. PyDriller exposes Lizard-backed source metrics. Null means
unavailable; parse failure is never silently changed to zero.

| Metric family | Granularity | Definition / source | Schema version 1 behavior and limitation |
|---|---|---|---|
| Revision/process | commit | Parent count, merge status, modified Go-file count, insertions, deletions, net lines, total/max/average churn, and aggregate changed-method count | Change totals are scoped to accepted Go files; empty counts remain measured zero |
| File change | file | Change type, additions, deletions, and churn | Describes the accepted file change |
| Size | commit/file/method | Commit aggregates; file NLOC, token count, and method count; method NLOC and token count | When every contributing static measurement is unavailable, the aggregate is null |
| Complexity | commit/file/method | Commit aggregate complexity and file/method cyclomatic complexity | Unavailable Lizard-backed values remain null |
| Interface | method | Parameter count | A measured empty parameter list is zero |
| OS-DMM | commit | PyDriller unit size, complexity, and interfacing scores | May be null when the change cannot be evaluated |
| Go-aware syntax | file | Structs, interfaces, loops, defer, goroutines, channels, error patterns, context use, JSON tags, variadics, and pointer receivers | Syntax-aware counts with explicit parser status |
| Go-aware method syntax | method | Loops, defer, goroutines, channels, and error-condition patterns | The complete declaration is parsed with a synthetic package clause; wrapper syntax is not counted |

`error_handling_count` counts `if` syntax containing the identifier `err`; it
does not prove correct error handling. `channel_count` counts channel type
syntax, not runtime communication. Method identifiers combine path, parsed
name, and start line and are stable only within a run.

Aggregate NLOC, complexity, and token count ignore unavailable component
measurements but remain null when every contributing measurement is
unavailable. This differs from genuinely countable empty sets, such as a
revision with no changed methods, for which zero is meaningful.
