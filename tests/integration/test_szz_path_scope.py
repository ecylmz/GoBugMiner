from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

import pytest

from gobugminer.config import load_config
from gobugminer.pipeline import mine
from gobugminer.szz.pydriller_szz import candidates


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _write(repo: Path, relative: str, value: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


@pytest.fixture
def scoped_szz_case(tmp_path: Path) -> tuple[Path, str, dict[str, str]]:
    repo = tmp_path / "scope-repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Scope Fixture")
    _git(repo, "config", "user.email", "scope@example.invalid")
    values = {
        "main.go": "package fixture\n\nvar MainValue = 0\n",
        "main_test.go": "package fixture\n\nvar TestValue = 0\n",
        "generated.go": (
            "// Code generated fixture. DO NOT EDIT.\npackage fixture\nvar GenValue = 0\n"
        ),
        "vendor/example/vendor.go": "package example\n\nvar VendorValue = 0\n",
        "README.md": "value: 0\n",
        ".github/workflows/ci.yml": "value: 0\n",
        "helper.py": "value = 0\n",
    }
    for path, value in values.items():
        _write(repo, path, value)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add scoped files")

    introducing: dict[str, str] = {}
    for path, value in values.items():
        _write(repo, path, value.replace("0", "1"))
        _git(repo, "add", path)
        _git(repo, "commit", "-m", f"change {path}")
        introducing[path] = _git(repo, "rev-parse", "HEAD")

    for path, value in values.items():
        _write(repo, path, value.replace("0", "2"))
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "fix all scoped files")
    return repo, _git(repo, "rev-parse", "HEAD"), introducing


def test_szz_scope_filters_all_required_categories(
    scoped_szz_case: tuple[Path, str, dict[str, str]],
) -> None:
    repo, fix, introducing = scoped_szz_case
    default = candidates(
        repo,
        fix,
        scope="production_go",
        exclude_tests=True,
        include_generated=False,
    )
    assert {(row.file_path, row.bic_commit_sha) for row in default.relations} == {
        ("main.go", introducing["main.go"])
    }
    assert {row["category"] for row in default.exclusions} == {
        "test_go",
        "generated_go",
        "vendor",
        "non_go",
    }
    assert sum(row["category"] == "non_go" for row in default.exclusions) == 3

    tests_included = candidates(
        repo,
        fix,
        scope="production_go",
        exclude_tests=False,
        include_generated=False,
    )
    assert {row.file_path for row in tests_included.relations} == {
        "main.go",
        "main_test.go",
    }

    generated_included = candidates(
        repo,
        fix,
        scope="production_go",
        exclude_tests=True,
        include_generated=True,
    )
    assert {row.file_path for row in generated_included.relations} == {
        "generated.go",
        "main.go",
    }

    all_changed = candidates(
        repo,
        fix,
        scope="all_changed",
        exclude_tests=True,
        include_generated=False,
    )
    assert {row.file_path for row in all_changed.relations} == set(introducing)
    assert {row.bic_commit_sha for row in all_changed.relations} == set(introducing.values())
    assert not all_changed.exclusions


def test_default_scope_prevents_non_go_positive_revision_labels(
    scoped_szz_case: tuple[Path, str, dict[str, str]],
    tmp_path: Path,
) -> None:
    repo, fix, introducing = scoped_szz_case
    prs = tmp_path / "pull-requests.json"
    prs.write_text(
        json.dumps(
            [
                {
                    "number": 1,
                    "html_url": "https://example.invalid/pull/1",
                    "labels": [{"name": "bug"}],
                    "merged_at": "2026-01-01T00:00:00Z",
                    "merge_commit_sha": fix,
                    "head": {"sha": fix},
                }
            ]
        ),
        encoding="utf-8",
    )
    config = tmp_path / "config.yml"
    config.write_text(
        f"""schema_version: "1"
project:
  repository: fixture/scope
  bug_labels: [bug]
mining:
  levels: [commit, file, method]
  szz_path_scope: production_go
paths:
  output_dir: ./run
  cache_dir: ./cache
offline:
  repository_path: {repo}
  pull_requests_path: {prs}
""",
        encoding="utf-8",
    )
    output = mine(load_config(config), offline=True)
    with (output / "labels/commit_labels.csv").open(encoding="utf-8", newline="") as handle:
        labels = {row["commit_sha"]: row["label"] for row in csv.DictReader(handle)}
    assert labels == {fix: "0", introducing["main.go"]: "1"}
    assert all(labels.get(sha) != "1" for path, sha in introducing.items() if path != "main.go")

    manifest = json.loads((output / "provenance/manifest.json").read_text(encoding="utf-8"))
    assert manifest["szz_path_scope"] == "production_go"
    assert manifest["source_filter_policy"] == {
        "exclude_tests": True,
        "include_generated_files": False,
    }
    assert manifest["excluded_szz_paths_by_category"] == {
        "generated_go": 1,
        "missing_path": 0,
        "non_go": 3,
        "production_go": 0,
        "test_go": 1,
        "unavailable_source": 0,
        "vendor": 1,
    }
