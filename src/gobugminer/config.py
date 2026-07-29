from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from gobugminer.constants import LEVELS
from gobugminer.exceptions import ConfigurationError
from gobugminer.source_filter import SZZ_PATH_SCOPES

REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
TOP_KEYS = {
    "schema_version",
    "project",
    "selection",
    "mining",
    "paths",
    "execution",
    "privacy",
    "offline",
}
BATCH_TOP_KEYS = (TOP_KEYS - {"project", "offline"}) | {"projects"}
PROJECT_KEYS = {"repository", "bug_labels"}
BATCH_PROJECT_KEYS = PROJECT_KEYS | {"output_dir", "offline"}


@dataclass
class Project:
    repository: str
    bug_labels: list[str]


@dataclass
class Selection:
    state: str = "closed"
    merged_only: bool = True
    since: str | None = None
    until: str | None = None
    max_prs: int | None = None


@dataclass
class Mining:
    levels: list[str] = field(default_factory=lambda: list(LEVELS))
    exclude_tests: bool = True
    include_generated_files: bool = False
    szz_engine: str = "pydriller"
    szz_path_scope: str = "production_go"


@dataclass
class Paths:
    output_dir: str = "./runs/output"
    cache_dir: str = "~/.cache/gobugminer"


@dataclass
class Execution:
    resume: bool = True
    api_cache: bool = True
    repository_cache: bool = True
    workers: int = 1
    log_level: str = "INFO"


@dataclass
class Privacy:
    include_commit_messages: bool = False
    include_author_names: bool = False
    include_author_emails: bool = False


@dataclass
class Offline:
    repository_path: str | None = None
    pull_requests_path: str | None = None


@dataclass
class Config:
    schema_version: str
    project: Project
    selection: Selection = field(default_factory=Selection)
    mining: Mining = field(default_factory=Mining)
    paths: Paths = field(default_factory=Paths)
    execution: Execution = field(default_factory=Execution)
    privacy: Privacy = field(default_factory=Privacy)
    offline: Offline = field(default_factory=Offline)
    source_path: Path | None = field(default=None, repr=False)
    submitted_text: str | None = field(default=None, repr=False)

    def dictionary(self) -> dict[str, Any]:
        result = asdict(self)
        result.pop("source_path", None)
        result.pop("submitted_text", None)
        return result


def _construct(cls: type[Any], raw: dict[str, Any], section: str) -> Any:
    allowed = set(cls.__dataclass_fields__)
    unknown = set(raw) - allowed
    if unknown:
        raise ConfigurationError(f"unknown {section} key(s): {', '.join(sorted(unknown))}")
    try:
        return cls(**raw)
    except TypeError as exc:
        raise ConfigurationError(f"invalid {section}: {exc}") from exc


def _datetime(value: str | None, name: str) -> str | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an ISO-8601 date-time") from exc


def _read_yaml(path: Path) -> tuple[dict[str, Any], str]:
    try:
        text = path.read_text(encoding="utf-8")
        raw = yaml.safe_load(text)
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"cannot read configuration: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigurationError("configuration root must be a mapping")
    return raw, text


def _config(raw: dict[str, Any], path: Path, submitted_text: str) -> Config:
    unknown = set(raw) - TOP_KEYS
    if unknown:
        raise ConfigurationError(f"unknown top-level key(s): {', '.join(sorted(unknown))}")
    if str(raw.get("schema_version")) != "1":
        raise ConfigurationError("schema_version must be '1'")
    if not isinstance(raw.get("project"), dict):
        raise ConfigurationError("project is required")
    cfg = Config(
        schema_version="1",
        project=_construct(Project, raw["project"], "project"),
        selection=_construct(Selection, raw.get("selection", {}), "selection"),
        mining=_construct(Mining, raw.get("mining", {}), "mining"),
        paths=_construct(Paths, raw.get("paths", {}), "paths"),
        execution=_construct(Execution, raw.get("execution", {}), "execution"),
        privacy=_construct(Privacy, raw.get("privacy", {}), "privacy"),
        offline=_construct(Offline, raw.get("offline", {}), "offline"),
        source_path=path.resolve(),
        submitted_text=submitted_text,
    )
    validate_config(cfg)
    return cfg


def load_config(path: Path) -> Config:
    raw, text = _read_yaml(path)
    if "projects" in raw:
        raise ConfigurationError("batch configuration requires the mine command")
    return _config(raw, path, text)


def load_configs(path: Path) -> list[Config]:
    raw, text = _read_yaml(path)
    if "projects" not in raw:
        return [_config(raw, path, text)]
    unknown = set(raw) - BATCH_TOP_KEYS
    if unknown:
        raise ConfigurationError(f"unknown batch key(s): {', '.join(sorted(unknown))}")
    if str(raw.get("schema_version")) != "1":
        raise ConfigurationError("schema_version must be '1'")
    projects = raw.get("projects")
    if not isinstance(projects, list) or not projects:
        raise ConfigurationError("projects must be a non-empty list")
    shared = {key: value for key, value in raw.items() if key not in {"projects"}}
    shared_paths = dict(shared.get("paths", {}))
    output_root = str(shared_paths.pop("output_dir", "./runs"))
    configs: list[Config] = []
    for index, project in enumerate(projects):
        if not isinstance(project, dict):
            raise ConfigurationError(f"projects[{index}] must be a mapping")
        project_unknown = set(project) - BATCH_PROJECT_KEYS
        if project_unknown:
            names = ", ".join(sorted(project_unknown))
            raise ConfigurationError(f"unknown projects[{index}] key(s): {names}")
        project_data = {key: project[key] for key in PROJECT_KEYS if key in project}
        repository = str(project_data.get("repository", ""))
        default_name = repository.replace("/", "__")
        output_dir = project.get("output_dir", str(Path(output_root) / default_name))
        document = {
            **shared,
            "project": project_data,
            "paths": {**shared_paths, "output_dir": output_dir},
        }
        if "offline" in project:
            document["offline"] = project["offline"]
        configs.append(_config(document, path, text))
    outputs = [resolve_relative(cfg.paths.output_dir, cfg) for cfg in configs]
    if len(outputs) != len(set(outputs)):
        raise ConfigurationError("batch projects resolve to duplicate output directories")
    return configs


def validate_config(cfg: Config) -> None:
    if not REPOSITORY_RE.fullmatch(cfg.project.repository):
        raise ConfigurationError("project.repository must be a public owner/name slug")
    if not cfg.project.bug_labels or any(not x.strip() for x in cfg.project.bug_labels):
        raise ConfigurationError("project.bug_labels must contain at least one non-empty label")
    invalid_levels = set(cfg.mining.levels) - set(LEVELS)
    if invalid_levels or not cfg.mining.levels:
        raise ConfigurationError(f"invalid mining levels: {sorted(invalid_levels)}")
    if cfg.mining.szz_path_scope not in SZZ_PATH_SCOPES:
        raise ConfigurationError(
            f"mining.szz_path_scope must be one of: {', '.join(SZZ_PATH_SCOPES)}"
        )
    if cfg.selection.state != "closed":
        raise ConfigurationError("version 1 supports selection.state='closed' only")
    if cfg.selection.max_prs is not None and cfg.selection.max_prs < 1:
        raise ConfigurationError("selection.max_prs must be positive")
    if cfg.execution.workers < 1:
        raise ConfigurationError("execution.workers must be positive")
    cfg.execution.log_level = cfg.execution.log_level.upper()
    if cfg.execution.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
        raise ConfigurationError("execution.log_level must be DEBUG, INFO, WARNING, or ERROR")
    cfg.selection.since = _datetime(cfg.selection.since, "selection.since")
    cfg.selection.until = _datetime(cfg.selection.until, "selection.until")
    if cfg.selection.since and cfg.selection.until:
        starts = datetime.fromisoformat(cfg.selection.since)
        ends = datetime.fromisoformat(cfg.selection.until)
        if starts > ends:
            raise ConfigurationError("selection.since must not be after selection.until")
    for label, value in (("output_dir", cfg.paths.output_dir), ("cache_dir", cfg.paths.cache_dir)):
        if "\x00" in value or any(part == ".." for part in Path(value).parts):
            raise ConfigurationError(f"paths.{label} must not contain traversal")


def resolve_relative(value: str, cfg: Config) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute() and cfg.source_path:
        path = cfg.source_path.parent / path
    return path.resolve()


def dump_yaml(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def direct_config(repository: str, bug_labels: list[str]) -> Config:
    output_dir = f"./runs/{repository.replace('/', '__')}"
    cfg = Config(
        schema_version="1",
        project=Project(repository=repository, bug_labels=bug_labels),
        paths=Paths(output_dir=output_dir),
        source_path=(Path.cwd() / "gobugminer-cli.yml").resolve(),
    )
    validate_config(cfg)
    cfg.submitted_text = dump_yaml(cfg.dictionary())
    return cfg


def apply_overrides(cfg: Config, **values: Any) -> Config:
    repository = values.get("repository")
    bug_labels = values.get("bug_labels")
    levels = values.get("levels")
    if repository is not None:
        cfg.project.repository = repository
    if bug_labels is not None:
        cfg.project.bug_labels = list(bug_labels)
    if levels is not None:
        cfg.mining.levels = list(levels)
    mapping = {
        "output_dir": (cfg.paths, "output_dir"),
        "cache_dir": (cfg.paths, "cache_dir"),
        "resume": (cfg.execution, "resume"),
        "log_level": (cfg.execution, "log_level"),
        "api_cache": (cfg.execution, "api_cache"),
        "repository_cache": (cfg.execution, "repository_cache"),
        "since": (cfg.selection, "since"),
        "until": (cfg.selection, "until"),
        "max_prs": (cfg.selection, "max_prs"),
    }
    for name, (section, attribute) in mapping.items():
        value = values.get(name)
        if value is not None:
            setattr(section, attribute, value)
    validate_config(cfg)
    return cfg


EXAMPLE_CONFIG = """schema_version: "1"
project:
  repository: "hashicorp/consul"
  bug_labels:
    - "type/bug"
selection:
  state: "closed"
  merged_only: true
  since: null
  until: null
  max_prs: 10
mining:
  levels: [commit, file, method]
  exclude_tests: true
  include_generated_files: false
  szz_engine: "pydriller"
  szz_path_scope: "production_go"
paths:
  output_dir: "./runs/consul"
  cache_dir: "~/.cache/gobugminer"
execution:
  resume: true
  api_cache: true
  repository_cache: true
  workers: 1
  log_level: INFO
privacy:
  include_commit_messages: false
  include_author_names: false
  include_author_emails: false
"""
