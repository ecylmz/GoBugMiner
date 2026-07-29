from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return result.stdout.strip()


@pytest.fixture
def offline_case(tmp_path: Path) -> tuple[Path, Path, str, str]:
    repo = tmp_path / "fixture-repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "Fixture Author")
    git(repo, "config", "user.email", "fixture@example.invalid")
    source = repo / "calc.go"
    source.write_text(
        "package fixture\n\nfunc Subtract(a, b int) int {\n\treturn a - b\n}\n",
        encoding="utf-8",
    )
    git(repo, "add", "calc.go")
    git(repo, "commit", "-m", "initial implementation")
    source.write_text(
        "package fixture\n\nfunc Subtract(a, b int) int {\n\treturn a + b\n}\n",
        encoding="utf-8",
    )
    git(repo, "commit", "-am", "introduce arithmetic defect")
    bic = git(repo, "rev-parse", "HEAD")
    (repo / "calc_test.go").write_text(
        "package fixture\n\nfunc ExampleSubtract() { _ = Subtract(2, 1) }\n",
        encoding="utf-8",
    )
    git(repo, "add", "calc_test.go")
    git(repo, "commit", "-m", "add test fixture")
    source.write_text(
        "package fixture\n\nfunc Subtract(a, b int) int {\n\treturn a - b\n}\n",
        encoding="utf-8",
    )
    (repo / "calc_test.go").write_text(
        "package fixture\n\n// Fixed behavior.\nfunc ExampleSubtract() { _ = Subtract(2, 1) }\n",
        encoding="utf-8",
    )
    git(repo, "commit", "-am", "fix arithmetic defect")
    fix = git(repo, "rev-parse", "HEAD")
    prs = tmp_path / "pull_requests.json"
    prs.write_text(
        json.dumps(
            [
                {
                    "number": 7,
                    "html_url": "https://example.invalid/pr/7",
                    "labels": [{"name": "bug"}],
                    "merged_at": "2026-01-04T00:00:00Z",
                    "merge_commit_sha": fix,
                    "created_at": "2026-01-03T00:00:00Z",
                    "closed_at": "2026-01-04T00:00:00Z",
                }
            ]
        ),
        encoding="utf-8",
    )
    config = tmp_path / "offline.yml"
    config.write_text(
        f"""schema_version: "1"
project:
  repository: fixture/example
  bug_labels: [bug]
mining:
  levels: [commit, file, method]
paths:
  output_dir: ./run
  cache_dir: ./cache
offline:
  repository_path: {repo}
  pull_requests_path: {prs}
""",
        encoding="utf-8",
    )
    return config, repo, fix, bic
