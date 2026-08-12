"""Extract a stable public surface from Python stubs or source files."""

from __future__ import annotations

import ast
from pathlib import Path

from .surface import PublicMember


def extract(path: Path) -> set[PublicMember]:
    files = sorted(path.rglob("*.pyi")) or sorted(path.rglob("*.py"))
    members: set[PublicMember] = set()
    for file_path in files:
        module = ".".join(file_path.relative_to(path).with_suffix("").parts)
        tree = ast.parse(file_path.read_text(), filename=str(file_path))
        members.update(_members(tree.body, module))
    return members


def _members(nodes: list[ast.stmt], prefix: str) -> set[PublicMember]:
    result: set[PublicMember] = set()
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            path = f"{prefix}.{node.name}" if prefix else node.name
            result.add(PublicMember(path, "function", _signature(node), _required(node.args)))
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            class_path = f"{prefix}.{node.name}" if prefix else node.name
            result.add(PublicMember(class_path, "class", ""))
            result.update(_members(node.body, class_path))
    return result


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = node.args
    parts = [ast.unparse(arg.annotation) if arg.annotation else "Any" for arg in [*args.posonlyargs, *args.args]]
    parts.extend(f"*{arg.arg}" for arg in args.kwonlyargs)
    returns = ast.unparse(node.returns) if node.returns else "Any"
    return f"({','.join(parts)})->{returns}"


def _required(args: ast.arguments) -> bool | None:
    positional = [*args.posonlyargs, *args.args]
    return bool(len(positional) > len(args.defaults) or any(default is None for default in args.kw_defaults))
