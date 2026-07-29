from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

import gobugminer.pipeline as pipeline_module
from gobugminer.cli import execute
from gobugminer.config import load_config
from gobugminer.exceptions import ExtractionError, ValidationError
from gobugminer.pipeline import mine
from gobugminer.validation.run import validate


def test_offline_pipeline(
    offline_case: tuple[Path, Path, str, str],
) -> None:
    config_path, _repo, fix, bic = offline_case
    output = mine(load_config(config_path), offline=True)
    assert (output / "RUN_COMPLETE").is_file()
    assert validate(output)["valid"]
    summary = json.loads((output / "reports/summary.json").read_text(encoding="utf-8"))
    assert summary["pull_request_count"] == 1
    assert summary["fix_commit_count"] == 1
    assert summary["bic_candidate_count"] >= 1
    assert summary["file_label_count"] == summary["file_metric_count"]
    assert summary["method_label_count"] == summary["method_metric_count"]
    with (output / "normalized/fix_bic_relations.csv").open(encoding="utf-8", newline="") as handle:
        relations = list(csv.DictReader(handle))
    assert any(row["fix_commit_sha"] == fix and row["bic_commit_sha"] == bic for row in relations)
    with (output / "reports/exclusions.csv").open(encoding="utf-8", newline="") as handle:
        exclusions = list(csv.DictReader(handle))
    assert any(row["category"] == "test_go" for row in exclusions)
    manifest = json.loads((output / "provenance/manifest.json").read_text(encoding="utf-8"))
    assert manifest["szz_path_scope"] == "production_go"
    assert manifest["excluded_szz_paths_by_category"]["test_go"] == 1
    for label_file in ("commit_labels.csv", "file_labels.csv", "method_labels.csv"):
        assert (output / "labels" / label_file).is_file()
    assert mine(load_config(config_path), offline=True) == output
    assert execute(["inspect", str(output)]) == 0
    events = [
        json.loads(line)
        for line in (output / "logs/events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert events[0]["event"] == "run_started"
    assert events[-1]["event"] == "final_validation_started"
    stage_inputs = json.loads((output / "provenance/stage-inputs.json").read_text(encoding="utf-8"))
    assert stage_inputs["run_input_fingerprint"]
    assert "bic_extraction" in stage_inputs["stages"]
    with (output / "metrics/methods.csv").open(encoding="utf-8", newline="") as handle:
        assert all(row["parse_failure"] == "False" for row in csv.DictReader(handle))
    checksum_index = (output / "provenance/checksums.sha256").read_text(encoding="utf-8")
    assert "RUN_COMPLETE" not in checksum_index
    assert "reports/validation.json" not in checksum_index


def test_completion_marker_is_written_after_final_validation(
    offline_case: tuple[Path, Path, str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path, _repo, _fix, _bic = offline_case
    real_validate = pipeline_module.validate
    final_validation_observed = False

    def observe_validation(
        root: Path,
        *,
        allow_incomplete: bool = False,
    ) -> dict[str, object]:
        nonlocal final_validation_observed
        if not allow_incomplete:
            final_validation_observed = True
            assert not (root / "RUN_COMPLETE").exists()
        return real_validate(root, allow_incomplete=allow_incomplete)

    monkeypatch.setattr(pipeline_module, "validate", observe_validation)
    output = mine(load_config(config_path), offline=True)
    assert final_validation_observed
    assert (output / "RUN_COMPLETE").is_file()


def test_final_validation_failure_leaves_no_completion_marker(
    offline_case: tuple[Path, Path, str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path, _repo, _fix, _bic = offline_case
    real_validate = pipeline_module.validate

    def fail_final_validation(
        root: Path,
        *,
        allow_incomplete: bool = False,
    ) -> dict[str, object]:
        if not allow_incomplete:
            assert not (root / "RUN_COMPLETE").exists()
            raise ValidationError("forced final validation failure")
        return real_validate(root, allow_incomplete=True)

    monkeypatch.setattr(pipeline_module, "validate", fail_final_validation)
    with pytest.raises(ValidationError, match="forced final validation failure"):
        mine(load_config(config_path), offline=True)
    assert not (config_path.parent / "run" / "RUN_COMPLETE").exists()


def test_corrupted_checksum_fails(
    offline_case: tuple[Path, Path, str, str],
) -> None:
    config_path, _repo, _fix, _bic = offline_case
    output = mine(load_config(config_path), offline=True)
    (output / "metrics/commits.csv").write_text("corrupt\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="checksum mismatch"):
        validate(output)


def test_offline_batch_pipeline(
    offline_case: tuple[Path, Path, str, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path, repo, _fix, _bic = offline_case
    submitted = config_path.read_text(encoding="utf-8")
    pull_requests = next(
        line.split(":", 1)[1].strip()
        for line in submitted.splitlines()
        if line.strip().startswith("pull_requests_path:")
    )
    batch = config_path.parent / "batch.yml"
    batch.write_text(
        f"""schema_version: "1"
projects:
  - repository: fixture/one
    bug_labels: [bug]
    output_dir: ./batch-one
    offline:
      repository_path: {repo}
      pull_requests_path: {pull_requests}
  - repository: fixture/two
    bug_labels: [bug]
    output_dir: ./batch-two
    offline:
      repository_path: {repo}
      pull_requests_path: {pull_requests}
paths:
  cache_dir: ./cache
""",
        encoding="utf-8",
    )
    assert execute(["mine", "--config", str(batch), "--offline"]) == 0
    printed = capsys.readouterr().out
    for name in ("batch-one", "batch-two"):
        output = batch.parent / name
        assert str(output) in printed
        assert validate(output)["valid"]


def test_resume_rejects_changed_configuration(
    offline_case: tuple[Path, Path, str, str],
) -> None:
    config_path, _repo, _fix, _bic = offline_case
    mine(load_config(config_path), offline=True)
    changed = load_config(config_path)
    changed.project.bug_labels = ["different"]
    with pytest.raises(ExtractionError, match="restart-safe rerun"):
        mine(changed, offline=True)


def test_resume_preserves_incomplete_attempt(
    offline_case: tuple[Path, Path, str, str],
) -> None:
    config_path, _repo, _fix, _bic = offline_case
    output = mine(load_config(config_path), offline=True)
    (output / "RUN_COMPLETE").unlink()
    rerun = mine(load_config(config_path), offline=True)
    assert rerun == output
    assert (output / "RUN_COMPLETE").is_file()
    archives = list(output.parent.glob(f"{output.name}.failed-*"))
    assert len(archives) == 1
    assert (archives[0] / "logs/events.jsonl").is_file()


def test_resume_rejects_corrupted_stage_hash(
    offline_case: tuple[Path, Path, str, str],
) -> None:
    config_path, _repo, _fix, _bic = offline_case
    output = mine(load_config(config_path), offline=True)
    path = output / "provenance/stage-inputs.json"
    stage_inputs = json.loads(path.read_text(encoding="utf-8"))
    stage_inputs["stages"]["bic_extraction"] = "0" * 64
    path.write_text(json.dumps(stage_inputs), encoding="utf-8")
    with pytest.raises(ExtractionError, match="stage input hash changed"):
        mine(load_config(config_path), offline=True)


def test_restart_after_failure_preserves_attempt_without_duplicate_rows(
    offline_case: tuple[Path, Path, str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path, _repo, _fix, _bic = offline_case
    real_validate = pipeline_module.validate
    failed = False

    def fail_once(
        root: Path,
        *,
        allow_incomplete: bool = False,
    ) -> dict[str, object]:
        nonlocal failed
        if not allow_incomplete and not failed:
            failed = True
            raise ValidationError("one-time final failure")
        return real_validate(root, allow_incomplete=allow_incomplete)

    monkeypatch.setattr(pipeline_module, "validate", fail_once)
    with pytest.raises(ValidationError, match="one-time final failure"):
        mine(load_config(config_path), offline=True)
    output = mine(load_config(config_path), offline=True)
    assert (output / "RUN_COMPLETE").is_file()
    archives = list(output.parent.glob(f"{output.name}.failed-*"))
    assert len(archives) == 1
    with (output / "normalized/fix_bic_relations.csv").open(encoding="utf-8", newline="") as handle:
        relations = list(csv.DictReader(handle))
    relation_keys = {
        (row["fix_commit_sha"], row["bic_commit_sha"], row["file_path"]) for row in relations
    }
    assert len(relations) == len(relation_keys)
