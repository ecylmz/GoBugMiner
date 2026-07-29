from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from gobugminer.config import Config, Project
from gobugminer.exceptions import ExtractionError
from gobugminer.pipeline import _live_prs, _offline_prs, _resolve_fix, mine


class FakeClient:
    def issues_with_label(self, _repository: str, _label: str) -> list[dict[str, Any]]:
        return [
            {"number": 1, "pull_request": {}},
            {"number": 2},
            {"number": 3, "pull_request": {}},
        ]

    def api(self, endpoint: str) -> dict[str, Any]:
        number = int(endpoint.rsplit("/", 1)[-1])
        return {
            "number": number,
            "html_url": f"https://example/{number}",
            "labels": [{"name": "bug"}],
            "merged_at": None if number == 3 else "2026-01-01T00:00:00Z",
            "merge_commit_sha": "a" * 40,
            "created_at": None,
            "closed_at": None,
        }


def test_live_selection_filters_issues_and_unmerged() -> None:
    cfg = Config("1", Project("a/b", ["bug"]))
    assert [x.number for x in _live_prs(cfg, FakeClient())] == [1]  # type: ignore[arg-type]


def test_offline_requires_paths(tmp_path: Path) -> None:
    config = tmp_path / "config.yml"
    config.write_text(
        'schema_version: "1"\nproject:\n  repository: a/b\n  bug_labels: [bug]\n'
        "paths:\n  output_dir: ./run\n",
        encoding="utf-8",
    )
    from gobugminer.config import load_config

    with pytest.raises(ExtractionError, match=r"offline\.repository_path"):
        mine(load_config(config), offline=True)


def test_fix_revision_resolution(
    offline_case: tuple[Path, Path, str, str],
) -> None:
    from gobugminer.config import load_config

    config_path, repo, _fix, bic = offline_case
    pull_request = _offline_prs(load_config(config_path))[0]
    cfg = load_config(config_path)
    resolved = _resolve_fix(repo, pull_request, cfg)
    assert resolved.fix_resolution_policy == "reachable_squash_sha"
    assert resolved.evidence_fix_sha == resolved.analysis_fix_sha
    fallback = _resolve_fix(
        repo,
        replace(pull_request, merge_commit_sha="f" * 40, head_sha=bic),
        cfg,
    )
    assert fallback.fix_resolution_policy == "verified_head_fallback"
    assert fallback.evidence_fix_sha == bic
    assert fallback.analysis_fix_sha == bic
    unresolved = _resolve_fix(
        repo,
        replace(pull_request, merge_commit_sha="f" * 40, head_sha=None),
        cfg,
    )
    assert unresolved.fix_resolution_policy == "unresolvable"
    assert unresolved.analysis_fix_sha is None
