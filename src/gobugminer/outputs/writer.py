from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from gobugminer import SCHEMA_VERSION, __version__
from gobugminer.models import RunData


def csv_file(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        if fields:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)


def json_file(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def jsonl_file(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8"
    )


def checksums(root: Path) -> list[str]:
    target = root / "provenance" / "checksums.sha256"
    excluded = {
        target,
        root / "RUN_COMPLETE",
        root / "reports" / "validation.json",
    }
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path not in excluded:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            rows.append(f"{digest}  {path.relative_to(root).as_posix()}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return rows


def write_outputs(
    root: Path,
    data: RunData,
    *,
    repository: str,
    resolved_revision: str,
    labels: list[str],
    effective_config: dict[str, Any],
    environment: dict[str, Any],
    stages: dict[str, Any],
    input_fingerprint: str,
    stage_inputs: dict[str, str],
) -> dict[str, Any]:
    prs = sorted((x.row() for x in data.pull_requests), key=lambda row: row["number"])
    relations = [x.row() for x in sorted(data.relations)]
    fix_records = sorted(
        (
            {
                "fix_commit_sha": pr.analysis_fix_sha,
                "evidence_fix_sha": pr.evidence_fix_sha or "",
                "analysis_fix_sha": pr.analysis_fix_sha,
                "pull_request_number": pr.number,
                "fix_resolution_policy": pr.fix_resolution_policy or "",
                "analysis_resolution_reason": pr.analysis_resolution_reason or "",
            }
            for pr in data.pull_requests
            if pr.analysis_fix_sha is not None
        ),
        key=lambda row: (str(row["analysis_fix_sha"]), str(row["pull_request_number"])),
    )
    fixes = {str(row["analysis_fix_sha"]) for row in fix_records}
    bics = sorted({relation.bic_commit_sha for relation in data.relations})
    jsonl_file(root / "raw/pull_requests.jsonl", prs)
    csv_file(root / "normalized/pull_requests.csv", prs)
    csv_file(
        root / "normalized/fix_commits.csv",
        fix_records,
        [
            "fix_commit_sha",
            "evidence_fix_sha",
            "analysis_fix_sha",
            "pull_request_number",
            "fix_resolution_policy",
            "analysis_resolution_reason",
        ],
    )
    csv_file(
        root / "normalized/bic_candidates.csv",
        [{"bic_commit_sha": sha} for sha in bics],
        ["bic_commit_sha"],
    )
    csv_file(root / "normalized/fix_bic_relations.csv", relations)
    csv_file(
        root / "metrics/commits.csv",
        sorted(data.commit_metrics, key=lambda row: (row["commit_sha"], row["role"])),
    )
    csv_file(
        root / "metrics/files.csv",
        sorted(data.file_metrics, key=lambda row: (row["commit_sha"], row["file_path"])),
    )
    csv_file(
        root / "metrics/methods.csv",
        sorted(
            data.method_metrics,
            key=lambda row: (row["commit_sha"], row["method_identifier"]),
        ),
    )
    labels_by_commit = {sha: 0 for sha in fixes}
    labels_by_commit.update({sha: 1 for sha in bics})
    labels_rows = [
        {
            "commit_sha": sha,
            "label": label,
            "policy": "candidate_bic" if label else "fix_revision",
        }
        for sha, label in labels_by_commit.items()
    ]
    csv_file(
        root / "labels/commit_labels.csv",
        sorted(labels_rows, key=lambda row: row["commit_sha"]),
        ["commit_sha", "label", "policy"],
    )
    file_labels = [
        {
            "commit_sha": row["commit_sha"],
            "file_path": row["file_path"],
            "label": labels_by_commit[row["commit_sha"]],
            "policy": "candidate_bic_entity"
            if labels_by_commit[row["commit_sha"]]
            else "fix_revision_entity",
        }
        for row in data.file_metrics
    ]
    csv_file(
        root / "labels/file_labels.csv",
        sorted(file_labels, key=lambda row: (row["commit_sha"], row["file_path"])),
        ["commit_sha", "file_path", "label", "policy"],
    )
    method_labels = [
        {
            "commit_sha": row["commit_sha"],
            "file_path": row["file_path"],
            "method_identifier": row["method_identifier"],
            "label": labels_by_commit[row["commit_sha"]],
            "policy": "candidate_bic_entity"
            if labels_by_commit[row["commit_sha"]]
            else "fix_revision_entity",
        }
        for row in data.method_metrics
    ]
    csv_file(
        root / "labels/method_labels.csv",
        sorted(
            method_labels,
            key=lambda row: (row["commit_sha"], row["file_path"], row["method_identifier"]),
        ),
        ["commit_sha", "file_path", "method_identifier", "label", "policy"],
    )
    csv_file(
        root / "reports/exclusions.csv",
        data.exclusions,
        ["stage", "sha", "file_path", "category", "reason"],
    )
    csv_file(root / "reports/warnings.csv", data.warnings, ["entity", "warning"])
    szz_exclusion_counts = Counter(
        row["category"] for row in data.exclusions if row.get("stage") == "szz"
    )
    all_szz_categories = (
        "production_go",
        "test_go",
        "generated_go",
        "vendor",
        "non_go",
        "missing_path",
        "unavailable_source",
    )
    excluded_szz_paths_by_category = {
        category: szz_exclusion_counts.get(category, 0) for category in all_szz_categories
    }
    mining_config = effective_config.get("mining", {})
    szz_path_scope = mining_config.get("szz_path_scope", "production_go")
    summary = {
        "repository": repository,
        "resolved_revision": resolved_revision,
        "labels": labels,
        "pull_request_count": len(prs),
        "fix_commit_count": len(fix_records),
        "bic_candidate_count": len(bics),
        "commit_metric_count": len(data.commit_metrics),
        "file_metric_count": len(data.file_metrics),
        "method_metric_count": len(data.method_metrics),
        "commit_label_count": len(labels_rows),
        "file_label_count": len(file_labels),
        "method_label_count": len(method_labels),
        "exclusion_count": len(data.exclusions),
        "szz_exclusion_count": sum(szz_exclusion_counts.values()),
        "warning_count": len(data.warnings),
        "software_version": __version__,
        "schema_version": SCHEMA_VERSION,
        "run_status": "awaiting_validation",
    }
    json_file(root / "reports/summary.json", summary)
    (root / "reports/summary.md").write_text(
        "# GoBugMiner run summary\n\n"
        + "\n".join(f"- {key}: {value}" for key, value in summary.items())
        + "\n",
        encoding="utf-8",
    )
    json_file(root / "provenance/environment.json", environment)
    json_file(
        root / "provenance/versions.json",
        {
            "gobugminer": __version__,
            "schema": SCHEMA_VERSION,
        },
    )
    json_file(root / "provenance/stages.json", stages)
    json_file(
        root / "provenance/manifest.json",
        {
            "schema_version": SCHEMA_VERSION,
            "software_version": __version__,
            "repository": repository,
            "resolved_revision": resolved_revision,
            "effective_config": effective_config,
            "input_fingerprint": input_fingerprint,
            "szz_path_scope": szz_path_scope,
            "source_filter_policy": {
                "exclude_tests": mining_config.get("exclude_tests", True),
                "include_generated_files": mining_config.get("include_generated_files", False),
            },
            "excluded_szz_paths_by_category": excluded_szz_paths_by_category,
            "fix_revision_resolutions": [
                {
                    "pull_request_number": pr.number,
                    "github_merge_sha": pr.merge_commit_sha,
                    "pr_head_sha": pr.head_sha,
                    "evidence_fix_sha": pr.evidence_fix_sha,
                    "analysis_fix_sha": pr.analysis_fix_sha,
                    "fix_resolution_policy": pr.fix_resolution_policy,
                    "analysis_resolution_reason": pr.analysis_resolution_reason,
                }
                for pr in sorted(data.pull_requests, key=lambda item: item.number)
            ],
        },
    )
    json_file(
        root / "provenance/stage-inputs.json",
        {
            "run_input_fingerprint": input_fingerprint,
            "stages": stage_inputs,
        },
    )
    checksums(root)
    return summary
