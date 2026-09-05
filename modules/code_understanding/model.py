"""Structured representation of parsed source code.

Defines the CodeState contract produced by this module (language-agnostic,
parsed via tree-sitter) and consumed by downstream modules
(energy_detection, candidate_generation, ...).

This representation makes no energy claims.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class FunctionInfo:
    name: str
    start_line: int
    end_line: int
    arguments: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    complexity: int | None = None  # cyclomatic complexity, if measured


@dataclass
class ClassInfo:
    name: str
    start_line: int
    end_line: int
    methods: list[FunctionInfo] = field(default_factory=list)


@dataclass
class LoopInfo:
    kind: str  # "for" | "while" | "async_for"
    line: int


@dataclass
class CallInfo:
    name: str
    line: int
    argument_count: int


@dataclass
class CodeState:
    """JSON-compatible structured representation of one parsed source file."""

    language: str = "python"
    path: str = "<unknown>"
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    loops: list[LoopInfo] = field(default_factory=list)
    conditionals: int = 0
    function_calls: list[CallInfo] = field(default_factory=list)
    data_structures: list[str] = field(default_factory=list)
    io_operations: list[str] = field(default_factory=list)
    complexity: dict[str, int] = field(default_factory=dict)
    allocations: int = 0
    dependencies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to a plain JSON-compatible dict."""
        return asdict(self)
