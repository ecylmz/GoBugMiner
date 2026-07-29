from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydriller import Git

from gobugminer import SCHEMA_VERSION, __version__
from gobugminer.commands import executable, run
from gobugminer.config import Config, dump_yaml, resolve_relative
from gobugminer.constants import STAGES
from gobugminer.exceptions import ExtractionError
from gobugminer.github.client import GitHubClient
from gobugminer.logging import RunLogger
from gobugminer.metrics.extract import extract_revision
from gobugminer.models import PullRequest, RunData
from gobugminer.outputs.writer import checksums, write_outputs
from gobugminer.repository.git import acquire, revision, version
from gobugminer.source_filter import classify_modified_file, szz_scope_accepts
from gobugminer.szz.pydriller_szz import candidates
from gobugminer.validation.run import validate


def _pr(payload: dict[str, Any]) -> PullRequest:
    return PullRequest(
        number=int(payload["number"]),
        url=payload.get("html_url", ""),
        labels=tuple(sorted(x["name"] for x in payload.get("labels", []))),
        merged=bool(payload.get("merged_at")),
        merge_commit_sha=payload.get("merge_commit_sha"),
        head_sha=payload.get("head", {}).get("sha"),
        base_sha=payload.get("base", {}).get("sha"),
        evidence_fix_sha=None,
        analysis_fix_sha=None,
        fix_resolution_policy=None,
        analysis_resolution_reason=None,
        created_at=payload.get("created_at"),
        closed_at=payload.get("closed_at"),
        merged_at=payload.get("merged_at"),
    )


def _offline_prs(cfg: Config) -> list[PullRequest]:
    if not cfg.offline.pull_requests_path:
        raise ExtractionError("offline.pull_requests_path is required in offline mode")
    path = resolve_relative(cfg.offline.pull_requests_path, cfg)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [_pr(item) for item in payload]


def _live_prs(cfg: Config, client: GitHubClient) -> list[PullRequest]:
    found: dict[int, dict[str, Any]] = {}
    for label in cfg.project.bug_labels:
        for item in client.issues_with_label(cfg.project.repository, label):
            if "pull_request" in item:
                found[int(item["number"])] = item
    owner, name = cfg.project.repository.split("/", 1)
    result: list[PullRequest] = []
    for number in sorted(found):
        detail = client.api(f"repos/{owner}/{name}/pulls/{number}")
        pull_request = _pr(detail)
        if cfg.selection.merged_only and not pull_request.merged:
            continue
        selected_at = pull_request.merged_at or pull_request.closed_at
        selected_time = (
            datetime.fromisoformat(selected_at.replace("Z", "+00:00")) if selected_at else None
        )
        since = (
            datetime.fromisoformat(cfg.selection.since) if cfg.selection.since is not None else None
        )
        until = (
            datetime.fromisoformat(cfg.selection.until) if cfg.selection.until is not None else None
        )
        if since and (not selected_time or selected_time < since):
            continue
        if until and (not selected_time or selected_time > until):
            continue
        result.append(pull_request)
    if cfg.selection.max_prs:
        result = result[: cfg.selection.max_prs]
    return result


def _has_commit(repo: Path, sha: str | None) -> bool:
    if not sha:
        return False
    try:
        run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=repo)
        return True
    except Exception:
        return False


def _is_ancestor(repo: Path, ancestor: str | None, descendant: str) -> bool:
    if not ancestor:
        return False
    try:
        run(["git", "merge-base", "--is-ancestor", ancestor, descendant], cwd=repo)
        return True
    except Exception:
        return False


def _has_analyzable_modifications(repo: Path, sha: str, cfg: Config) -> bool:
    try:
        commit = Git(str(repo)).get_commit(sha)
    except Exception:
        return False
    return any(
        szz_scope_accepts(
            classify_modified_file(modified_file).category,
            scope=cfg.mining.szz_path_scope,
            exclude_tests=cfg.mining.exclude_tests,
            include_generated=cfg.mining.include_generated_files,
        )
        for modified_file in commit.modified_files
    )


def _resolve_fix(repo: Path, pr: PullRequest, cfg: Config) -> PullRequest:
    merge_reachable = _has_commit(repo, pr.merge_commit_sha)
    head_reachable = _has_commit(repo, pr.head_sha)
    if merge_reachable and pr.merge_commit_sha:
        merge_commit = Git(str(repo)).get_commit(pr.merge_commit_sha)
        if _has_analyzable_modifications(repo, pr.merge_commit_sha, cfg):
            policy = "reachable_merge_sha" if merge_commit.merge else "reachable_squash_sha"
            return replace(
                pr,
                evidence_fix_sha=pr.merge_commit_sha,
                analysis_fix_sha=pr.merge_commit_sha,
                fix_resolution_policy=policy,
                analysis_resolution_reason=(
                    "reachable GitHub merge revision provides analyzable accepted modifications"
                ),
            )
        if (
            head_reachable
            and pr.head_sha
            and _is_ancestor(repo, pr.head_sha, pr.merge_commit_sha)
            and _has_analyzable_modifications(repo, pr.head_sha, cfg)
        ):
            return replace(
                pr,
                evidence_fix_sha=pr.merge_commit_sha,
                analysis_fix_sha=pr.head_sha,
                fix_resolution_policy="verified_head_fallback",
                analysis_resolution_reason=(
                    "reachable GitHub merge revision has no analyzable accepted "
                    "modifications; the PR head is reachable, analyzable, and its "
                    "ancestry to the merge was verified"
                ),
            )
        return replace(
            pr,
            evidence_fix_sha=pr.merge_commit_sha,
            analysis_fix_sha=None,
            fix_resolution_policy="unresolvable",
            analysis_resolution_reason=(
                "reachable GitHub merge revision has no analyzable accepted modifications and "
                "no safe ancestry-verified PR-head fallback exists"
            ),
        )
    if (
        head_reachable
        and pr.head_sha
        and _is_ancestor(repo, pr.head_sha, "HEAD")
        and _has_analyzable_modifications(repo, pr.head_sha, cfg)
    ):
        return replace(
            pr,
            evidence_fix_sha=pr.head_sha,
            analysis_fix_sha=pr.head_sha,
            fix_resolution_policy="verified_head_fallback",
            analysis_resolution_reason=(
                "GitHub merge revision is unavailable; the PR head is reachable, analyzable, "
                "and verified as an ancestor of the acquired target revision"
            ),
        )
    return replace(
        pr,
        evidence_fix_sha=None,
        analysis_fix_sha=None,
        fix_resolution_policy="unresolvable",
        analysis_resolution_reason=(
            "neither the GitHub merge revision nor a safe ancestry-verified analyzable PR head "
            "is available"
        ),
    )


def _hash(data: Any) -> str:
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _lock_hash() -> str | None:
    lock = Path(__file__).resolve().parents[2] / "uv.lock"
    return hashlib.sha256(lock.read_bytes()).hexdigest() if lock.is_file() else None


def _input_material(
    cfg: Config,
    resolved_revision: str,
    pull_requests: list[PullRequest],
    offline: bool,
) -> dict[str, Any]:
    return {
        "effective_config": cfg.dictionary(),
        "software_version": __version__,
        "schema_version": SCHEMA_VERSION,
        "resolved_revision": resolved_revision,
        "pull_requests": [
            item.row() for item in sorted(pull_requests, key=lambda item: item.number)
        ],
        "dependency_lock_sha256": _lock_hash(),
        "mode": "offline" if offline else "live",
    }


def _prepare_output(output: Path, input_fingerprint: str, cfg: Config, force: bool) -> bool:
    """Prepare a run directory; return True when a completed run can be reused."""
    if not output.exists():
        output.mkdir(parents=True)
        return False
    if force:
        if output == Path("/") or len(output.parts) < 3:
            raise ExtractionError("refusing unsafe output deletion")
        shutil.rmtree(output)
        output.mkdir(parents=True)
        return False
    if not cfg.execution.resume:
        raise ExtractionError(f"output directory already exists: {output}; use --force or --resume")
    inputs_path = output / "provenance/stage-inputs.json"
    if not inputs_path.is_file():
        raise ExtractionError(
            "existing run has no stage input hashes; use --force after preserving it"
        )
    recorded = json.loads(inputs_path.read_text(encoding="utf-8"))
    if recorded.get("run_input_fingerprint") != input_fingerprint:
        raise ExtractionError(
            "restart-safe rerun refused: configuration, software, revision, API evidence, "
            "or dependency lock changed"
        )
    previous_hash = input_fingerprint
    recorded_stages = recorded.get("stages")
    if not isinstance(recorded_stages, dict):
        raise ExtractionError("restart-safe rerun refused: malformed stage input hashes")
    for stage in STAGES:
        if stage not in recorded_stages:
            continue
        expected = _hash(
            {"run_input_fingerprint": input_fingerprint, "stage": stage, "prior": previous_hash}
        )
        if recorded_stages[stage] != expected:
            raise ExtractionError(
                f"restart-safe rerun refused: stage input hash changed for {stage}"
            )
        previous_hash = expected
    if (output / "RUN_COMPLETE").is_file():
        validate(output)
        return True
    suffix = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    archive = output.with_name(f"{output.name}.failed-{suffix}")
    counter = 1
    while archive.exists():
        archive = output.with_name(f"{output.name}.failed-{suffix}-{counter}")
        counter += 1
    shutil.move(str(output), str(archive))
    output.mkdir(parents=True)
    return False


def mine(cfg: Config, *, offline: bool = False, force: bool = False) -> Path:
    output = resolve_relative(cfg.paths.output_dir, cfg)
    stage_time = datetime.now(UTC).isoformat()
    stages: dict[str, Any] = {}

    executable("git")
    cache_root = resolve_relative(cfg.paths.cache_dir, cfg)
    if offline:
        if not cfg.offline.repository_path:
            raise ExtractionError("offline.repository_path is required in offline mode")
        repo = resolve_relative(cfg.offline.repository_path, cfg)
        prs = _offline_prs(cfg)
    else:
        client = GitHubClient(cache_root / "api" if cfg.execution.api_cache else None)
        client.authenticate()
        client.rate_limit()
        prs = _live_prs(cfg, client)
        repo = acquire(cfg.project.repository, cache_root / "repositories")
    if not (repo / ".git").is_dir():
        raise ExtractionError(f"repository is not a Git worktree: {repo}")
    prs = [_resolve_fix(repo, item, cfg) for item in prs]
    resolved = revision(repo)
    input_material = _input_material(cfg, resolved, prs, offline)
    input_fingerprint = _hash(input_material)
    if _prepare_output(output, input_fingerprint, cfg, force):
        return output
    (output / "config").mkdir()
    submitted = cfg.submitted_text
    if submitted is None and cfg.source_path and cfg.source_path.is_file():
        submitted = cfg.source_path.read_text(encoding="utf-8")
    if submitted is None:
        raise ExtractionError("submitted configuration is unavailable")
    (output / "config/submitted.yml").write_text(submitted, encoding="utf-8")
    (output / "config/effective.yml").write_text(dump_yaml(cfg.dictionary()), encoding="utf-8")
    logger = RunLogger(output, cfg.execution.log_level)
    logger.emit(
        "INFO",
        "run_started",
        "mining run started",
        repository=cfg.project.repository,
        input_fingerprint=input_fingerprint,
    )
    stage_inputs: dict[str, str] = {}
    previous_hash = input_fingerprint

    def persist_stage_inputs() -> None:
        path = output / "provenance/stage-inputs.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "run_input_fingerprint": input_fingerprint,
                    "input_material": input_material,
                    "stages": stage_inputs,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    def done(name: str) -> None:
        nonlocal previous_hash
        stage_hash = _hash(
            {"run_input_fingerprint": input_fingerprint, "stage": name, "prior": previous_hash}
        )
        stage_inputs[name] = stage_hash
        previous_hash = stage_hash
        stages[name] = {
            "status": "complete",
            "completed_at": datetime.now(UTC).isoformat(),
            "input_hash": stage_hash,
        }
        persist_stage_inputs()
        logger.emit("INFO", "stage_complete", f"{name} completed", stage=name)

    for name in ("environment_preflight", "configuration_validation"):
        done(name)
    for name in ("github_authentication", "rate_limit"):
        done(name)
    for name in (
        "pull_request_discovery",
        "pull_request_resolution",
        "fix_commit_resolution",
        "repository_acquisition",
    ):
        done(name)
    data = RunData(pull_requests=prs)
    for pr in prs:
        if not pr.analysis_fix_sha:
            warning: dict[str, Any] = {
                "entity": f"PR {pr.number}",
                "warning": (
                    "no safe analysis fix revision: "
                    f"{pr.analysis_resolution_reason or 'unresolved'}"
                ),
            }
            data.warnings.append(warning)
            logger.emit("WARNING", "unresolved_fix", warning["warning"], entity=warning["entity"])
            continue
        try:
            result = candidates(
                repo,
                pr.analysis_fix_sha,
                scope=cfg.mining.szz_path_scope,
                exclude_tests=cfg.mining.exclude_tests,
                include_generated=cfg.mining.include_generated_files,
            )
            data.relations.extend(result.relations)
            data.exclusions.extend(result.exclusions)
        except Exception as exc:
            warning = {
                "entity": pr.analysis_fix_sha,
                "warning": f"SZZ failure: {type(exc).__name__}: {exc}",
            }
            data.warnings.append(warning)
            logger.emit("WARNING", "szz_failure", warning["warning"], entity=warning["entity"])
    data.relations = sorted(set(data.relations))
    done("bic_extraction")
    roles = {x.analysis_fix_sha: "fix_revision" for x in prs if x.analysis_fix_sha}
    roles.update({x.bic_commit_sha: "candidate_bic" for x in data.relations})
    for sha, role in sorted(roles.items()):
        try:
            commit, files, methods, exclusions = extract_revision(
                repo,
                sha,
                cfg.project.repository,
                role,
                exclude_tests=cfg.mining.exclude_tests,
                include_generated=cfg.mining.include_generated_files,
                include_message=cfg.privacy.include_commit_messages,
            )
            if commit and "commit" in cfg.mining.levels:
                data.commit_metrics.append(commit)
            if "file" in cfg.mining.levels:
                data.file_metrics.extend(files)
            if "method" in cfg.mining.levels:
                data.method_metrics.extend(methods)
            data.exclusions.extend(exclusions)
        except Exception as exc:
            warning = {"entity": sha, "warning": f"metric failure: {type(exc).__name__}: {exc}"}
            data.warnings.append(warning)
            logger.emit("WARNING", "metric_failure", warning["warning"], entity=sha)
    for name in (
        "commit_extraction",
        "file_extraction",
        "method_extraction",
        "relation_assembly",
    ):
        done(name)
    environment = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git": version("git"),
        "gh": "not used (offline)" if offline else version("gh"),
        "gobugminer": __version__,
        "run_started": stage_time,
        "run_finished": datetime.now(UTC).isoformat(),
        "pid": os.getpid(),
        "python_executable_name": Path(sys.executable).name,
    }
    done("output_writing")
    done("provenance_capture")
    write_outputs(
        output,
        data,
        repository=cfg.project.repository,
        resolved_revision=resolved,
        labels=cfg.project.bug_labels,
        effective_config=cfg.dictionary(),
        environment=environment,
        stages=stages,
        input_fingerprint=input_fingerprint,
        stage_inputs=stage_inputs,
    )
    validate(output, allow_incomplete=True)
    done("validation")
    done("final_summary")
    (output / "provenance/stages.json").write_text(
        json.dumps(stages, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    summary_path = output / "reports/summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["run_status"] = "complete"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "reports/summary.md").write_text(
        "# GoBugMiner run summary\n\n"
        + "\n".join(f"- {key}: {value}" for key, value in summary.items())
        + "\n",
        encoding="utf-8",
    )
    logger.emit(
        "INFO",
        "final_validation_started",
        "final outputs and checksums are ready for validation",
    )
    checksums(output)
    marker = output / "RUN_COMPLETE"
    marker.unlink(missing_ok=True)
    validate(output)
    marker.write_text("validated\n", encoding="utf-8")
    if not offline and not cfg.execution.repository_cache:
        repository_cache = cache_root / "repositories" / cfg.project.repository.replace("/", "__")
        if repository_cache.is_dir():
            shutil.rmtree(repository_cache)
    return output
