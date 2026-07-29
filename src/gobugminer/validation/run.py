from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from gobugminer.constants import STAGES
from gobugminer.exceptions import ValidationError

REQUIRED = (
    "config/submitted.yml",
    "config/effective.yml",
    "raw/pull_requests.jsonl",
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
    "reports/summary.json",
    "reports/validation.json",
    "provenance/environment.json",
    "provenance/manifest.json",
    "provenance/stage-inputs.json",
    "provenance/stages.json",
    "provenance/versions.json",
    "provenance/checksums.sha256",
    "logs/events.jsonl",
)


def _rows(path: Path) -> list[dict[str, str]]:
    if path.stat().st_size == 0:
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def validate(
    root: Path,
    *,
    allow_incomplete: bool = False,
) -> dict[str, Any]:
    errors: list[str] = []
    for relative in REQUIRED:
        if allow_incomplete and relative == "reports/validation.json":
            continue
        if not (root / relative).is_file():
            errors.append(f"missing file: {relative}")
    checksum_path = root / "provenance/checksums.sha256"
    if checksum_path.is_file():
        indexed: set[str] = set()
        for line in checksum_path.read_text(encoding="utf-8").splitlines():
            digest, relative = line.split("  ", 1)
            indexed.add(relative)
            path = root / relative
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                errors.append(f"checksum mismatch: {relative}")
        checksum_exclusions = {
            "provenance/checksums.sha256",
            "reports/validation.json",
        }
        expected = set(REQUIRED) - checksum_exclusions
        for relative in sorted(expected - indexed):
            errors.append(f"missing checksum entry: {relative}")
    relation_path = root / "normalized/fix_bic_relations.csv"
    fixes_path = root / "normalized/fix_commits.csv"
    bics_path = root / "normalized/bic_candidates.csv"
    if all(x.is_file() for x in (relation_path, fixes_path, bics_path)):
        relations = _rows(relation_path)
        fix_rows = _rows(fixes_path)
        fixes = {x["fix_commit_sha"] for x in fix_rows}
        allowed_policies = {
            "reachable_merge_sha",
            "reachable_squash_sha",
            "verified_head_fallback",
        }
        for row in fix_rows:
            if row["fix_commit_sha"] != row.get("analysis_fix_sha"):
                errors.append("fix record analysis SHA differs from fix relation SHA")
            if not row.get("evidence_fix_sha"):
                errors.append("fix record is missing evidence SHA")
            if row.get("fix_resolution_policy") not in allowed_policies:
                errors.append("fix record has invalid resolution policy")
            if not row.get("analysis_resolution_reason"):
                errors.append("fix record is missing analysis resolution reason")
        bics = {x["bic_commit_sha"] for x in _rows(bics_path)}
        keys = [(x["fix_commit_sha"], x["bic_commit_sha"], x["file_path"]) for x in relations]
        if len(keys) != len(set(keys)):
            errors.append("duplicate fix/BIC relation")
        if any(x["fix_commit_sha"] not in fixes for x in relations):
            errors.append("relation references unknown fix commit")
        if any(x["bic_commit_sha"] not in bics for x in relations):
            errors.append("relation references unknown BIC candidate")
        if keys != sorted(keys):
            errors.append("relations are not deterministically ordered")
        commit_labels_path = root / "labels/commit_labels.csv"
        if commit_labels_path.is_file():
            commit_label_rows = _rows(commit_labels_path)
            commit_label_keys = [row["commit_sha"] for row in commit_label_rows]
            if len(commit_label_keys) != len(set(commit_label_keys)):
                errors.append("duplicate commit label")
            if set(commit_label_keys) != fixes | bics:
                errors.append("commit labels do not match fix/BIC evidence")
            if commit_label_keys != sorted(commit_label_keys):
                errors.append("commit labels are not deterministically ordered")
            for row in commit_label_rows:
                expected_label = "1" if row["commit_sha"] in bics else "0"
                expected_policy = "candidate_bic" if expected_label == "1" else "fix_revision"
                if row["label"] != expected_label or row["policy"] != expected_policy:
                    errors.append(f"incorrect commit label policy: {row['commit_sha']}")
            labels_by_commit = {row["commit_sha"]: row["label"] for row in commit_label_rows}
        else:
            labels_by_commit = {}
    else:
        labels_by_commit = {}
    file_metrics_path = root / "metrics/files.csv"
    file_labels_path = root / "labels/file_labels.csv"
    if file_metrics_path.is_file() and file_labels_path.is_file():
        file_metric_keys = {
            (row["commit_sha"], row["file_path"]) for row in _rows(file_metrics_path)
        }
        label_rows = _rows(file_labels_path)
        file_label_keys = [(row["commit_sha"], row["file_path"]) for row in label_rows]
        if len(file_label_keys) != len(set(file_label_keys)):
            errors.append("duplicate file label")
        if set(file_label_keys) != file_metric_keys:
            errors.append("file labels do not match file metrics")
        if file_label_keys != sorted(file_label_keys):
            errors.append("file labels are not deterministically ordered")
        if any(
            row["commit_sha"] not in labels_by_commit
            or row["label"] != labels_by_commit[row["commit_sha"]]
            for row in label_rows
        ):
            errors.append("file labels do not inherit revision labels")
    method_metrics_path = root / "metrics/methods.csv"
    method_labels_path = root / "labels/method_labels.csv"
    if method_metrics_path.is_file() and method_labels_path.is_file():
        method_metric_keys = {
            (row["commit_sha"], row["file_path"], row["method_identifier"])
            for row in _rows(method_metrics_path)
        }
        label_rows = _rows(method_labels_path)
        method_label_keys = [
            (row["commit_sha"], row["file_path"], row["method_identifier"]) for row in label_rows
        ]
        if len(method_label_keys) != len(set(method_label_keys)):
            errors.append("duplicate method label")
        if set(method_label_keys) != method_metric_keys:
            errors.append("method labels do not match method metrics")
        if method_label_keys != sorted(method_label_keys):
            errors.append("method labels are not deterministically ordered")
        if any(
            row["commit_sha"] not in labels_by_commit
            or row["label"] != labels_by_commit[row["commit_sha"]]
            for row in label_rows
        ):
            errors.append("method labels do not inherit revision labels")
    manifest_path = root / "provenance/manifest.json"
    stage_inputs_path = root / "provenance/stage-inputs.json"
    if manifest_path.is_file() and stage_inputs_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        stage_inputs = json.loads(stage_inputs_path.read_text(encoding="utf-8"))
        if manifest.get("input_fingerprint") != stage_inputs.get("run_input_fingerprint"):
            errors.append("manifest and stage input fingerprints differ")
        if manifest.get("szz_path_scope") not in {"production_go", "all_changed"}:
            errors.append("manifest has invalid SZZ path scope")
        if not isinstance(manifest.get("source_filter_policy"), dict):
            errors.append("manifest is missing source filter policy")
        excluded = manifest.get("excluded_szz_paths_by_category")
        if not isinstance(excluded, dict):
            errors.append("manifest is missing SZZ exclusion counts")
        resolutions = manifest.get("fix_revision_resolutions")
        if not isinstance(resolutions, list):
            errors.append("manifest is missing fix revision resolutions")
        stage_names = list(stage_inputs.get("stages", {}))
        if len(stage_names) != len(set(stage_names)):
            errors.append("duplicate stage input hash")
    stages_path = root / "provenance/stages.json"
    if stages_path.is_file() and not allow_incomplete:
        stages = json.loads(stages_path.read_text(encoding="utf-8"))
        incomplete = [name for name in STAGES if stages.get(name, {}).get("status") != "complete"]
        if incomplete:
            errors.append(f"incomplete stages: {', '.join(incomplete)}")
    report = {"valid": not errors, "errors": errors}
    report_path = root / "reports/validation.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if errors:
        raise ValidationError("; ".join(errors))
    return report
