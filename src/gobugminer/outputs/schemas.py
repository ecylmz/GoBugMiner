from __future__ import annotations

SCHEMAS = {
    "pull_requests": [
        "number",
        "url",
        "labels",
        "merged",
        "merge_commit_sha",
        "head_sha",
        "base_sha",
        "evidence_fix_sha",
        "analysis_fix_sha",
        "fix_resolution_policy",
        "analysis_resolution_reason",
        "created_at",
        "closed_at",
        "merged_at",
    ],
    "fix_commits": [
        "fix_commit_sha",
        "evidence_fix_sha",
        "analysis_fix_sha",
        "pull_request_number",
        "fix_resolution_policy",
        "analysis_resolution_reason",
    ],
    "bic_candidates": ["bic_commit_sha"],
    "fix_bic_relations": ["fix_commit_sha", "bic_commit_sha", "file_path", "engine"],
    "commit_labels": ["commit_sha", "label", "policy"],
    "file_labels": ["commit_sha", "file_path", "label", "policy"],
    "method_labels": [
        "commit_sha",
        "file_path",
        "method_identifier",
        "label",
        "policy",
    ],
}


def markdown() -> str:
    lines = ["# GoBugMiner schema version 1", ""]
    for name, fields in SCHEMAS.items():
        lines.extend([f"## {name}", "", ", ".join(f"`{x}`" for x in fields), ""])
    return "\n".join(lines)
