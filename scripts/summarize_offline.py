from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

DEPENDENCIES = ("pydriller", "PyYAML", "tree-sitter", "tree-sitter-go")
CANONICAL_OUTPUTS = (
    "normalized/pull_requests.csv",
    "normalized/fix_commits.csv",
    "normalized/bic_candidates.csv",
    "normalized/fix_bic_relations.csv",
    "metrics/commits.csv",
    "metrics/files.csv",
    "metrics/methods.csv",
    "labels/commit_labels.csv",
    "labels/file_labels.csv",
    "labels/method_labels.csv",
)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected an object in {path}")
    return value


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: summarize_offline.py RUN_1 RUN_2 OUTPUT")
    first, second, output = (Path(value).resolve() for value in sys.argv[1:])
    first_summary = _json(first / "reports/summary.json")
    second_summary = _json(second / "reports/summary.json")
    first_validation = _json(first / "reports/validation.json")
    second_validation = _json(second / "reports/validation.json")
    first_manifest = _json(first / "provenance/manifest.json")
    second_manifest = _json(second / "provenance/manifest.json")
    if first_summary != second_summary:
        raise ValueError("offline run summaries differ")
    for key in (
        "szz_path_scope",
        "source_filter_policy",
        "excluded_szz_paths_by_category",
    ):
        if first_manifest.get(key) != second_manifest.get(key):
            raise ValueError(f"offline manifest field differs: {key}")
    for relative in CANONICAL_OUTPUTS:
        if (first / relative).read_bytes() != (second / relative).read_bytes():
            raise ValueError(f"canonical output differs: {relative}")
    counts = {key: value for key, value in first_summary.items() if key.endswith("_count")}
    result = {
        "software_version": first_summary["software_version"],
        "schema_version": first_summary["schema_version"],
        "run_count": 2,
        "output_counts": counts,
        "checksum_comparison": {
            "canonical_outputs_identical": True,
            "files_compared": list(CANONICAL_OUTPUTS),
        },
        "validation_result": {
            "run_1_valid": first_validation.get("valid") is True,
            "run_2_valid": second_validation.get("valid") is True,
        },
        "szz_path_scope": first_manifest["szz_path_scope"],
        "source_filter_policy": first_manifest["source_filter_policy"],
        "excluded_szz_paths_by_category": first_manifest["excluded_szz_paths_by_category"],
        "fix_revision_resolutions": first_manifest["fix_revision_resolutions"],
        "execution_date": datetime.now(UTC).date().isoformat(),
        "dependency_versions": {name: version(name) for name in DEPENDENCIES},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
