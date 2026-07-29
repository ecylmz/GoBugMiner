from __future__ import annotations

from pathlib import Path

from gobugminer.commands import executable, run
from gobugminer.exceptions import RepositoryError


def acquire(repository: str, cache_root: Path) -> Path:
    executable("git")
    gh = executable("gh")
    owner, name = repository.split("/", 1)
    target = cache_root / f"{owner}__{name}"
    cache_root.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        run([gh, "repo", "clone", repository, str(target)], timeout=1800)
    elif not (target / ".git").is_dir():
        raise RepositoryError(f"cache target is not a Git repository: {target}")
    run(["git", "fetch", "--all", "--tags", "--prune"], cwd=target, timeout=1800)
    shallow = run(["git", "rev-parse", "--is-shallow-repository"], cwd=target).strip()
    if shallow == "true":
        run(["git", "fetch", "--unshallow"], cwd=target, timeout=1800)
    return target


def revision(repo: Path, ref: str = "HEAD") -> str:
    return run(["git", "rev-parse", "--verify", f"{ref}^{{commit}}"], cwd=repo).strip()


def version(executable_name: str) -> str:
    exe = executable(executable_name)
    return run([exe, "--version"]).splitlines()[0]
