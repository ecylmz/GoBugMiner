from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

GENERATED_RE = re.compile(r"^// Code generated .* DO NOT EDIT\.$")
SOURCE_CATEGORIES = (
    "production_go",
    "test_go",
    "generated_go",
    "vendor",
    "non_go",
    "missing_path",
    "unavailable_source",
)
SZZ_PATH_SCOPES = ("production_go", "all_changed")


@dataclass(frozen=True)
class ClassifiedSource:
    path: str
    source: str | None
    category: str


def resolved_path(modified_file: Any) -> str:
    value = (
        getattr(modified_file, "new_path", None)
        or getattr(modified_file, "old_path", None)
        or getattr(modified_file, "filename", None)
    )
    return str(value) if value else ""


def available_source(modified_file: Any) -> str | None:
    current = getattr(modified_file, "source_code", None)
    if current is not None:
        return str(current)
    previous = getattr(modified_file, "source_code_before", None)
    return str(previous) if previous is not None else None


def classify_source(path: str, source: str | None) -> str:
    if not path:
        return "missing_path"
    normalized = path.replace("\\", "/")
    if "/vendor/" in f"/{normalized}":
        return "vendor"
    if not normalized.endswith(".go"):
        return "non_go"
    if source is None:
        return "unavailable_source"
    if normalized.endswith("_test.go"):
        return "test_go"
    if any(GENERATED_RE.match(line) for line in source.splitlines()[:10]):
        return "generated_go"
    return "production_go"


def classify_modified_file(modified_file: Any) -> ClassifiedSource:
    path = resolved_path(modified_file)
    source = available_source(modified_file)
    return ClassifiedSource(path, source, classify_source(path, source))


def source_filter_accepts(
    category: str,
    *,
    exclude_tests: bool,
    include_generated: bool,
) -> bool:
    if category == "production_go":
        return True
    if category == "test_go":
        return not exclude_tests
    if category == "generated_go":
        return include_generated
    return False


def szz_scope_accepts(
    category: str,
    *,
    scope: str,
    exclude_tests: bool,
    include_generated: bool,
) -> bool:
    if scope == "all_changed":
        return category != "missing_path"
    return source_filter_accepts(
        category,
        exclude_tests=exclude_tests,
        include_generated=include_generated,
    )
