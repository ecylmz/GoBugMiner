from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, cast

from gobugminer.commands import executable, run
from gobugminer.exceptions import GitHubError


class GitHubClient:
    def __init__(self, cache_dir: Path | None = None) -> None:
        self.gh = executable("gh")
        self.cache_dir = cache_dir

    def authenticate(self) -> None:
        run([self.gh, "auth", "status"], error_type=GitHubError)

    def rate_limit(self) -> dict[str, Any]:
        return cast(dict[str, Any], self.api("rate_limit"))

    def api(self, endpoint: str, *, fields: dict[str, str] | None = None) -> Any:
        cache_path = None
        key = endpoint.replace("/", "_")
        if fields:
            key += "_" + "_".join(f"{k}-{v}" for k, v in sorted(fields.items()))
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path = self.cache_dir / f"{key}.json"
            if cache_path.exists():
                return json.loads(cache_path.read_text(encoding="utf-8"))
        args = [
            self.gh,
            "api",
            "--method",
            "GET",
            "-H",
            "Accept: application/vnd.github+json",
            "-H",
            "X-GitHub-Api-Version: 2022-11-28",
            endpoint,
        ]
        for name, value in (fields or {}).items():
            args.extend(["-f", f"{name}={value}"])
        for attempt in range(3):
            try:
                payload = json.loads(run(args, error_type=GitHubError, timeout=120))
                break
            except GitHubError:
                if attempt == 2:
                    raise
                time.sleep(2**attempt)
        if cache_path:
            cache_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        return payload

    def issues_with_label(self, repository: str, label: str) -> list[dict[str, Any]]:
        owner, name = repository.split("/", 1)
        args = [
            self.gh,
            "api",
            "--method",
            "GET",
            "--paginate",
            "--slurp",
            f"repos/{owner}/{name}/issues",
            "-f",
            "state=closed",
            "-f",
            f"labels={label}",
            "-f",
            "per_page=100",
        ]
        try:
            pages = json.loads(run(args, error_type=GitHubError, timeout=300))
        except json.JSONDecodeError as exc:
            raise GitHubError("gh returned invalid paginated issue JSON") from exc
        return [item for page in pages for item in page]
