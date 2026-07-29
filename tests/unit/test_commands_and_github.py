from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import gobugminer.commands as commands
import gobugminer.github.client as github_module
from gobugminer.exceptions import DependencyError, GitHubError, RepositoryError
from gobugminer.github.client import GitHubClient


def test_executable_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(commands.shutil, "which", lambda _name: None)
    with pytest.raises(DependencyError):
        commands.executable("missing")


def test_run_success_failure_and_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert commands.run(["git", "--version"])
    with pytest.raises(RepositoryError, match="failed"):
        commands.run(["git", "not-a-command"], cwd=tmp_path)

    def expired(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired("tool", 1)

    monkeypatch.setattr(commands.subprocess, "run", expired)
    with pytest.raises(RepositoryError, match="timed out"):
        commands.run(["tool"])


def test_json_output_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(commands, "run", lambda *_args, **_kwargs: "not json")
    with pytest.raises(RepositoryError, match="invalid JSON"):
        commands.json_output(["tool"])


def test_github_client_cache_and_auth(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(github_module, "executable", lambda _name: "/usr/bin/gh")

    def fake_run(args: list[str], **_kwargs: object) -> str:
        calls.append(args)
        return json.dumps({"resources": {}})

    monkeypatch.setattr(github_module, "run", fake_run)
    client = GitHubClient(tmp_path)
    client.authenticate()
    assert client.rate_limit() == {"resources": {}}
    assert client.rate_limit() == {"resources": {}}
    assert len([x for x in calls if "rate_limit" in x]) == 1


def test_paginated_issues(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(github_module, "executable", lambda _name: "gh")
    monkeypatch.setattr(
        github_module,
        "run",
        lambda *_args, **_kwargs: json.dumps([[{"number": 1}], [{"number": 2}]]),
    )
    assert [x["number"] for x in GitHubClient().issues_with_label("a/b", "bug")] == [1, 2]
    monkeypatch.setattr(github_module, "run", lambda *_args, **_kwargs: "bad")
    with pytest.raises(GitHubError, match="invalid paginated"):
        GitHubClient().issues_with_label("a/b", "bug")
