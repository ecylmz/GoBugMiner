# Expected offline behavior

The fixture must yield one merged PR, one fix revision, at least one candidate
BIC relation, production-Go commit/file/method metrics, and an exclusion for
`calc_test.go`. `scripts/reproduce_offline.sh` compares all canonical
normalized, metric, and label files between two independent runs because Git
SHA values depend on the fixture's exact deterministic history.
