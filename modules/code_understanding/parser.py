"""Parse source into a structured CodeState using tree-sitter.

The walker is language-independent: it traverses the concrete syntax tree
and interprets node types through a per-language adapter (see ``adapters.py``).
Python is the first adapter; per-function cyclomatic complexity is added by
radon when available and omitted (None) otherwise.

This module makes no energy claims and never modifies source code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .adapters import LanguageAdapter, get_adapter
from .model import CallInfo, ClassInfo, CodeState, FunctionInfo, LoopInfo

if TYPE_CHECKING:
    from tree_sitter import Node

# node types -> base loop kind
_LOOP_KINDS = {"for_statement": "for", "while_statement": "while"}


def parse_code(source: str, path: str = "<unknown>", language: str = "python") -> CodeState:
    """Parse ``source`` into a CodeState.

    Raises ValueError with location details on syntax errors, or for an
    unsupported ``language``.
    """
    return _Walker(source, path, get_adapter(language)).parse()


class _Walker:
    """Stateful traversal of one parsed source file."""

    def __init__(self, source: str, path: str, adapter: LanguageAdapter) -> None:
        self.adapter = adapter
        self.root = adapter.parser.parse(source.encode("utf-8")).root_node
        self.state = CodeState(language=adapter.language, path=path)
        self.class_names = _top_level_class_names(self.root, adapter)
        self.complexities = adapter.complexity(source)
        self.decorators: dict[tuple, list[str]] = {}

    def parse(self) -> CodeState:
        """Walk the tree, filling and returning ``state``."""
        if self.root.has_error:
            raise ValueError(_syntax_error_message(self.root, self.state.path))
        for node in self.root.named_children:
            self._visit(node)
        self.state.complexity = _complexity_summary(self.state.functions)
        return self.state

    def _visit(self, node: Node) -> None:
        if node.type in self.adapter.wrapper_types:
            _register_decorators(node, self.adapter, self.decorators)
        self._dispatch(node)
        for child in node.named_children:
            self._visit(child)

    def _dispatch(self, node: Node) -> None:
        node_type = node.type
        if node_type in self.adapter.function_types:
            self.state.functions.append(
                _function_info(node, self.adapter, self.decorators, self.complexities)
            )
        elif node_type in self.adapter.class_types:
            self.state.classes.append(
                _class_info(node, self.adapter, self.decorators, self.complexities)
            )
        elif node_type in self.adapter.loop_types:
            kind = _loop_kind(node)
            self.state.loops.append(LoopInfo(kind=kind, line=node.start_point.row + 1))
        elif node_type in self.adapter.conditional_types:
            self.state.conditionals += 1
        elif node_type in self.adapter.call_types:
            self._record_call(node)
        elif node_type in self.adapter.data_types:
            self._record_data_structure(node)
        elif node_type in self.adapter.import_types:
            self.state.dependencies.extend(self.adapter.import_roots(node))

    def _record_call(self, node: Node) -> None:
        name = self.adapter.call_name(node)
        if name is None:
            return
        line = node.start_point.row + 1
        self.state.function_calls.append(
            CallInfo(name=name, line=line, argument_count=self.adapter.call_arg_count(node))
        )
        if name in self.adapter.io_names:
            self.state.io_operations.append(f"{name} (line {line})")
        if name in self.class_names:
            self.state.allocations += 1

    def _record_data_structure(self, node: Node) -> None:
        if node.type not in self.state.data_structures:
            self.state.data_structures.append(node.type)
        self.state.allocations += 1


# --- extraction helpers -----------------------------------------------------

def _name_of(node: Node) -> str | None:
    name = node.child_by_field_name("name")
    return name.text.decode("utf-8", errors="replace") if name is not None else None


def _function_info(
    node: Node,
    adapter: LanguageAdapter,
    decorators: dict[tuple, list[str]],
    complexities: dict[tuple[str, int], int],
) -> FunctionInfo:
    name = _name_of(node) or ""
    start_line = node.start_point.row + 1
    params = node.child_by_field_name("parameters")
    return FunctionInfo(
        name=name,
        start_line=start_line,
        end_line=node.end_point.row + 1,
        arguments=adapter.param_names(params),
        decorators=decorators.get(_node_key(node), []),
        complexity=complexities.get((name, start_line)),
    )


def _class_info(
    node: Node,
    adapter: LanguageAdapter,
    decorators: dict[tuple, list[str]],
    complexities: dict[tuple[str, int], int],
) -> ClassInfo:
    methods: list[FunctionInfo] = []
    body = node.child_by_field_name("body")
    if body is not None:
        for child in body.named_children:
            def_node: Node | None = None
            if child.type in adapter.function_types:
                def_node = child
            elif child.type in adapter.wrapper_types:
                def_node = _inner_definition(child, adapter)
            if def_node is not None:
                methods.append(_function_info(def_node, adapter, decorators, complexities))
    return ClassInfo(
        name=_name_of(node) or "",
        start_line=node.start_point.row + 1,
        end_line=node.end_point.row + 1,
        methods=methods,
    )


def _register_decorators(
    node: Node, adapter: LanguageAdapter, decorators: dict[tuple, list[str]]
) -> None:
    """Record decorator texts so the wrapped definition can pick them up later."""
    inner = _inner_definition(node, adapter)
    if inner is None:
        return
    texts = []
    for child in node.named_children:
        if child.type == "decorator":
            text = child.text.decode("utf-8", errors="replace")
            texts.append(text.lstrip("@").strip())
    decorators[_node_key(inner)] = texts


def _inner_definition(node: Node, adapter: LanguageAdapter) -> Node | None:
    """If ``node`` wraps a decorated function/class, return that definition."""
    for child in node.named_children:
        if child.type in adapter.function_types | adapter.class_types:
            return child
    return None


def _loop_kind(node: Node) -> str:
    kind = _LOOP_KINDS.get(node.type, node.type)
    # async for / async while carry an "async" keyword token up front.
    children = node.children
    if children and children[0].type == "async":
        kind = f"async_{kind}"
    return kind


def _node_key(node: Node) -> tuple:
    return (node.type, node.start_byte, node.end_byte)


def _top_level_class_names(root: Node, adapter: LanguageAdapter) -> set[str]:
    """Simple names of classes defined at module level (used to spot allocations)."""
    names: set[str] = set()
    for node in root.named_children:
        if node.type in adapter.class_types:
            name = _name_of(node)
        elif node.type in adapter.wrapper_types:
            inner = _inner_definition(node, adapter)
            if inner is None or inner.type not in adapter.class_types:
                continue
            name = _name_of(inner)
        else:
            continue
        if name:
            names.add(name)
    return names


def _syntax_error_message(root: Node, path: str) -> str:
    """Human-readable message for the first ERROR / missing node in the tree."""

    def find_error(node: Node) -> Node | None:
        if node.type in {"ERROR", "missing"}:
            return node
        for child in node.named_children:
            found = find_error(child)
            if found is not None:
                return found
        return None

    err = find_error(root)
    if err is not None and err.start_point.row >= 0:
        return f"Syntax error in {path} at line {err.start_point.row + 1}"
    return f"Syntax error in {path}"


def _complexity_summary(functions: list[FunctionInfo]) -> dict[str, int]:
    values = [f.complexity for f in functions if f.complexity is not None]
    if not values:
        return {}
    return {"measured": len(values), "max": max(values), "total": sum(values)}
