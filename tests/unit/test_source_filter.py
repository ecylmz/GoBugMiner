from __future__ import annotations

from types import SimpleNamespace

import pytest

from gobugminer.source_filter import (
    classify_modified_file,
    classify_source,
    source_filter_accepts,
    szz_scope_accepts,
)


@pytest.mark.parametrize(
    ("path", "source", "category"),
    [
        ("main.go", "package main\n", "production_go"),
        ("main_test.go", "package main\n", "test_go"),
        (
            "generated.go",
            "// Code generated fixture. DO NOT EDIT.\npackage main\n",
            "generated_go",
        ),
        ("vendor/example/main.go", "package main\n", "vendor"),
        ("README.md", "# readme\n", "non_go"),
        ("", "package main\n", "missing_path"),
        ("deleted.go", None, "unavailable_source"),
    ],
)
def test_source_categories(path: str, source: str | None, category: str) -> None:
    assert classify_source(path, source) == category


def test_deleted_file_uses_previous_source_and_path() -> None:
    modified = SimpleNamespace(
        new_path=None,
        old_path="old.go",
        filename="old.go",
        source_code=None,
        source_code_before="package old\n",
    )
    classified = classify_modified_file(modified)
    assert classified.path == "old.go"
    assert classified.source == "package old\n"
    assert classified.category == "production_go"


def test_policy_acceptance_is_explicit() -> None:
    assert source_filter_accepts("production_go", exclude_tests=True, include_generated=False)
    assert not source_filter_accepts("test_go", exclude_tests=True, include_generated=False)
    assert source_filter_accepts("test_go", exclude_tests=False, include_generated=False)
    assert source_filter_accepts("generated_go", exclude_tests=True, include_generated=True)
    assert szz_scope_accepts(
        "non_go",
        scope="all_changed",
        exclude_tests=True,
        include_generated=False,
    )
    assert not szz_scope_accepts(
        "missing_path",
        scope="all_changed",
        exclude_tests=True,
        include_generated=False,
    )
