from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from gobugminer.exceptions import DependencyError, RepositoryError


def executable(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise DependencyError(f"required executable '{name}' was not found; install it and retry")
    return path


def run(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 300,
    error_type: type[Exception] = RepositoryError,
) -> str:
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise error_type(f"command timed out: {args[0]}") from exc
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise error_type(f"{args[0]} failed: {detail[:1000]}")
    return result.stdout


def json_output(args: list[str], *, timeout: int = 300) -> Any:
    text = run(args, timeout=timeout)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RepositoryError(f"{args[0]} returned invalid JSON") from exc
