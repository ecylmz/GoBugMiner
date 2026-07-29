from pathlib import Path

import pytest

from gobugminer.config import (
    Config,
    Project,
    apply_overrides,
    direct_config,
    load_config,
    load_configs,
    validate_config,
)
from gobugminer.exceptions import ConfigurationError


@pytest.mark.parametrize("slug", ["owner", "../owner/repo", "owner/repo/extra", "owner repo/x"])
def test_invalid_repository_slug(slug: str) -> None:
    with pytest.raises(ConfigurationError):
        validate_config(Config("1", Project(slug, ["bug"])))


def test_unknown_config_key_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.yml"
    path.write_text(
        'schema_version: "1"\nproject:\n  repository: a/b\n  bug_labels: [bug]\nmagic: true\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="unknown top-level"):
        load_config(path)


def test_path_traversal_is_rejected() -> None:
    cfg = Config("1", Project("a/b", ["bug"]))
    cfg.paths.output_dir = "../escape"
    with pytest.raises(ConfigurationError, match="traversal"):
        validate_config(cfg)


def test_batch_configuration_expands_projects(tmp_path: Path) -> None:
    path = tmp_path / "batch.yml"
    path.write_text(
        """schema_version: "1"
projects:
  - repository: one/project
    bug_labels: [defect]
  - repository: two/project
    bug_labels: [bug]
    output_dir: ./custom
paths:
  output_dir: ./runs
  cache_dir: ./cache
execution:
  log_level: warning
""",
        encoding="utf-8",
    )
    configs = load_configs(path)
    assert [cfg.project.repository for cfg in configs] == ["one/project", "two/project"]
    assert configs[0].paths.output_dir == "runs/one__project"
    assert configs[1].paths.output_dir == "./custom"
    assert configs[0].execution.log_level == "WARNING"
    assert configs[0].submitted_text == path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "text",
    [
        'schema_version: "1"\nprojects: []\n',
        'schema_version: "1"\nprojects: [invalid]\n',
        'schema_version: "1"\nprojects:\n  - repository: a/b\n    bug_labels: [bug]\n    x: 1\n',
        'schema_version: "1"\nprojects:\n'
        "  - repository: a/b\n    bug_labels: [bug]\n"
        "  - repository: a/b\n    bug_labels: [bug]\n",
    ],
)
def test_invalid_batch_configuration_is_rejected(tmp_path: Path, text: str) -> None:
    path = tmp_path / "batch.yml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_configs(path)


def test_single_loader_rejects_batch(tmp_path: Path) -> None:
    path = tmp_path / "batch.yml"
    path.write_text('schema_version: "1"\nprojects: []\n', encoding="utf-8")
    with pytest.raises(ConfigurationError, match="batch"):
        load_config(path)


def test_direct_config_and_cli_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = direct_config("owner/repo", ["bug"])
    apply_overrides(
        cfg,
        levels=["commit", "file"],
        output_dir="./result",
        cache_dir="./cache",
        resume=False,
        log_level="debug",
        api_cache=False,
        repository_cache=False,
        since="2026-01-01T00:00:00Z",
        until="2026-02-01T00:00:00Z",
        max_prs=2,
    )
    assert cfg.paths.output_dir == "./result"
    assert cfg.execution.log_level == "DEBUG"
    assert cfg.execution.api_cache is False
    assert cfg.selection.since == "2026-01-01T00:00:00+00:00"
    assert cfg.submitted_text


def test_invalid_log_level_is_rejected() -> None:
    cfg = Config("1", Project("a/b", ["bug"]))
    cfg.execution.log_level = "verbose"
    with pytest.raises(ConfigurationError, match="log_level"):
        validate_config(cfg)


def test_invalid_szz_path_scope_is_rejected() -> None:
    cfg = Config("1", Project("a/b", ["bug"]))
    cfg.mining.szz_path_scope = "implicit"
    with pytest.raises(ConfigurationError, match="szz_path_scope"):
        validate_config(cfg)
