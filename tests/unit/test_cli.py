import json
from pathlib import Path

import pytest

import gobugminer.cli as cli
from gobugminer.cli import execute
from gobugminer.exceptions import (
    ConfigurationError,
    DependencyError,
    ExtractionError,
    GitHubError,
    RepositoryError,
    ValidationError,
)


def test_init_and_schema(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = tmp_path / "config.yml"
    assert execute(["init", "--output", str(config)]) == 0
    assert config.is_file()
    capsys.readouterr()
    assert execute(["schema", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "1"


def test_init_refuses_overwrite(tmp_path: Path) -> None:
    config = tmp_path / "config.yml"
    config.write_text("keep", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        execute(["init", "--output", str(config)])


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert execute(["version"]) == 0
    assert "GoBugMiner 1.0" in capsys.readouterr().out


def test_direct_mine_and_overrides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: list[object] = []

    def fake_mine(cfg: object, *, offline: bool, force: bool) -> Path:
        captured.append((cfg, offline, force))
        return tmp_path / "run"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "mine", fake_mine)
    assert (
        execute(
            [
                "mine",
                "--repo",
                "owner/repo",
                "--bug-label",
                "bug",
                "--levels",
                "commit,file",
                "--output",
                "./output",
                "--max-prs",
                "3",
                "--log-level",
                "DEBUG",
                "--resume",
            ]
        )
        == 0
    )
    cfg, offline, force = captured[0]
    assert cfg.project.repository == "owner/repo"
    assert cfg.mining.levels == ["commit", "file"]
    assert cfg.selection.max_prs == 3
    assert cfg.execution.resume is True
    assert offline is False and force is False
    assert str(tmp_path / "run") in capsys.readouterr().out


def test_direct_mine_requires_selection() -> None:
    with pytest.raises(ConfigurationError, match="requires"):
        execute(["mine", "--repo", "owner/repo"])


def test_markdown_schema_output(tmp_path: Path) -> None:
    output = tmp_path / "schema.md"
    assert execute(["schema", "--format", "markdown", "--output", str(output)]) == 0
    assert "# GoBugMiner schema" in output.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ConfigurationError("bad"), 2),
        (DependencyError("bad"), 3),
        (GitHubError("bad"), 4),
        (RepositoryError("bad"), 5),
        (ExtractionError("bad"), 6),
        (ValidationError("bad"), 7),
    ],
)
def test_main_maps_expected_failures(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    code: int,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(_argv: object = None) -> int:
        raise error

    monkeypatch.setattr(cli, "execute", fail)
    with pytest.raises(SystemExit) as caught:
        cli.main([])
    assert caught.value.code == code
    assert "gobugminer: bad" in capsys.readouterr().err
