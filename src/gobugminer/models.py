from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class PullRequest:
    number: int
    url: str
    labels: tuple[str, ...]
    merged: bool
    merge_commit_sha: str | None
    head_sha: str | None
    base_sha: str | None
    evidence_fix_sha: str | None
    analysis_fix_sha: str | None
    fix_resolution_policy: str | None
    analysis_resolution_reason: str | None
    created_at: str | None
    closed_at: str | None
    merged_at: str | None

    def row(self) -> dict[str, Any]:
        result = asdict(self)
        result["labels"] = "|".join(self.labels)
        return result


@dataclass(frozen=True, order=True)
class BicRelation:
    fix_commit_sha: str
    bic_commit_sha: str
    file_path: str
    engine: str = "pydriller"

    def row(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class RunData:
    pull_requests: list[PullRequest] = field(default_factory=list)
    relations: list[BicRelation] = field(default_factory=list)
    commit_metrics: list[dict[str, Any]] = field(default_factory=list)
    file_metrics: list[dict[str, Any]] = field(default_factory=list)
    method_metrics: list[dict[str, Any]] = field(default_factory=list)
    exclusions: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
