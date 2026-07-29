from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from gobugminer import SCHEMA_VERSION, __version__
from gobugminer.config import (
    EXAMPLE_CONFIG,
    apply_overrides,
    direct_config,
    dump_yaml,
    load_configs,
)
from gobugminer.constants import ExitCode
from gobugminer.exceptions import (
    ConfigurationError,
    DependencyError,
    ExtractionError,
    GitHubError,
    GoBugMinerError,
    RepositoryError,
    ValidationError,
)
from gobugminer.outputs.schemas import SCHEMAS, markdown
from gobugminer.pipeline import mine
from gobugminer.validation.run import validate


def _git_revision() -> str:
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["git", "rev-parse", "--short=12", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="gobugminer")
    root.add_argument("--debug", action="store_true", help="show full tracebacks")
    commands = root.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="create an example configuration")
    init.add_argument("--output", type=Path, default=Path("gobugminer.yml"))
    init.add_argument("--force", action="store_true")
    mining = commands.add_parser("mine", help="execute the mining pipeline")
    mining.add_argument("--config", type=Path)
    mining.add_argument("--repo")
    mining.add_argument("--bug-label", action="append", dest="bug_labels")
    mining.add_argument("--levels", help="comma-separated: commit,file,method")
    mining.add_argument("--output", dest="output_dir")
    mining.add_argument("--cache-dir")
    mining.add_argument(
        "--resume",
        action="store_true",
        default=None,
        help="reuse a validated matching run or preserve and restart an incomplete run",
    )
    mining.add_argument("--force", action="store_true")
    mining.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    mining.add_argument("--offline", action="store_true")
    mining.add_argument("--since")
    mining.add_argument("--until")
    mining.add_argument("--max-prs", type=int, help="sampling/debugging only")
    mining.add_argument("--keep-api-cache", action="store_true", default=None)
    mining.add_argument("--keep-repository-cache", action="store_true", default=None)
    check = commands.add_parser("validate", help="validate a run directory")
    check.add_argument("run_directory", type=Path)
    inspect = commands.add_parser("inspect", help="print a run summary")
    inspect.add_argument("run_directory", type=Path)
    schema = commands.add_parser("schema", help="print or export schemas")
    schema.add_argument("--format", choices=("json", "markdown"), default="markdown")
    schema.add_argument("--output", type=Path)
    commands.add_parser("version", help="print version information")
    return root


def execute(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "init":
        if args.output.exists() and not args.force:
            raise ConfigurationError(f"{args.output} exists; use --force to replace it")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(EXAMPLE_CONFIG, encoding="utf-8")
        print(args.output)
    elif args.command == "mine":
        if args.config:
            configs = load_configs(args.config)
        else:
            if not args.repo or not args.bug_labels:
                raise ConfigurationError(
                    "mine requires --config or both --repo and at least one --bug-label"
                )
            configs = [direct_config(args.repo, args.bug_labels)]
        if len(configs) > 1 and any((args.repo, args.bug_labels, args.output_dir)):
            raise ConfigurationError(
                "--repo, --bug-label, and --output cannot override a batch configuration"
            )
        levels = args.levels.split(",") if args.levels else None
        outputs = []
        for cfg in configs:
            apply_overrides(
                cfg,
                repository=args.repo,
                bug_labels=args.bug_labels,
                levels=levels,
                output_dir=args.output_dir,
                cache_dir=args.cache_dir,
                resume=args.resume,
                log_level=args.log_level,
                api_cache=args.keep_api_cache,
                repository_cache=args.keep_repository_cache,
                since=args.since,
                until=args.until,
                max_prs=args.max_prs,
            )
            if not args.config:
                cfg.submitted_text = dump_yaml(cfg.dictionary())
            outputs.append(mine(cfg, offline=args.offline, force=args.force))
        print("\n".join(str(output) for output in outputs))
    elif args.command == "validate":
        report = validate(args.run_directory.resolve())
        print(json.dumps(report, sort_keys=True))
    elif args.command == "inspect":
        path = args.run_directory / "reports/summary.json"
        if not path.is_file():
            raise ValidationError(f"summary not found: {path}")
        print(path.read_text(encoding="utf-8"), end="")
    elif args.command == "schema":
        content = (
            json.dumps({"schema_version": SCHEMA_VERSION, "tables": SCHEMAS}, indent=2) + "\n"
            if args.format == "json"
            else markdown()
        )
        if args.output:
            args.output.write_text(content, encoding="utf-8")
        else:
            print(content, end="")
    elif args.command == "version":
        print(f"GoBugMiner {__version__}")
        print(f"Python {platform.python_version()}")
        print(f"Schema {SCHEMA_VERSION}")
        print(f"Git {_git_revision()}")
    return int(ExitCode.SUCCESS)


def main(argv: Sequence[str] | None = None) -> None:
    debug = "--debug" in (argv or sys.argv[1:])
    try:
        raise SystemExit(execute(argv))
    except GoBugMinerError as exc:
        if debug:
            raise
        if isinstance(exc, ConfigurationError):
            code = ExitCode.USAGE
        elif isinstance(exc, DependencyError):
            code = ExitCode.DEPENDENCY
        elif isinstance(exc, GitHubError):
            code = ExitCode.GITHUB
        elif isinstance(exc, RepositoryError):
            code = ExitCode.REPOSITORY
        elif isinstance(exc, ValidationError):
            code = ExitCode.VALIDATION
        elif isinstance(exc, ExtractionError):
            code = ExitCode.EXTRACTION
        else:
            code = ExitCode.INTERNAL
        print(f"gobugminer: {exc}", file=sys.stderr)
        raise SystemExit(int(code)) from exc
