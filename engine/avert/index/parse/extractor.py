"""Tree-sitter call site extraction (SPEC §8.1 step 2).

Resolves call expressions found by index/candidates.py into typed CallSite
records: matches the callee's dotted attribute/member path against the
controlled vocabulary (avert.vocabulary), then classifies the "model"
argument's value_binding (SPEC §6.1: literal / dynamic / absent).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import tree_sitter_python as tsp
import tree_sitter_typescript as tsts
from tree_sitter import Language, Node, Parser, Query, QueryCursor

from avert import vocabulary
from avert.models.call_site_schema import CallSite
from avert.models.surface_id_schema import SurfaceID

_QUERIES_DIR = Path(__file__).parent / "queries"

_PY_LANGUAGE = Language(tsp.language())
_TS_LANGUAGE = Language(tsts.language_typescript())
_TSX_LANGUAGE = Language(tsts.language_tsx())

_TS_QUERY_TEXT = (_QUERIES_DIR / "typescript.scm").read_text()

_PY_QUERY = Query(_PY_LANGUAGE, (_QUERIES_DIR / "python.scm").read_text())
_TS_QUERY = Query(_TS_LANGUAGE, _TS_QUERY_TEXT)
_TSX_QUERY = Query(_TSX_LANGUAGE, _TS_QUERY_TEXT)

_LANGUAGE_CONFIG = {
    "python": (_PY_LANGUAGE, _PY_QUERY),
    "typescript": (_TS_LANGUAGE, _TS_QUERY),
}


def extract_call_sites(
    *,
    file_path: str,
    language: str,
    source: bytes,
    repo: str,
    commit_sha: str | None,
) -> list[CallSite]:
    """Parses `source` and returns every CallSite whose callee resolves
    against the controlled vocabulary. Non-matching calls are silently
    dropped — SPEC §8.1's funnel narrows here, it doesn't flag rejects."""
    if language == "typescript" and file_path.endswith(".tsx"):
        # tree-sitter-typescript ships separate TS and TSX grammars; the
        # plain TS grammar can't parse JSX and silently drops call sites
        # in any .tsx file that uses it.
        ts_language, query = _TSX_LANGUAGE, _TSX_QUERY
    else:
        ts_language, query = _LANGUAGE_CONFIG[language]
    parser = Parser(ts_language)
    tree = parser.parse(source)
    file_hash = hashlib.sha256(source).hexdigest()

    cursor = QueryCursor(query)
    matches = cursor.matches(tree.root_node)

    call_sites: list[CallSite] = []
    for _pattern_idx, captures in matches:
        expr = captures["call.expr"][0]
        callee = captures["call.callee"][0]
        dotted_path = _text(callee, source).replace("\n", "").replace(" ", "")

        surface_match = vocabulary.match_callee(dotted_path)
        if surface_match is None:
            continue

        args_node = expr.child_by_field_name("arguments")
        if language == "python":
            value_binding, value = _python_model_arg(args_node, source)
        else:
            value_binding, value = _ts_model_arg(args_node, source)

        call_sites.append(
            CallSite(
                surface=SurfaceID(
                    provider=surface_match.provider,
                    resource=surface_match.resource,
                    operation=surface_match.operation,
                    field_path="model",
                    value=value,
                ),
                repo=repo,
                commit_sha=commit_sha,
                file_path=file_path,
                line_start=expr.start_point[0] + 1,
                line_end=expr.end_point[0] + 1,
                language=language,
                api_version=None,
                value_binding=value_binding,
                # A match on an ambiguous (generic-name) resource like
                # "messages" is real but weaker evidence than a distinctive
                # multi-segment chain — don't claim full confidence for it.
                confidence=0.6 if surface_match.ambiguous else 1.0,
                extractor=f"tree_sitter.{language}",
                file_content_hash=file_hash,
            )
        )
    return call_sites


def _text(node: Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


# --- Python "model" keyword argument classification ---

_PY_STRING_PREFIX_RE = re.compile(r"^[a-zA-Z]*")


def _python_model_arg(args_node: Node | None, source: bytes) -> tuple[str, str | None]:
    if args_node is None:
        return "absent", None
    for child in args_node.named_children:
        if child.type != "keyword_argument":
            continue
        name_node = child.child_by_field_name("name")
        if name_node is None or _text(name_node, source) != "model":
            continue
        value_node = child.child_by_field_name("value")
        return _classify_python_value(value_node, source)
    return "absent", None


def _classify_python_value(value_node: Node | None, source: bytes) -> tuple[str, str | None]:
    if value_node is None:
        return "absent", None
    if value_node.type == "string":
        has_interpolation = any(c.type == "interpolation" for c in value_node.children)
        if has_interpolation:
            return "dynamic", None
        text = _text(value_node, source)
        prefix_end = _PY_STRING_PREFIX_RE.match(text).end()
        body = text[prefix_end:]
        for quote in ('"""', "'''", '"', "'"):
            if body.startswith(quote) and body.endswith(quote) and len(body) >= 2 * len(quote):
                return "literal", body[len(quote) : -len(quote)]
        return "dynamic", None
    return "dynamic", None


# --- TypeScript "model" property classification ---


def _ts_model_arg(args_node: Node | None, source: bytes) -> tuple[str, str | None]:
    if args_node is None:
        return "absent", None
    for arg in args_node.named_children:
        if arg.type != "object":
            continue
        for prop in arg.named_children:
            if prop.type != "pair":
                continue
            key_node = prop.child_by_field_name("key")
            if key_node is None:
                continue
            key_text = _text(key_node, source).strip("'\"")
            if key_text != "model":
                continue
            value_node = prop.child_by_field_name("value")
            return _classify_ts_value(value_node, source)
    return "absent", None


def _classify_ts_value(value_node: Node | None, source: bytes) -> tuple[str, str | None]:
    if value_node is None:
        return "absent", None
    if value_node.type == "string":
        text = _text(value_node, source)
        return "literal", text[1:-1]
    if value_node.type == "template_string":
        has_substitution = any(c.type == "template_substitution" for c in value_node.children)
        if not has_substitution:
            text = _text(value_node, source)
            return "literal", text[1:-1]
        return "dynamic", None
    return "dynamic", None
