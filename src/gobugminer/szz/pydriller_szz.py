from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydriller import Git

from gobugminer.models import BicRelation
from gobugminer.source_filter import classify_modified_file, szz_scope_accepts


@dataclass(frozen=True)
class SzzResult:
    relations: list[BicRelation]
    exclusions: list[dict[str, Any]]


def candidates(
    repo: Path,
    fix_sha: str,
    *,
    scope: str,
    exclude_tests: bool,
    include_generated: bool,
) -> SzzResult:
    git = Git(str(repo))
    commit = git.get_commit(fix_sha)
    rows: set[BicRelation] = set()
    exclusions: list[dict[str, Any]] = []
    for modified_file in commit.modified_files:
        classified = classify_modified_file(modified_file)
        if not szz_scope_accepts(
            classified.category,
            scope=scope,
            exclude_tests=exclude_tests,
            include_generated=include_generated,
        ):
            exclusions.append(
                {
                    "stage": "szz",
                    "sha": fix_sha,
                    "file_path": classified.path,
                    "category": classified.category,
                    "reason": f"excluded by SZZ path scope {scope}",
                }
            )
            continue
        evidence = git.get_commits_last_modified_lines(commit, modification=modified_file)
        rows.update(
            BicRelation(fix_sha, bic_sha, path)
            for path, commits in evidence.items()
            for bic_sha in commits
        )
    return SzzResult(sorted(rows), exclusions)
