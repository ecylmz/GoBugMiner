from __future__ import annotations

import re

import tree_sitter_go
from tree_sitter import Language, Node, Parser

from gobugminer.source_filter import classify_source, source_filter_accepts


def _node_text(source_bytes: bytes, node: Node) -> str:
    return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def classify(path: str, source: str | None) -> tuple[bool, str]:
    category = classify_source(path, source)
    return (
        source_filter_accepts(
            category,
            exclude_tests=True,
            include_generated=False,
        ),
        category,
    )


def go_counts(
    source: str | None,
    *,
    wrap_declaration: bool = False,
) -> dict[str, int | bool]:
    names = {
        "struct_count": 0,
        "interface_count": 0,
        "loop_count": 0,
        "error_handling_count": 0,
        "goroutine_count": 0,
        "channel_count": 0,
        "defer_count": 0,
        "context_usage_count": 0,
        "json_tag_count": 0,
        "variadic_function_count": 0,
        "pointer_receiver_count": 0,
    }
    if not source:
        return {**names, "parse_failure": False}
    try:
        parsed_source = f"package fixture\n{source}\n" if wrap_declaration else source
        source_bytes = parsed_source.encode("utf-8")
        parser = Parser(Language(tree_sitter_go.language()))
        tree = parser.parse(source_bytes)

        def walk(node: Node) -> None:
            kind = node.type
            text = _node_text(source_bytes, node)
            if kind == "struct_type":
                names["struct_count"] += 1
            elif kind == "interface_type":
                names["interface_count"] += 1
            elif kind == "for_statement":
                names["loop_count"] += 1
            elif kind == "defer_statement":
                names["defer_count"] += 1
            elif kind == "go_statement":
                names["goroutine_count"] += 1
            elif kind == "channel_type":
                names["channel_count"] += 1
            elif kind == "if_statement" and re.search(r"\berr\b", text):
                names["error_handling_count"] += 1
            elif kind in {"function_declaration", "method_declaration", "method_elem"}:
                if "context.Context" in text:
                    names["context_usage_count"] += 1
                if "..." in text:
                    names["variadic_function_count"] += 1
                if kind == "method_declaration" and re.search(r"func\s*\([^)]*\*", text):
                    names["pointer_receiver_count"] += 1
            elif kind == "raw_string_literal" and "json:" in text:
                names["json_tag_count"] += 1
            for child in node.children:
                walk(child)

        walk(tree.root_node)
        return {**names, "parse_failure": tree.root_node.has_error}
    except Exception:
        return {**names, "parse_failure": True}
