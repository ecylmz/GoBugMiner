from __future__ import annotations

import csv
from pathlib import Path

from gobugminer.models import BicRelation, PullRequest, RunData
from gobugminer.outputs.writer import write_outputs


def _pull_request(number: int, fix: str) -> PullRequest:
    return PullRequest(
        number=number,
        url=f"https://example.invalid/pull/{number}",
        labels=("bug",),
        merged=True,
        merge_commit_sha=fix,
        head_sha=fix,
        base_sha="base",
        evidence_fix_sha=fix,
        analysis_fix_sha=fix,
        fix_resolution_policy="reachable_squash_sha",
        analysis_resolution_reason="fixture",
        created_at="2026-01-01T00:00:00Z",
        closed_at="2026-01-02T00:00:00Z",
        merged_at="2026-01-02T00:00:00Z",
    )


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_revision_role_label_policy_and_entity_inheritance(tmp_path: Path) -> None:
    data = RunData(
        pull_requests=[_pull_request(1, "fix"), _pull_request(2, "both")],
        relations=[
            BicRelation("fix", "bic", "bic.go"),
            BicRelation("fix", "both", "both.go"),
        ],
        commit_metrics=[
            {"commit_sha": "bic", "role": "candidate_bic"},
            {"commit_sha": "both", "role": "candidate_bic"},
            {"commit_sha": "fix", "role": "fix_revision"},
        ],
        file_metrics=[
            {"commit_sha": sha, "file_path": f"{sha}.go"} for sha in ("bic", "both", "fix")
        ],
        method_metrics=[
            {
                "commit_sha": sha,
                "file_path": f"{sha}.go",
                "method_identifier": f"{sha}.go::f@1",
            }
            for sha in ("bic", "both", "fix")
        ],
    )
    write_outputs(
        tmp_path,
        data,
        repository="fixture/example",
        resolved_revision="target",
        labels=["bug"],
        effective_config={},
        environment={},
        stages={},
        input_fingerprint="fingerprint",
        stage_inputs={},
    )

    commit_rows = _rows(tmp_path / "labels/commit_labels.csv")
    assert [(row["commit_sha"], row["label"]) for row in commit_rows] == [
        ("bic", "1"),
        ("both", "1"),
        ("fix", "0"),
    ]
    assert {row["commit_sha"] for row in commit_rows} == {"bic", "both", "fix"}

    labels_by_commit = {row["commit_sha"]: row["label"] for row in commit_rows}
    file_rows = _rows(tmp_path / "labels/file_labels.csv")
    method_rows = _rows(tmp_path / "labels/method_labels.csv")
    assert all(row["label"] == labels_by_commit[row["commit_sha"]] for row in file_rows)
    assert all(row["label"] == labels_by_commit[row["commit_sha"]] for row in method_rows)

    file_metric_keys = {
        (row["commit_sha"], row["file_path"]) for row in _rows(tmp_path / "metrics/files.csv")
    }
    file_label_keys = {(row["commit_sha"], row["file_path"]) for row in file_rows}
    assert file_label_keys == file_metric_keys

    method_metric_keys = {
        (row["commit_sha"], row["file_path"], row["method_identifier"])
        for row in _rows(tmp_path / "metrics/methods.csv")
    }
    method_label_keys = {
        (row["commit_sha"], row["file_path"], row["method_identifier"]) for row in method_rows
    }
    assert method_label_keys == method_metric_keys
