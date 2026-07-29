from __future__ import annotations

import argparse
import csv
import hashlib
import json
from importlib.metadata import version
from pathlib import Path
from typing import Any

DEPENDENCIES = ("pydriller", "PyYAML", "tree-sitter", "tree-sitter-go")


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected an object in {path}")
    return value


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--command", required=True)
    args = parser.parse_args()

    run = args.run.resolve()
    destination = args.destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    summary = _json(run / "reports/summary.json")
    validation = _json(run / "reports/validation.json")
    manifest = _json(run / "provenance/manifest.json")
    environment = _json(run / "provenance/environment.json")
    pull_requests = _rows(run / "normalized/pull_requests.csv")
    fixes = _rows(run / "normalized/fix_commits.csv")
    candidates = _rows(run / "normalized/bic_candidates.csv")
    if len(pull_requests) != 1 or len(fixes) != 1:
        raise ValueError("paper snapshot requires exactly one pull request and one fix revision")
    selected = pull_requests[0]
    selection = manifest["effective_config"]["selection"]
    labels = manifest["effective_config"]["project"]["bug_labels"]
    dependencies = {name: version(name) for name in DEPENDENCIES}

    snapshot_summary = {
        "repository": summary["repository"],
        "configured_bug_labels": labels,
        "observation_window": {
            "since": selection["since"],
            "until": selection["until"],
        },
        "max_prs": selection["max_prs"],
        "selected_pull_request_number": int(selected["number"]),
        "selected_pull_request_url": selected["url"],
        "github_merge_sha": selected["merge_commit_sha"],
        "pr_head_sha": selected["head_sha"],
        "evidence_fix_sha": fixes[0]["evidence_fix_sha"],
        "analysis_fix_sha": fixes[0]["analysis_fix_sha"],
        "fix_resolution_policy": fixes[0]["fix_resolution_policy"],
        "analysis_resolution_reason": fixes[0]["analysis_resolution_reason"],
        "szz_path_scope": manifest["szz_path_scope"],
        "excluded_szz_paths_by_category": manifest["excluded_szz_paths_by_category"],
        "acquired_target_revision": summary["resolved_revision"],
        "candidate_bic_count": len(candidates),
        "commit_metric_row_count": summary["commit_metric_count"],
        "file_metric_row_count": summary["file_metric_count"],
        "method_metric_row_count": summary["method_metric_count"],
        "commit_label_row_count": summary["commit_label_count"],
        "file_label_row_count": summary["file_label_count"],
        "method_label_row_count": summary["method_label_count"],
        "warning_count": summary["warning_count"],
        "exclusion_count": summary["exclusion_count"],
        "validation_result": validation.get("valid") is True,
        "run_date": environment["run_finished"][:10],
        "software_version": summary["software_version"],
        "schema_version": summary["schema_version"],
        "python_version": environment["python"],
        "dependency_versions": dependencies,
        "exact_command": args.command,
    }
    snapshot_manifest = {
        "software_version": manifest["software_version"],
        "schema_version": manifest["schema_version"],
        "repository": manifest["repository"],
        "acquired_target_revision": manifest["resolved_revision"],
        "input_fingerprint": manifest["input_fingerprint"],
        "selected_pull_request": selected,
        "fix_revision": fixes[0],
        "szz_path_scope": manifest["szz_path_scope"],
        "source_filter_policy": manifest["source_filter_policy"],
        "excluded_szz_paths_by_category": manifest["excluded_szz_paths_by_category"],
        "candidate_bic_revisions": [row["bic_commit_sha"] for row in candidates],
        "validation_result": validation,
    }
    snapshot_versions = {
        "gobugminer": summary["software_version"],
        "schema": summary["schema_version"],
        "python": environment["python"],
        "git": environment["git"],
        "gh": environment["gh"],
        "dependencies": dependencies,
    }
    prefix = "gin-validation"
    config_target = destination / args.config.name
    if args.config.resolve() != config_target:
        config_target.write_bytes(args.config.resolve().read_bytes())
    (destination / f"{prefix}-command.txt").write_text(args.command + "\n", encoding="utf-8")
    _write(destination / f"{prefix}-summary.json", snapshot_summary)
    _write(destination / f"{prefix}-manifest.json", snapshot_manifest)
    _write(destination / f"{prefix}-versions.json", snapshot_versions)

    evidence = (
        config_target.name,
        f"{prefix}-command.txt",
        f"{prefix}-summary.json",
        f"{prefix}-manifest.json",
        f"{prefix}-versions.json",
    )
    checksums = []
    for name in evidence:
        digest = hashlib.sha256((destination / name).read_bytes()).hexdigest()
        checksums.append(f"{digest}  {name}")
    (destination / f"{prefix}-checksums.sha256").write_text(
        "\n".join(checksums) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
