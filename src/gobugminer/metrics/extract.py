from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydriller import Git

from gobugminer.metrics.go import go_counts
from gobugminer.source_filter import classify_modified_file, source_filter_accepts


def _value(value: Any) -> Any:
    return value if value is not None else None


def sum_or_none(values: Iterable[int | float | None]) -> int | float | None:
    available = [value for value in values if value is not None]
    if not available:
        return None
    return sum(available)


def extract_revision(
    repo: Path,
    sha: str,
    project: str,
    role: str,
    *,
    exclude_tests: bool,
    include_generated: bool,
    include_message: bool,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    commit = Git(str(repo)).get_commit(sha)
    files: list[dict[str, Any]] = []
    methods: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    production = []
    for modified in commit.modified_files:
        classified = classify_modified_file(modified)
        path = classified.path
        category = classified.category
        accepted = source_filter_accepts(
            category,
            exclude_tests=exclude_tests,
            include_generated=include_generated,
        )
        if not accepted:
            exclusions.append(
                {
                    "stage": "metrics",
                    "sha": sha,
                    "file_path": path,
                    "category": category,
                    "reason": "excluded by configured Go source policy",
                }
            )
            continue
        production.append(modified)
        counts = go_counts(classified.source)
        file_row = {
            "project": project,
            "commit_sha": sha,
            "role": role,
            "file_path": path,
            "old_path": modified.old_path or "",
            "change_type": str(modified.change_type.name).lower(),
            "classification": category,
            "added_lines": modified.added_lines,
            "deleted_lines": modified.deleted_lines,
            "churn": modified.added_lines + modified.deleted_lines,
            "nloc": _value(modified.nloc),
            "complexity": _value(modified.complexity),
            "token_count": _value(modified.token_count),
            "method_count": len(modified.methods),
            **counts,
        }
        files.append(file_row)
        for method in modified.methods:
            method_source = None
            if classified.source and method.start_line and method.end_line:
                lines = classified.source.splitlines()
                method_source = "\n".join(lines[method.start_line - 1 : method.end_line])
            method_counts = go_counts(method_source, wrap_declaration=True)
            methods.append(
                {
                    "project": project,
                    "commit_sha": sha,
                    "role": role,
                    "file_path": path,
                    "method_identifier": f"{path}::{method.name}@{method.start_line}",
                    "method_name": method.name,
                    "start_line": method.start_line,
                    "end_line": method.end_line,
                    "nloc": _value(method.nloc),
                    "cyclomatic_complexity": _value(method.complexity),
                    "token_count": _value(method.token_count),
                    "parameter_count": len(method.parameters),
                    "defer_count": method_counts["defer_count"],
                    "channel_count": method_counts["channel_count"],
                    "goroutine_count": method_counts["goroutine_count"],
                    "error_handling_count": method_counts["error_handling_count"],
                    "loop_count": method_counts["loop_count"],
                    "parse_failure": method_counts["parse_failure"],
                }
            )
    if not production:
        return None, files, methods, exclusions
    churns = [item.added_lines + item.deleted_lines for item in production]
    commit_row = {
        "project": project,
        "commit_sha": sha,
        "role": role,
        "commit_timestamp": commit.committer_date.isoformat(),
        "parent_count": len(commit.parents),
        "is_merge": commit.merge,
        "modified_go_files": len(production),
        "insertions": sum(item.added_lines for item in production),
        "deletions": sum(item.deleted_lines for item in production),
        "net_lines": sum(item.added_lines - item.deleted_lines for item in production),
        "total_churn": sum(churns),
        "maximum_file_churn": max(churns),
        "average_file_churn": sum(churns) / len(churns),
        "dmm_unit_size": _value(commit.dmm_unit_size),
        "dmm_unit_complexity": _value(commit.dmm_unit_complexity),
        "dmm_unit_interfacing": _value(commit.dmm_unit_interfacing),
        "aggregate_nloc": sum_or_none(x["nloc"] for x in files),
        "aggregate_complexity": sum_or_none(x["complexity"] for x in files),
        "aggregate_token_count": sum_or_none(x["token_count"] for x in files),
        "aggregate_changed_method_count": sum(len(x.changed_methods) for x in production),
        "commit_message": commit.msg if include_message else "",
    }
    return commit_row, files, methods, exclusions
