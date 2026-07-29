from __future__ import annotations

from pathlib import Path

import pytest

import gobugminer.repository.git as repository
from gobugminer.exceptions import RepositoryError


def test_acquire_clone_and_unshallow(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(repository, "executable", lambda name: name)

    def fake_run(args: list[str], **_kwargs: object) -> str:
        calls.append(args)
        if args[:3] == ["gh", "repo", "clone"]:
            target = Path(args[-1])
            (target / ".git").mkdir(parents=True)
        if args[:3] == ["git", "rev-parse", "--is-shallow-repository"]:
            return "true\n"
        return ""

    monkeypatch.setattr(repository, "run", fake_run)
    path = repository.acquire("owner/name", tmp_path)
    assert path.name == "owner__name"
    assert any("--unshallow" in args for args in calls)


def test_acquire_rejects_non_repo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(repository, "executable", lambda name: name)
    (tmp_path / "owner__name").mkdir()
    with pytest.raises(RepositoryError, match="not a Git repository"):
        repository.acquire("owner/name", tmp_path)


def test_revision_and_version(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(repository, "executable", lambda name: name)
    monkeypatch.setattr(
        repository,
        "run",
        lambda args, **_kwargs: "abc\n" if "rev-parse" in args else "git version 1\n",
    )
    assert repository.revision(tmp_path) == "abc"
    assert repository.version("git") == "git version 1"
