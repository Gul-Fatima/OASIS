"""Language-agnostic adapters for the tree-sitter based parser.

Each adapter bundles the pieces that differ between languages:
- the tree-sitter Language (grammar) and parser,
- which node types represent which concept (read from JSON config),
- small extraction helpers for language-specific node shapes.

Adding a new language means:
1. Adding a JSON config file in configs/
2. Installing the tree-sitter grammar for that language
No Python code changes needed.

Based on: SMART-Dal/codegreen (MPL-2.0) config-driven approach.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .language_config import LanguageConfig, get_language_config_manager

if TYPE_CHECKING:
    from collections.abc import Callable
    from tree_sitter import Node

# Common builtin call names treated as I/O operations (Python).
_IO_NAMES = frozenset({
    "open", "print", "input", "read", "readline", "readlines",
    "write", "writelines", "close",
})


@dataclass
class LanguageAdapter:
    """Everything the generic walker needs for one language."""

    language: str

    # tree-sitter Language object (grammar)
    grammar: object = None  # tree_sitter.Language

    # Node types per concept (loaded from JSON config)
    function_types: frozenset[str] = field(default_factory=frozenset)
    class_types: frozenset[str] = field(default_factory=frozenset)
    loop_types: frozenset[str] = field(default_factory=frozenset)
    conditional_types: frozenset[str] = field(default_factory=frozenset)
    call_types: frozenset[str] = field(default_factory=frozenset)
    data_types: frozenset[str] = field(default_factory=frozenset)
    import_types: frozenset[str] = field(default_factory=frozenset)
    wrapper_types: frozenset[str] = field(default_factory=frozenset)

    # Language-specific extraction rules
    param_names: Callable = None
    call_name: Callable = None
    call_arg_count: Callable = None
    import_roots: Callable = None
    complexity: Callable = None

    io_names: frozenset[str] = _IO_NAMES


# --- Generic helpers (work for any tree-sitter language) ---

def _node_text(node: Node | None) -> str | None:
    if node is None:
        return None
    return node.text.decode("utf-8", errors="replace")


def _first_identifier(node: Node) -> str | None:
    """Text of the first identifier anywhere under node."""
    if node.type == "identifier":
        return _node_text(node)
    for child in node.named_children:
        found = _first_identifier(child)
        if found is not None:
            return found
    return None


# --- Python-specific helpers ---

def _python_param_names(parameters: Node | None) -> list[str]:
    """Extract argument names from a parameters node."""
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
    """Resolve a call node to the called function's simple name."""
    callee = node.child_by_field_name("function")
    if callee is None:
        return None
    if callee.type == "identifier":
        return _node_text(callee)
    if callee.type == "attribute":
        attr = callee.child_by_field_name("attribute")
        return _node_text(attr) if attr is not None else None
    return None


def _python_call_arg_count(node: Node) -> int:
    args = node.child_by_field_name("arguments")
    return len(args.named_children) if args is not None else 0


def _python_import_roots(node: Node) -> list[str]:
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
            root = _first_identifier(module)
            if root is not None:
                roots.append(root)
    return roots


def _python_complexity(source: str) -> dict[tuple[str, int], int]:
    try:
        from radon.complexity import cc_visit
        return {(block.name, block.lineno): block.complexity for block in cc_visit(source)}
    except Exception:
        return {}


# --- Generic helpers for any language ---

def _generic_param_names(parameters: Node | None) -> list[str]:
    """Generic parameter extraction — works for most C-like languages."""
    if parameters is None:
        return []
    names = []
    for child in parameters.named_children:
        if child.type == "identifier":
            names.append(_node_text(child) or "")
        elif child.type == "formal_parameter":
            # Java/C++ style: type + name
            name_child = child.child_by_field_name("name")
            if name_child:
                names.append(_node_text(name_child) or "")
            else:
                name = _first_identifier(child)
                if name:
                    names.append(name)
        else:
            name = _first_identifier(child)
            if name:
                names.append(name)
    return names


def _generic_call_name(node: Node) -> str | None:
    """Generic call name extraction."""
    # Try field-based first (Python-style)
    callee = node.child_by_field_name("function")
    if callee is not None:
        return _node_text(callee) if callee.type == "identifier" else _first_identifier(callee)

    # Try method_name field (Java/C++ style)
    name = node.child_by_field_name("name")
    if name is not None:
        return _node_text(name)

    # Fallback: first identifier
    return _first_identifier(node)


def _generic_call_arg_count(node: Node) -> int:
    args = node.child_by_field_name("arguments")
    if args is not None:
        return len(args.named_children)
    # Try argument_list (Java/C++ style)
    for child in node.named_children:
        if child.type == "argument_list":
            return len(child.named_children)
    return 0


def _generic_import_roots(node: Node) -> list[str]:
    """Generic import root extraction."""
    roots: list[str] = []
    # import_statement (Python)
    if node.type == "import_statement":
        for child in node.named_children:
            root = _first_identifier(child)
            if root:
                roots.append(root)
    # import_from_statement (Python)
    elif node.type == "import_from_statement":
        module = node.named_children[0] if node.named_children else None
        if module:
            root = _first_identifier(module)
            if root:
                roots.append(root)
    # import_declaration (Java/C++)
    elif node.type == "import_declaration":
        root = _first_identifier(node)
        if root:
            roots.append(root)
    # #include (C/C++)
    elif node.type == "preproc_include":
        root = _first_identifier(node)
        if root:
            roots.append(root)
    return roots


def _generic_complexity(source: str) -> dict[tuple[str, int], int]:
    """Generic complexity — tries radon, falls back to empty."""
    try:
        from radon.complexity import cc_visit
        return {(block.name, block.lineno): block.complexity for block in cc_visit(source)}
    except Exception:
        return {}


def _noop_complexity(source: str) -> dict[tuple[str, int], int]:
    """No-op for languages without radon support."""
    return {}


# --- Adapter builders ---

def _build_python() -> LanguageAdapter:
    """Build Python adapter from JSON config."""
    import tree_sitter_python
    from tree_sitter import Language, Parser

    mgr = get_language_config_manager()
    cfg = mgr.get_config("python")
    nt = cfg.node_types if cfg else {}
    grammar = Language(tree_sitter_python.language())

    return LanguageAdapter(
        language="python",
        grammar=grammar,
        function_types=frozenset(nt.get("function_types", ["function_definition"])),
        class_types=frozenset(nt.get("class_types", ["class_definition"])),
        loop_types=frozenset(nt.get("loop_types", ["for_statement", "while_statement"])),
        conditional_types=frozenset(nt.get("if_statement_types", ["if_statement", "elif_clause"])),
        call_types=frozenset({"call"}),
        data_types=frozenset({
            "list", "dictionary", "set", "tuple",
            "list_comprehension", "dictionary_comprehension",
            "set_comprehension", "generator_expression",
        }),
        import_types=frozenset(nt.get("import_after_node_types", []) or
                               ["import_statement", "import_from_statement"]),
        wrapper_types=frozenset({"decorated_definition"}),
        param_names=_python_param_names,
        call_name=_python_call_name,
        call_arg_count=_python_call_arg_count,
        import_roots=_python_import_roots,
        complexity=_python_complexity,
    )


def _build_java() -> LanguageAdapter:
    """Build Java adapter from JSON config."""
    mgr = get_language_config_manager()
    cfg = mgr.get_config("java")
    nt = cfg.node_types if cfg else {}
    grammar = _try_load_grammar("java")

    return LanguageAdapter(
        language="java",
        grammar=grammar,
        function_types=frozenset(nt.get("function_types", ["method_declaration", "constructor_declaration"])),
        class_types=frozenset(nt.get("class_types", ["class_declaration", "interface_declaration", "enum_declaration"])),
        loop_types=frozenset(nt.get("loop_types", ["for_statement", "while_statement", "do_statement", "enhanced_for_statement"])),
        conditional_types=frozenset(nt.get("if_statement_types", ["if_statement"])),
        call_types=frozenset({"method_invocation"}),
        data_types=frozenset({"array_initializer", "new_array_expression", "new_object_expression"}),
        import_types=frozenset({"import_declaration"}),
        wrapper_types=frozenset(),  # Java has no decorators
        param_names=_generic_param_names,
        call_name=_generic_call_name,
        call_arg_count=_generic_call_arg_count,
        import_roots=_generic_import_roots,
        complexity=_noop_complexity,
    )


def _build_c() -> LanguageAdapter:
    """Build C adapter from JSON config."""
    mgr = get_language_config_manager()
    cfg = mgr.get_config("c")
    nt = cfg.node_types if cfg else {}
    grammar = _try_load_grammar("c")

    return LanguageAdapter(
        language="c",
        grammar=grammar,
        function_types=frozenset(nt.get("function_types", ["function_definition"])),
        class_types=frozenset(nt.get("class_types", [])),
        loop_types=frozenset(nt.get("loop_types", ["for_statement", "while_statement", "do_statement"])),
        conditional_types=frozenset(nt.get("if_statement_types", ["if_statement"])),
        call_types=frozenset({"call_expression"}),
        data_types=frozenset({"compound_literal_expression", "cast_expression"}),
        import_types=frozenset({"preproc_include"}),
        wrapper_types=frozenset(),
        param_names=_generic_param_names,
        call_name=_generic_call_name,
        call_arg_count=_generic_call_arg_count,
        import_roots=_generic_import_roots,
        complexity=_noop_complexity,
    )


def _build_cpp() -> LanguageAdapter:
    """Build C++ adapter from JSON config."""
    mgr = get_language_config_manager()
    cfg = mgr.get_config("cpp")
    nt = cfg.node_types if cfg else {}
    grammar = _try_load_grammar("cpp")

    return LanguageAdapter(
        language="cpp",
        grammar=grammar,
        function_types=frozenset(nt.get("function_types", ["function_definition"])),
        class_types=frozenset(nt.get("class_types", ["class_specifier", "struct_specifier"])),
        loop_types=frozenset(nt.get("loop_types", ["for_statement", "while_statement", "do_statement"])),
        conditional_types=frozenset(nt.get("if_statement_types", ["if_statement"])),
        call_types=frozenset({"call_expression"}),
        data_types=frozenset({"new_expression", "new_expression", "compound_literal_expression"}),
        import_types=frozenset({"preproc_include"}),
        wrapper_types=frozenset(),
        param_names=_generic_param_names,
        call_name=_generic_call_name,
        call_arg_count=_generic_call_arg_count,
        import_roots=_generic_import_roots,
        complexity=_noop_complexity,
    )


def _build_javascript() -> LanguageAdapter:
    """Build JavaScript adapter from JSON config."""
    mgr = get_language_config_manager()
    cfg = mgr.get_config("javascript")
    nt = cfg.node_types if cfg else {}
    grammar = _try_load_grammar("javascript")

    return LanguageAdapter(
        language="javascript",
        grammar=grammar,
        function_types=frozenset(nt.get("function_types", ["function_declaration", "arrow_function", "function_expression", "method_definition"])),
        class_types=frozenset(nt.get("class_types", ["class_declaration"])),
        loop_types=frozenset(nt.get("loop_types", ["for_statement", "while_statement", "do_statement", "for_in_statement"])),
        conditional_types=frozenset(nt.get("if_statement_types", ["if_statement"])),
        call_types=frozenset({"call_expression"}),
        data_types=frozenset({"array", "object", "new_expression"}),
        import_types=frozenset({"import_statement", "import_declaration"}),
        wrapper_types=frozenset(),
        param_names=_generic_param_names,
        call_name=_generic_call_name,
        call_arg_count=_generic_call_arg_count,
        import_roots=_generic_import_roots,
        complexity=_noop_complexity,
    )


def _try_load_grammar(language: str):
    """Try to load tree-sitter grammar for a language. Returns None if not installed."""
    try:
        import tree_sitter
        if language == "java":
            import tree_sitter_java
            return tree_sitter.Language(tree_sitter_java.language())
        elif language == "c":
            import tree_sitter_c
            return tree_sitter.Language(tree_sitter_c.language())
        elif language == "cpp":
            import tree_sitter_cpp
            return tree_sitter.Language(tree_sitter_cpp.language())
        elif language == "javascript":
            import tree_sitter_javascript
            return tree_sitter.Language(tree_sitter_javascript.language())
    except ImportError:
        pass
    return None


# --- Registry ---

ADAPTERS: dict[str, LanguageAdapter] = {
    "python": _build_python(),
    "java": _build_java(),
    "c": _build_c(),
    "cpp": _build_cpp(),
    "javascript": _build_javascript(),
}


def get_adapter(language: str) -> LanguageAdapter:
    """Look up an adapter, raising a clear error for unsupported languages."""
    try:
        return ADAPTERS[language]
    except KeyError:
        raise ValueError(_unsupported_message(language)) from None


def get_supported_languages() -> list[str]:
    """Return list of languages with available adapters."""
    return sorted(ADAPTERS.keys())


def _unsupported_message(language: str) -> str:
    available = ", ".join(get_supported_languages())
    config_mgr = get_language_config_manager()
    config_langs = config_mgr.get_supported_languages()
    config_available = ", ".join(config_langs)

    msg = f"Unsupported language {language!r}; adapter available for: {available}"
    if language in config_langs and language not in ADAPTERS:
        msg += (f"\nNote: JSON config exists for {language!r} but no tree-sitter "
                f"grammar is installed. Install it with: pip install tree-sitter-{language}")
    return msg
