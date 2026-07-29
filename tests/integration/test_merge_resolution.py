from __future__ import annotations

import csv
import json
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from gobugminer.config import Config, Project, load_config
from gobugminer.models import PullRequest
from gobugminer.pipeline import _resolve_fix, mine


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


@dataclass(frozen=True)
class MergeCase:
    repo: Path
    base: str
    head: str
    merge: str


def _repository(path: Path, *, true_merge: bool) -> MergeCase:
    path.mkdir()
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.name", "Merge Fixture")
    _git(path, "config", "user.email", "merge@example.invalid")
    (path / "main.go").write_text(
        "package fixture\n\nfunc Value() int { return 1 }\n",
        encoding="utf-8",
    )
    (path / "README.md").write_text("status: buggy\n", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-m", "introduce fixture defect")
    base = _git(path, "rev-parse", "HEAD")

    _git(path, "checkout", "-b", "fix")
    (path / "main.go").write_text(
        "package fixture\n\nfunc Value() int { return 2 }\n",
        encoding="utf-8",
    )
    (path / "README.md").write_text("status: fixed\n", encoding="utf-8")
    _git(path, "commit", "-am", "fix production and documentation")
    head = _git(path, "rev-parse", "HEAD")
    _git(path, "checkout", "main")
    if true_merge:
        (path / "NOTES.md").write_text("side change\n", encoding="utf-8")
        _git(path, "add", "NOTES.md")
        _git(path, "commit", "-m", "add side change")
        _git(path, "merge", "--no-ff", "fix", "-m", "merge fix branch")
    else:
        _git(path, "merge", "--squash", "fix")
        _git(path, "commit", "-m", "squash fix branch")
    return MergeCase(path, base, head, _git(path, "rev-parse", "HEAD"))


@pytest.fixture
def merge_cases(tmp_path: Path) -> tuple[MergeCase, MergeCase]:
    return (
        _repository(tmp_path / "squash", true_merge=False),
        _repository(tmp_path / "merge", true_merge=True),
    )


def _pr(case: MergeCase) -> PullRequest:
    return PullRequest(
        number=1,
        url="https://example.invalid/pull/1",
        labels=("bug",),
        merged=True,
        merge_commit_sha=case.merge,
        head_sha=case.head,
        base_sha=case.base,
        evidence_fix_sha=None,
        analysis_fix_sha=None,
        fix_resolution_policy=None,
        analysis_resolution_reason=None,
        created_at="2026-01-01T00:00:00Z",
        closed_at="2026-01-02T00:00:00Z",
        merged_at="2026-01-02T00:00:00Z",
    )


def _offline_config(tmp_path: Path, case: MergeCase, name: str) -> Path:
    pull_requests = tmp_path / f"{name}-pulls.json"
    pull_requests.write_text(
        json.dumps(
            [
                {
                    "number": 1,
                    "html_url": "https://example.invalid/pull/1",
                    "labels": [{"name": "bug"}],
                    "merged_at": "2026-01-02T00:00:00Z",
                    "merge_commit_sha": case.merge,
                    "head": {"sha": case.head},
                    "base": {"sha": case.base},
                }
            ]
        ),
        encoding="utf-8",
    )
    config = tmp_path / f"{name}.yml"
    config.write_text(
        f"""schema_version: "1"
project:
  repository: fixture/{name}
  bug_labels: [bug]
mining:
  levels: [commit, file, method]
  szz_path_scope: production_go
paths:
  output_dir: ./{name}-run
  cache_dir: ./cache
offline:
  repository_path: {case.repo}
  pull_requests_path: {pull_requests}
""",
        encoding="utf-8",
    )
    return config


def test_squash_style_single_parent_revision_is_analyzed_directly(
    merge_cases: tuple[MergeCase, MergeCase],
) -> None:
    squash, _true_merge = merge_cases
    resolved = _resolve_fix(
        squash.repo,
        _pr(squash),
        Config("1", Project("fixture/squash", ["bug"])),
    )
    assert resolved.evidence_fix_sha == squash.merge
    assert resolved.analysis_fix_sha == squash.merge
    assert resolved.fix_resolution_policy == "reachable_squash_sha"


def test_true_two_parent_merge_uses_verified_head_fallback(
    merge_cases: tuple[MergeCase, MergeCase],
) -> None:
    _squash, true_merge = merge_cases
    resolved = _resolve_fix(
        true_merge.repo,
        _pr(true_merge),
        Config("1", Project("fixture/merge", ["bug"])),
    )
    assert resolved.evidence_fix_sha == true_merge.merge
    assert resolved.analysis_fix_sha == true_merge.head
    assert resolved.fix_resolution_policy == "verified_head_fallback"
    assert "ancestry to the merge was verified" in (resolved.analysis_resolution_reason or "")


def test_reachable_merge_sha_with_analyzable_modifications(
    merge_cases: tuple[MergeCase, MergeCase],
) -> None:
    squash, _true_merge = merge_cases
    resolved = _resolve_fix(
        squash.repo,
        _pr(squash),
        Config("1", Project("fixture/squash", ["bug"])),
    )
    assert resolved.analysis_fix_sha == squash.merge


def test_reachable_merge_sha_without_analyzable_modifications(
    merge_cases: tuple[MergeCase, MergeCase],
) -> None:
    _squash, true_merge = merge_cases
    unsafe = replace(_pr(true_merge), head_sha="f" * 40)
    resolved = _resolve_fix(
        true_merge.repo,
        unsafe,
        Config("1", Project("fixture/merge", ["bug"])),
    )
    assert resolved.evidence_fix_sha == true_merge.merge
    assert resolved.analysis_fix_sha is None
    assert resolved.fix_resolution_policy == "unresolvable"


def test_verified_pr_head_fallback_is_recorded(
    merge_cases: tuple[MergeCase, MergeCase],
) -> None:
    _squash, true_merge = merge_cases
    resolved = _resolve_fix(
        true_merge.repo,
        _pr(true_merge),
        Config("1", Project("fixture/merge", ["bug"])),
    )
    assert resolved.fix_resolution_policy == "verified_head_fallback"


def test_unreachable_merge_sha_can_use_target_ancestor_head(
    merge_cases: tuple[MergeCase, MergeCase],
) -> None:
    _squash, true_merge = merge_cases
    unresolved_merge = replace(_pr(true_merge), merge_commit_sha="e" * 40)
    resolved = _resolve_fix(
        true_merge.repo,
        unresolved_merge,
        Config("1", Project("fixture/merge", ["bug"])),
    )
    assert resolved.evidence_fix_sha == true_merge.head
    assert resolved.analysis_fix_sha == true_merge.head
    assert resolved.fix_resolution_policy == "verified_head_fallback"


def test_unreachable_head_sha_is_rejected(
    merge_cases: tuple[MergeCase, MergeCase],
) -> None:
    _squash, true_merge = merge_cases
    unsafe = replace(
        _pr(true_merge),
        merge_commit_sha="e" * 40,
        head_sha="f" * 40,
    )
    resolved = _resolve_fix(
        true_merge.repo,
        unsafe,
        Config("1", Project("fixture/merge", ["bug"])),
    )
    assert resolved.fix_resolution_policy == "unresolvable"
    assert resolved.analysis_fix_sha is None


def test_head_that_fails_ancestry_verification_is_rejected(
    merge_cases: tuple[MergeCase, MergeCase],
) -> None:
    squash, _true_merge = merge_cases
    unsafe = replace(_pr(squash), merge_commit_sha="e" * 40)
    resolved = _resolve_fix(
        squash.repo,
        unsafe,
        Config("1", Project("fixture/squash", ["bug"])),
    )
    assert resolved.fix_resolution_policy == "unresolvable"
    assert resolved.analysis_fix_sha is None


def test_pr_without_safe_analysis_revision_emits_warning(
    merge_cases: tuple[MergeCase, MergeCase],
    tmp_path: Path,
) -> None:
    _squash, true_merge = merge_cases
    config = _offline_config(tmp_path, true_merge, "unsafe")
    payload = json.loads((tmp_path / "unsafe-pulls.json").read_text(encoding="utf-8"))
    payload[0]["head"]["sha"] = "f" * 40
    (tmp_path / "unsafe-pulls.json").write_text(json.dumps(payload), encoding="utf-8")
    output = mine(load_config(config), offline=True)
    summary = json.loads((output / "reports/summary.json").read_text(encoding="utf-8"))
    assert summary["fix_commit_count"] == 0
    assert summary["warning_count"] == 1
    warnings = (output / "reports/warnings.csv").read_text(encoding="utf-8")
    assert "no safe analysis fix revision" in warnings


def test_merge_changing_go_and_non_go_preserves_resolution_and_scope(
    merge_cases: tuple[MergeCase, MergeCase],
    tmp_path: Path,
) -> None:
    _squash, true_merge = merge_cases
    output = mine(
        load_config(_offline_config(tmp_path, true_merge, "true-merge")),
        offline=True,
    )
    with (output / "normalized/fix_commits.csv").open(encoding="utf-8", newline="") as handle:
        fix = next(csv.DictReader(handle))
    assert fix["evidence_fix_sha"] == true_merge.merge
    assert fix["analysis_fix_sha"] == true_merge.head
    assert fix["fix_resolution_policy"] == "verified_head_fallback"

    manifest = json.loads((output / "provenance/manifest.json").read_text(encoding="utf-8"))
    resolution = manifest["fix_revision_resolutions"][0]
    assert resolution["github_merge_sha"] == true_merge.merge
    assert resolution["pr_head_sha"] == true_merge.head
    assert resolution["evidence_fix_sha"] == true_merge.merge
    assert resolution["analysis_fix_sha"] == true_merge.head
    assert manifest["szz_path_scope"] == "production_go"
    assert manifest["excluded_szz_paths_by_category"]["non_go"] == 1

    with (output / "normalized/fix_bic_relations.csv").open(encoding="utf-8", newline="") as handle:
        relations = list(csv.DictReader(handle))
    assert {(row["file_path"], row["bic_commit_sha"]) for row in relations} == {
        ("main.go", true_merge.base)
    }
    with (output / "metrics/commits.csv").open(encoding="utf-8", newline="") as handle:
        commit_shas = {row["commit_sha"] for row in csv.DictReader(handle)}
    assert true_merge.head in commit_shas
