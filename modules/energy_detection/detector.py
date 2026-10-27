"""Rule-based energy smell detection.

Maps patterns found in a parsed ``CodeState`` onto the Energy Smells taxonomy
(``taxonomy.py``). Detection is a *hypothesis*, not proof of energy
inefficiency: nothing here measures energy, and every detection carries the
subcategory it maps to so the claim can be audited against CLAUDE.md.

Each rule is a small function returning detections, so rules can be added,
tested and reasoned about individually.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Callable

from modules.code_understanding.model import CodeState
from modules.energy_detection.taxonomy import get_category, get_subcategory

Detection = dict[str, Any]
Rule = Callable[[CodeState, str, list[str]], list[Detection]]

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


# ============================================================
# HELPERS
# ============================================================

def _function_lines(state: CodeState, source_lines: list[str], func: Any) -> list[str]:
    """Source lines belonging to a function (1-indexed -> 0-indexed slice)."""
    return source_lines[func.start_line - 1 : func.end_line]


def _detection(
    category_id: str,
    subcategory_id: str,
    category_name: str,
    subcategory_name: str,
    description: str,
    suggestion: str,
    severity: str,
    **location: Any,
) -> Detection:
    # Labels are resolved from the taxonomy, so this detector cannot drift from
    # it the way okeb.json once did. The literal names are the fallback for ids
    # the taxonomy does not define (e.g. the C0.S0 detector-failure marker).
    category = get_category(category_id)
    subcategory = get_subcategory(subcategory_id)
    return {
        "category_id": category_id,
        "subcategory_id": subcategory_id,
        "category_name": category.name if category else category_name,
        "subcategory_name": subcategory.name if subcategory else subcategory_name,
        "location": {key: value for key, value in location.items() if value is not None},
        "description": description,
        "severity": severity,
        "suggestion": suggestion,
        "evidence": "static pattern match",  # never a measurement
    }


# ============================================================
# RULES
# ============================================================

def rule_empty_function(
    state: CodeState, source: str, source_lines: list[str]
) -> list[Detection]:
    """C1.S5 — Resultless Computation."""
    detections: list[Detection] = []
    for func in state.functions:
        # Drop only the ``def`` line. The old ``[1:-1]`` also dropped the
        # function's last line, so every one-line body (e.g. ``return a + b``)
        # was reported as empty.
        body = [
            line.strip()
            for line in _function_lines(state, source_lines, func)[1:]
            if line.strip() and not line.strip().startswith("#")
        ]
        if body:
            continue
        detections.append(
            _detection(
                "C1", "C1.S5", "Redundant Computation", "Resultless Computation",
                f"Function '{func.name}' has an empty body — it executes but produces no result.",
                "Remove the empty function or implement its logic.",
                "medium", function=func.name, line=func.start_line,
            )
        )
    return detections


def rule_unnecessary_variable(
    state: CodeState, source: str, source_lines: list[str]
) -> list[Detection]:
    """C1.S7 — Unnecessary Variable (assign immediately followed by return)."""
    detections: list[Detection] = []
    for func in state.functions:
        lines = _function_lines(state, source_lines, func)
        for index, line in enumerate(lines):
            stripped = line.strip()
            if (
                "=" not in stripped
                or stripped.startswith("#")
                or stripped.startswith("def")
                or stripped.startswith("if")
                or stripped.startswith("return")
                or "==" in stripped
            ):
                continue

            variable = stripped.split("=", 1)[0].strip()
            if not variable or index + 1 >= len(lines):
                continue

            next_line = lines[index + 1].strip()
            if next_line.startswith("return") and variable in next_line:
                returned = next_line.replace("return", "", 1).strip()
                detections.append(
                    _detection(
                        "C1", "C1.S7", "Redundant Computation", "Unnecessary Variable",
                        f"Variable '{variable}' is assigned and immediately returned — "
                        "an unnecessary intermediate value.",
                        f"Return the expression directly: return {returned}",
                        "low", function=func.name, line=func.start_line + index,
                    )
                )
    return detections


def rule_range_len(
    state: CodeState, source: str, source_lines: list[str]
) -> list[Detection]:
    """C3.S1 — Inefficient Iteration Construct."""
    detections: list[Detection] = []
    for func in state.functions:
        for index, line in enumerate(_function_lines(state, source_lines, func)):
            if "range(len(" in line:
                detections.append(
                    _detection(
                        "C3", "C3.S1", "Inefficient Iteration Patterns",
                        "Inefficient Iteration Construct",
                        "Using range(len(...)) instead of iterating the collection adds "
                        "index lookup overhead on every step.",
                        "Iterate directly: 'for item in collection:'",
                        "low", function=func.name, line=func.start_line + index,
                    )
                )
    return detections


def rule_missing_early_exit(
    state: CodeState, source: str, source_lines: list[str]
) -> list[Detection]:
    """C3.S5 — Missing Loop Early Exit."""
    detections: list[Detection] = []
    for loop in state.loops:
        if loop.kind != "for":
            continue
        line = source_lines[loop.line - 1] if loop.line <= len(source_lines) else ""
        if "search" in line.lower() or "find" in line.lower():
            detections.append(
                _detection(
                    "C3", "C3.S5", "Inefficient Iteration Patterns",
                    "Missing Loop Early Exit",
                    "Loop performs a search without an obvious early exit, so it may "
                    "iterate the whole collection unnecessarily.",
                    "Return or break as soon as the target is found.",
                    "medium", line=loop.line,
                )
            )
    return detections


def rule_list_materialisation(
    state: CodeState, source: str, source_lines: list[str]
) -> list[Detection]:
    """C6.S3 — Unnecessary Data Materialization."""
    detections: list[Detection] = []
    reducers = ("sum(", "max(", "min(", "list(", "sorted(", "any(", "all(")

    for func in state.functions:
        for index, line in enumerate(_function_lines(state, source_lines, func)):
            stripped = line.strip()
            is_comprehension = (
                stripped.startswith("[") and "for" in stripped and " in " in stripped
            )
            if not is_comprehension:
                continue
            if any(reducer in stripped for reducer in reducers):
                detections.append(
                    _detection(
                        "C6", "C6.S3", "Unnecessary Memory Usage",
                        "Unnecessary Data Materialization",
                        "The list comprehension materialises the whole sequence in memory "
                        "although it is consumed once.",
                        "Use a generator expression: (x for x in ...)",
                        "medium", function=func.name, line=func.start_line + index,
                    )
                )
    return detections


def rule_mutable_default(
    state: CodeState, source: str, source_lines: list[str]
) -> list[Detection]:
    """C6.S7 — Leaking Mutable Default Arguments."""
    detections: list[Detection] = []
    for func in state.functions:
        for argument in func.arguments:
            if "=" not in argument:
                continue
            default = argument.split("=", 1)[1].strip()
            if default not in ("[]", "{}", "set()", "dict()", "list()"):
                continue
            detections.append(
                _detection(
                    "C6", "C6.S7", "Unnecessary Memory Usage",
                    "Leaking Mutable Default Arguments",
                    f"Function '{func.name}' uses the mutable default argument "
                    f"'{default}', which persists and grows across calls.",
                    "Use None as the default and create the container inside the function.",
                    "high", function=func.name, line=func.start_line,
                )
            )
    return detections


def rule_repeated_calls(
    state: CodeState, source: str, source_lines: list[str]
) -> list[Detection]:
    """C8.S1 — Missing Memoization Cache."""
    builtins = {"print", "len", "str", "int", "float", "list", "dict", "set", "range"}
    counts = Counter(
        call.name for call in state.function_calls if call.name not in builtins
    )

    detections: list[Detection] = []
    for name, count in counts.items():
        if count <= 2:
            continue
        detections.append(
            _detection(
                "C8", "C8.S1", "Missing Reuse", "Missing Memoization Cache",
                f"Function '{name}' is called {count} times — a repeated computation "
                "whose result may be cacheable.",
                "Store the result in a local variable or apply @functools.lru_cache.",
                "medium", function=name,
            )
        )
    return detections


def rule_manual_min_max(
    state: CodeState, source: str, source_lines: list[str]
) -> list[Detection]:
    """C10.S1 — Skipping Optimized Built-ins."""
    detections: list[Detection] = []
    for func in state.functions:
        lines = _function_lines(state, source_lines, func)
        for index, line in enumerate(lines):
            stripped = line.strip()
            if not stripped.startswith("if "):
                continue
            if "<" not in stripped and ">" not in stripped:
                continue
            if index + 1 >= len(lines):
                continue

            next_line = lines[index + 1]
            if "=" not in next_line or next_line.strip().startswith("#"):
                continue
            variable = next_line.split("=", 1)[0].strip()
            if variable and variable in stripped:
                detections.append(
                    _detection(
                        "C10", "C10.S1", "Underused Language Primitives",
                        "Skipping Optimized Built-ins",
                        "Manual comparison to pick a value where a built-in would work; "
                        "min()/max() are implemented natively.",
                        "Use built-in min() or max() instead of a manual comparison.",
                        "low", function=func.name, line=func.start_line + index,
                    )
                )
    return detections


RULES: list[Rule] = [
    rule_empty_function,
    rule_unnecessary_variable,
    rule_range_len,
    rule_missing_early_exit,
    rule_list_materialisation,
    rule_mutable_default,
    rule_repeated_calls,
    rule_manual_min_max,
]


# ============================================================
# PUBLIC API
# ============================================================

def detect_smells(
    state: CodeState,
    source: str,
    language: str = "python",
) -> list[Detection]:
    """Run every rule over a parsed file and return ranked detections.

    Detections are hypotheses: each one names the taxonomy subcategory it maps
    to and explicitly states that its evidence is a static pattern match.
    """
    source_lines = source.splitlines()
    detections: list[Detection] = []

    for rule in RULES:
        try:
            detections.extend(rule(state, source, source_lines))
        except Exception as error:  # one bad rule must not break detection
            detections.append(
                _detection(
                    "C0", "C0.S0", "Detector", "Rule Failure",
                    f"Rule '{rule.__name__}' could not run: {error}",
                    "Report this as a detector bug.",
                    "low", line=None,
                )
            )

    # Stable ordering: severity first, then source line.
    detections.sort(
        key=lambda item: (
            SEVERITY_ORDER.get(str(item.get("severity", "low")), 3),
            int((item.get("location") or {}).get("line") or 0),
        )
    )
    return detections


def summarise_detections(detections: list[Detection]) -> dict[str, Any]:
    """Aggregate detections for a summary-first dashboard."""
    by_severity: Counter[str] = Counter(
        str(item.get("severity", "unknown")) for item in detections
    )
    by_category: Counter[str] = Counter(
        f"{item.get('category_id')} — {item.get('category_name')}" for item in detections
    )

    return {
        "detection_count": len(detections),
        "by_severity": dict(by_severity),
        "by_category": dict(by_category),
        "categories_detected": sorted(
            {str(item.get("category_id")) for item in detections if item.get("category_id")}
        ),
    }


# Backwards-compatible alias for the previous backend-local helper name.
detect_smells_from_code_state = detect_smells


__all__ = [
    "RULES",
    "detect_smells",
    "detect_smells_from_code_state",
    "summarise_detections",
]
