"""Per-language adapters for the tree-sitter based parser.

Each adapter bundles the pieces that differ between languages:

* the tree-sitter ``Language`` (grammar) and parser,
* which node types represent which concept (functions, classes, loops, ...),
* small extraction helpers for language-specific node shapes.

Adding a new language means implementing one more adapter here; the walker
in ``parser.py`` stays unchanged. Python is the first (and currently only)
adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import tree_sitter_python
from tree_sitter import Language, Parser

if TYPE_CHECKING:
    from collections.abc import Callable

    from tree_sitter import Node

try:
    from radon.complexity import cc_visit

except ImportError:
    cc_visit = None

# Common builtin call names treated as I/O operations (Python).
_IO_NAMES = frozenset({
    "open", "print", "input", "read", "readline", "readlines",
    "write", "writelines", "close",
})


@dataclass(frozen=True)
class LanguageAdapter:
    """Everything the generic walker needs for one language."""

    language: str
    grammar: Language

    # Node types per concept.
    function_types: frozenset[str]
    class_types: frozenset[str]
    loop_types: frozenset[str]          # value = base kind, e.g. "for" / "while"
    conditional_types: frozenset[str]
    call_types: frozenset[str]
    data_types: frozenset[str]          # literals + comprehensions -> allocations
    import_types: frozenset[str]
    wrapper_types: frozenset[str]       # definitions carrying decorators

    # Language-specific extraction rules.
    param_names: Callable[[Node | None], list[str]]
    call_name: Callable[[Node], str | None]
    call_arg_count: Callable[[Node], int]
    import_roots: Callable[[Node], list[str]]
    complexity: Callable[[str], dict[tuple[str, int], int]]

    io_names: frozenset[str] = _IO_NAMES
    parser: Parser = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "parser", Parser(self.grammar))


# --- python helpers ---------------------------------------------------------

def _node_text(node: Node | None) -> str | None:
    if node is None:
        return None
    return node.text.decode("utf-8", errors="replace")


def _first_identifier(node: Node) -> str | None:
    """Text of the first identifier anywhere under ``node``."""
    if node.type == "identifier":
        return _node_text(node)
    for child in node.named_children:
        found = _first_identifier(child)
        if found is not None:
            return found
    return None


def _python_param_names(parameters: Node | None) -> list[str]:
    """Extract argument names from a ``parameters`` node.

    Handles plain identifiers as well as typed/default/splat parameters,
    whose own first identifier is the parameter name.
    """
    if parameters is None:
        return []
    names = []
    for child in parameters.named_children:
        if child.type == "identifier":
            names.append(_node_text(child) or "")
        else:
            name = _first_identifier(child)
            if name is not None:
                names.append(name)
    return names


def _python_call_name(node: Node) -> str | None:
    """Resolve a ``call`` node to the called function's simple name.

    ``foo()`` -> "foo", ``math.sqrt()`` -> "sqrt", ``obj.attr()`` -> "attr".
    """
    callee = node.child_by_field_name("function")
    if callee is None:
        return None
    if callee.type == "identifier":
        return _node_text(callee)
    if callee.type == "attribute":
        attr = callee.child_by_field_name("attribute")
        return _node_text(attr) if attr is not None else None
    return None  # indirect call, e.g. f()()


def _python_call_arg_count(node: Node) -> int:
    args = node.child_by_field_name("arguments")
    return len(args.named_children) if args is not None else 0


def _python_import_roots(node: Node) -> list[str]:
    """Root module of each import in an import statement.

    ``import a.b, c`` -> ["a", "c"]; ``from a.b import x`` -> ["a"].
    """
    roots: list[str] = []
    if node.type == "import_statement":
        for child in node.named_children:
            if child.type in {"dotted_name", "aliased_import"}:
                root = _first_identifier(child)
                if root is not None:
                    roots.append(root)
    elif node.type == "import_from_statement":
        module = node.named_children[0] if node.named_children else None
        if module is not None and module.type == "dotted_name":
            root = _first_identifier(module)
            if root is not None:
                roots.append(root)
        elif module is not None and module.type == "relative_import":
            root = _first_identifier(module)  # package part of e.g. "..pkg.mod"
            if root is not None:
                roots.append(root)
    return roots


def _python_complexity(source: str) -> dict[tuple[str, int], int]:
    """Per-(function name, line) cyclomatic complexity via radon (optional)."""
    if cc_visit is None:
        return {}
    try:
        return {(block.name, block.lineno): block.complexity for block in cc_visit(source)}
    except Exception:
        return {}


def _build_python() -> LanguageAdapter:
    return LanguageAdapter(
        language="python",
        grammar=Language(tree_sitter_python.language()),
        function_types=frozenset({"function_definition"}),
        class_types=frozenset({"class_definition"}),
        loop_types=frozenset({"for_statement", "while_statement"}),
        conditional_types=frozenset({"if_statement", "elif_clause"}),
        call_types=frozenset({"call"}),
        data_types=frozenset({
            "list", "dictionary", "set", "tuple",
            "list_comprehension", "dictionary_comprehension",
            "set_comprehension", "generator_expression",
        }),
        import_types=frozenset({"import_statement", "import_from_statement"}),
        wrapper_types=frozenset({"decorated_definition"}),
        param_names=_python_param_names,
        call_name=_python_call_name,
        call_arg_count=_python_call_arg_count,
        import_roots=_python_import_roots,
        complexity=_python_complexity,
    )


ADAPTERS: dict[str, LanguageAdapter] = {"python": _build_python()}


def get_adapter(language: str) -> LanguageAdapter:
    """Look up an adapter, raising a clear error for unsupported languages."""
    try:
        return ADAPTERS[language]
    except KeyError:
        raise ValueError(_unsupported_message(language)) from None


def _unsupported_message(language: str) -> str:
    available = ", ".join(sorted(ADAPTERS))
    return f"Unsupported language {language!r}; available: {available}"
