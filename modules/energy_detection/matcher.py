"""Structural issue identification against the OKEB rule base.

This is the layer between the parser and the knowledge base. It does *not*
search rule text for keywords. It walks the tree-sitter AST, matches a concrete
code shape, binds the names the strategy needs (``capture``), and checks the
rule's preconditions where they are statically decidable (``guards``).

A match produces an *opportunity*:

    rule id + span + captures + guard status + strategy text

The rule id is the join key into ``okeb.json``; the captures are what turn the
prose strategy ("Iterate directly") into an applicable rewrite for one specific
loop. That difference is the whole point: a detector that only says "you have
inefficient iteration" forces the generator to invent a strategy, while a
detector that says "line 7, ``for i in range(len(self.items))``, index used only
as ``self.items[i]``" hands it ``for item in self.items``.

Evidence levels follow the knowledge base, not this module:

* ``static`` — the shape is decidable from the AST; guards are evaluated.
* ``hybrid`` / ``profiling`` — not implemented here. Those rules require
  runtime evidence, so emitting them from a static match would overstate what
  is known. They are left to the profiler/probe stage.

Matches are hypotheses about inefficiency, never measurements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Iterator

from modules.code_understanding.adapters import get_adapter
from modules.code_understanding.parser import parse_code
from modules.energy_detection.rulebase import canonical_rule_id, load_kb

PASSED = "passed"
FAILED = "failed"
UNRESOLVED = "unresolved"

MUTATORS = {
    "append", "extend", "insert", "pop", "remove", "clear", "sort", "reverse",
    "update", "setdefault", "popitem",
}
REDUCERS = {"sum", "max", "min", "any", "all"}


# ============================================================
# AST HELPERS
# ============================================================

def _text(node: Any) -> str:
    return node.text.decode("utf-8", errors="replace")


def _walk(node: Any) -> Iterator[Any]:
    yield node
    for child in node.named_children:
        yield from _walk(child)


def _same(left: Any, right: Any) -> bool:
    return (
        left is not None
        and right is not None
        and left.start_byte == right.start_byte
        and left.end_byte == right.end_byte
        and left.type == right.type
    )


def _line(node: Any) -> int:
    return node.start_point[0] + 1


def _end_line(node: Any) -> int:
    return node.end_point[0] + 1


def _field(node: Any, name: str) -> Any:
    return None if node is None else node.child_by_field_name(name)


def _call_name(call: Any) -> str | None:
    function = _field(call, "function")
    return None if function is None else _text(function)


def _positional_args(call: Any) -> list[Any]:
    arguments = _field(call, "arguments")
    if arguments is None:
        return []
    return [
        child for child in arguments.named_children
        if child.type not in {"keyword_argument", "list_splat", "dictionary_splat"}
    ]


def _siblings(node: Any) -> list[Any]:
    parent = node.parent
    return [] if parent is None else list(parent.named_children)


def _previous_sibling(node: Any) -> Any:
    siblings = _siblings(node)
    for index, sibling in enumerate(siblings):
        if _same(sibling, node):
            return siblings[index - 1] if index > 0 else None
    return None


def _next_sibling(node: Any) -> Any:
    siblings = _siblings(node)
    for index, sibling in enumerate(siblings):
        if _same(sibling, node):
            return siblings[index + 1] if index + 1 < len(siblings) else None
    return None


def _nearest_loop(node: Any) -> Any:
    """Innermost loop containing ``node`` (None outside any loop)."""
    current = node.parent
    while current is not None:
        if current.type in {"for_statement", "while_statement"}:
            return current
        current = current.parent
    return None


def _single_assignment_name(statement: Any) -> tuple[str, Any] | None:
    """Return ``(name, value_node)`` for ``x = expr`` / ``x: T = expr``."""
    if statement is None or statement.type != "expression_statement":
        return None
    assignment = statement.named_children[0] if statement.named_children else None
    if assignment is None or assignment.type != "assignment":
        return None
    left = _field(assignment, "left")
    right = _field(assignment, "right")
    if left is None or right is None or left.type != "identifier":
        return None
    return _text(left), right


def _collection_mutated(body: Any, collection: str) -> bool:
    """True when ``collection`` is mutated inside ``body``."""
    for node in _walk(body):
        if node.type == "call":
            function = _field(node, "function")
            if (
                function is not None
                and function.type == "attribute"
                and _text(_field(function, "object")) == collection
                and _text(_field(function, "attribute")) in MUTATORS
            ):
                return True
        if node.type in {"assignment", "augmented_assignment"}:
            left = _field(node, "left")
            if left is not None and _text(left).startswith(f"{collection}["):
                return True
            if left is not None and left.type == "identifier" and _text(left) == collection:
                return True
    return False


def _is_range_len(iterable: Any) -> Any:
    """Return the collection node of ``range(len(collection))``, else None."""
    if iterable is None or iterable.type != "call":
        return None
    if _call_name(iterable) != "range":
        return None
    arguments = _positional_args(iterable)
    if len(arguments) != 1:
        return None
    inner = arguments[0]
    if inner.type != "call" or _call_name(inner) != "len":
        return None
    inner_arguments = _positional_args(inner)
    if len(inner_arguments) != 1:
        return None
    return inner_arguments[0]


def _comparison_parts(node: Any) -> tuple[list[Any], list[str]]:
    operands = list(node.named_children)
    operators = [child.type for child in node.children if not child.is_named]
    return operands, operators


def _reduction_source(iterable: Any, item: str, index_name: str) -> str:
    """The collection a built-in reducer should receive for ``item``.

    ``for i in range(len(xs))`` with ``if xs[i] > best`` reduces ``xs``, not
    ``range(len(xs))``, so the index wrapper is unwrapped before the hint is
    built.
    """
    collection = _is_range_len(iterable)
    if collection is not None and item == f"{_text(collection)}[{index_name}]":
        return _text(collection)
    return _text(iterable) if iterable is not None else ""


def _is_empty_container_check(condition: Any) -> tuple[str, str] | None:
    """Return ``(collection, operator)`` for a ``len(x) == 0`` style check."""
    if condition is None:
        return None
    node = condition
    if node.type == "boolean_operator":
        for child in node.named_children:
            found = _is_empty_container_check(child)
            if found:
                return found
        return None
    if node.type != "comparison_operator":
        return None
    operands, operators = _comparison_parts(node)
    if len(operands) != 2 or len(operators) != 1:
        return None
    operator = operators[0]
    if operator not in {"==", "!=", ">", ">=", "<"}:
        return None
    for index in (0, 1):
        candidate = operands[index]
        other = operands[1 - index]
        if (
            candidate.type == "call"
            and _call_name(candidate) == "len"
            and len(_positional_args(candidate)) == 1
            and other.type in {"integer", "float"}
        ):
            collection = _positional_args(candidate)[0]
            if collection.type not in {"identifier", "attribute"}:
                return None
            # Only zero means emptiness. Accepting 1 would rewrite
            # ``len(x) == 1`` / ``len(x) > 1`` to ``if x:``, which changes
            # behaviour for single-element and multi-element containers.
            zero = _text(other).strip()
            if zero not in {"0", "0.0"}:
                return None
            return _text(collection), operator
    return None


# ============================================================
# MATCH MODEL
# ============================================================

@dataclass
class Guard:
    name: str
    status: str
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


@dataclass
class Match:
    """One concrete code location that satisfies a rule's shape."""

    rule_id: str
    node: Any
    capture: dict[str, str] = field(default_factory=dict)
    guards: list[Guard] = field(default_factory=list)
    rewrite_hint: str = ""

    @property
    def guard_status(self) -> str:
        statuses = {guard.status for guard in self.guards}
        if FAILED in statuses:
            return FAILED
        if UNRESOLVED in statuses:
            return UNRESOLVED
        return "resolved"

    @property
    def confidence(self) -> str:
        return "high" if self.guard_status == "resolved" else "medium"


# ============================================================
# MATCHERS (keyed by canonical OKEB rule id)
# ============================================================

def match_index_based_iteration(root: Any) -> list[Match]:
    """C3.S1.R1 — ``for i in range(len(items)): ... items[i]``."""
    matches: list[Match] = []
    for node in _walk(root):
        if node.type != "for_statement":
            continue
        target = _field(node, "left")
        collection_node = _is_range_len(_field(node, "right"))
        body = _field(node, "body")
        if target is None or target.type != "identifier" or collection_node is None:
            continue

        index = _text(target)
        collection = _text(collection_node)
        other_uses: list[str] = []
        for node_in_body in _walk(body):
            if node_in_body.type != "identifier" or _text(node_in_body) != index:
                continue
            parent = node_in_body.parent
            if (
                parent is not None
                and parent.type == "subscript"
                and _same(_field(parent, "subscript"), node_in_body)
                and _text(_field(parent, "value")) == collection
            ):
                continue
            other_uses.append(_text(parent) if parent is not None else index)

        guards = [
            Guard(
                "index_used_only_for_subscript",
                PASSED if not other_uses else FAILED,
                "" if not other_uses else f"index also used in: {other_uses[0]}",
            )
        ]
        if other_uses:
            continue

        mutated = _collection_mutated(body, collection)
        guards.append(
            Guard(
                "collection_not_mutated",
                UNRESOLVED if mutated else PASSED,
                "collection is mutated inside the loop" if mutated else "",
            )
        )
        matches.append(
            Match(
                rule_id="C3.S1.R1",
                node=node,
                capture={
                    "collection": collection,
                    "index": index,
                    "item": _singular(collection),
                },
                guards=guards,
                rewrite_hint=(
                    f"for {_singular(collection)} in {collection}: "
                    f"and replace {collection}[{index}] with {_singular(collection)}"
                ),
            )
        )
    return matches


def match_repeated_list_append(root: Any) -> list[Match]:
    """C3.S1.R2 — a loop whose body only appends one expression to a list."""
    matches: list[Match] = []
    for node in _walk(root):
        if node.type != "for_statement":
            continue
        body = _field(node, "body")
        if body is None or not body.named_children:
            continue

        accumulators: set[str] = set()
        expressions: list[str] = []
        valid = True
        for statement in body.named_children:
            if statement.type != "expression_statement" or not statement.named_children:
                valid = False
                break
            call = statement.named_children[0]
            function = _field(call, "function") if call.type == "call" else None
            if (
                function is None
                or function.type != "attribute"
                or _text(_field(function, "attribute")) != "append"
            ):
                valid = False
                break
            arguments = _positional_args(call)
            if len(arguments) != 1:
                valid = False
                break
            accumulators.add(_text(_field(function, "object")))
            expressions.append(_text(arguments[0]))

        if not valid or len(accumulators) != 1:
            continue
        accumulator = next(iter(accumulators))

        previous = _previous_sibling(node)
        assignment = _single_assignment_name(previous)
        initialised = (
            assignment is not None
            and assignment[0] == accumulator
            and assignment[1].type in {"list", "list_comprehension"}
        )
        guards = [
            Guard(
                "accumulator_initialised_as_list",
                PASSED if initialised else UNRESOLVED,
                "" if initialised else "no local `x = []` initialisation found before the loop",
            ),
            Guard(
                "body_is_only_appends",
                PASSED,
                "",
            ),
        ]
        iterable = _field(node, "right")
        target = _field(node, "left")
        target_name = _text(target) if target is not None else "item"
        matches.append(
            Match(
                rule_id="C3.S1.R2",
                node=node,
                capture={
                    "accumulator": accumulator,
                    "target": target_name,
                    "iterable": _text(iterable) if iterable is not None else "",
                    "append_expression": expressions[0] if expressions else "",
                },
                guards=guards,
                rewrite_hint=(
                    f"{accumulator} = [{expressions[0] if expressions else 'expr'} "
                    f"for {target_name} in {_text(iterable) if iterable is not None else 'iterable'}]"
                ),
            )
        )
    return matches


def match_dict_keys(root: Any) -> list[Match]:
    """C3.S1.R3 — ``for k in d.keys()`` only needs ``for k in d``."""
    matches: list[Match] = []
    for node in _walk(root):
        if node.type != "for_statement":
            continue
        iterable = _field(node, "right")
        if iterable is None or iterable.type != "call":
            continue
        function = _field(iterable, "function")
        if (
            function is None
            or function.type != "attribute"
            or _text(_field(function, "attribute")) != "keys"
            or _positional_args(iterable)
        ):
            continue
        mapping = _text(_field(function, "object"))
        body = _field(node, "body")
        mutated = _collection_mutated(body, mapping)
        matches.append(
            Match(
                rule_id="C3.S1.R3",
                node=node,
                capture={"mapping": mapping, "target": _text(_field(node, "left"))},
                guards=[
                    Guard(
                        "only_keys_required",
                        PASSED,
                        "iteration target is bound to a key",
                    ),
                    Guard(
                        "mapping_not_mutated",
                        UNRESOLVED if mutated else PASSED,
                        "mapping is mutated inside the loop" if mutated else "",
                    ),
                ],
                rewrite_hint=f"for {_text(_field(node, 'left'))} in {mapping}:",
            )
        )
    return matches


def match_manual_reduction(root: Any) -> list[Match]:
    """C3.S1.R4 — a loop that reimplements ``max()`` / ``min()``."""
    matches: list[Match] = []
    for node in _walk(root):
        if node.type != "for_statement":
            continue
        body = _field(node, "body")
        if body is None:
            continue
        conditionals = [
            child for child in body.named_children if child.type == "if_statement"
        ]
        if len(conditionals) != 1:
            continue
        conditional = conditionals[0]
        if _field(conditional, "alternative") is not None:
            continue
        condition = _field(conditional, "condition")
        if condition is None or condition.type != "comparison_operator":
            continue
        operands, operators = _comparison_parts(condition)
        if len(operands) != 2 or len(operators) != 1:
            continue
        operator = operators[0]
        if operator not in {">", ">=", "<", "<="}:
            continue

        consequence = _field(conditional, "consequence")
        if consequence is None or len(consequence.named_children) != 1:
            continue
        assignment = _single_assignment_name(consequence.named_children[0])
        if assignment is None:
            continue
        accumulated, assigned_value = assignment

        names = [_text(operand) for operand in operands]
        if accumulated not in names:
            continue
        item = names[1 - names.index(accumulated)]
        if _text(assigned_value) != item:
            continue

        previous = _previous_sibling(node)
        initialisation = _single_assignment_name(previous)
        if initialisation is None or initialisation[0] != accumulated:
            continue

        reducer = "max" if operator in {">", ">="} else "min"
        collection = _reduction_source(
            _field(node, "right"), item, _text(_field(node, "left"))
        )
        matches.append(
            Match(
                rule_id="C3.S1.R4",
                node=node,
                capture={
                    "accumulator": accumulated,
                    "initial_value": _text(initialisation[1]),
                    "iterable": collection,
                    "item": item,
                },
                guards=[
                    Guard("single_branch", PASSED, ""),
                    Guard("accumulator_initialised", PASSED, ""),
                ],
                rewrite_hint=f"{accumulated} = {reducer}({collection})",
            )
        )
    return matches


def match_boolean_scan(root: Any) -> list[Match]:
    """C3.S5.R2 — a full scan that should short-circuit with ``any()``."""
    matches: list[Match] = []
    for node in _walk(root):
        if node.type != "for_statement":
            continue
        body = _field(node, "body")
        if body is None or len(body.named_children) != 1:
            continue
        conditional = body.named_children[0]
        if conditional.type != "if_statement" or _field(conditional, "alternative") is not None:
            continue
        consequence = _field(conditional, "consequence")
        if consequence is None or len(consequence.named_children) != 1:
            continue
        result = consequence.named_children[0]
        if result.type != "return_statement" or not result.named_children:
            continue
        if result.named_children[0].type != "true":
            continue

        following = _next_sibling(node)
        if following is None or following.type != "return_statement":
            continue
        if not following.named_children or following.named_children[0].type != "false":
            continue

        condition = _field(conditional, "condition")
        iterable = _text(_field(node, "right"))
        target = _text(_field(node, "left"))
        predicate = _text(condition)
        matches.append(
            Match(
                rule_id="C3.S5.R2",
                node=node,
                capture={
                    "iterable": iterable,
                    "predicate": predicate,
                    "target": target,
                },
                guards=[
                    Guard("returns_true_then_false", PASSED, ""),
                    Guard(
                        "predicate_side_effects",
                        UNRESOLVED,
                        "any() would stop calling the predicate after the first match",
                    ),
                ],
                rewrite_hint=f"return any({predicate} for {target} in {iterable})",
            )
        )
    return matches


def match_empty_container_check(root: Any) -> list[Match]:
    """C4.S8.R1 — ``len(items) == 0`` instead of ``not items``."""
    matches: list[Match] = []
    for node in _walk(root):
        if node.type not in {"if_statement", "while_statement", "boolean_operator", "unary_operator"}:
            continue
        condition = _field(node, "condition") if node.type != "boolean_operator" else node
        if condition is None:
            continue
        found = _is_empty_container_check(condition)
        if not found:
            continue
        collection, operator = found
        matches.append(
            Match(
                rule_id="C4.S8.R1",
                node=node,
                capture={"collection": collection, "operator": operator},
                guards=[Guard("truthiness_means_emptiness", PASSED, "")],
                rewrite_hint=f"{'not' if operator in {'==', '<'} else ''} {collection}".strip(),
            )
        )
    return matches


def match_string_concatenation(root: Any) -> list[Match]:
    """C10.S4.R1 — repeated ``+=`` on a string inside a loop."""
    matches: list[Match] = []
    for loop in _walk(root):
        if loop.type not in {"for_statement", "while_statement"}:
            continue
        body = _field(loop, "body")
        if body is None:
            continue
        for node in _walk(body):
            if node.type != "augmented_assignment":
                continue
            if not _same(_nearest_loop(node), loop):
                continue  # reported once, for the loop that actually contains it
            if _text(_field(node, "operator")) != "+=":
                continue
            left = _field(node, "left")
            right = _field(node, "right")
            if left is None or right is None or left.type != "identifier":
                continue
            if right.type not in {"string", "concatenated_string", "interpolation"}:
                continue
            accumulator = _text(left)
            initialised_as_string = False
            previous = _previous_sibling(loop)
            assignment = _single_assignment_name(previous)
            if assignment is not None and assignment[0] == accumulator:
                initialised_as_string = assignment[1].type == "string"
            matches.append(
                Match(
                    rule_id="C10.S4.R1",
                    node=loop,
                    capture={
                        "accumulator": accumulator,
                        "fragment": _text(right),
                        "iterable": _text(_field(loop, "right"))
                        if loop.type == "for_statement" else "",
                    },
                    guards=[
                        Guard(
                            "accumulator_is_string",
                            PASSED if initialised_as_string else UNRESOLVED,
                            "" if initialised_as_string else "string type inferred from the fragment only",
                        )
                    ],
                    rewrite_hint=(
                        f"collect fragments in a list and use ''.join(...) instead of {accumulator} += ..."
                    ),
                )
            )
    return matches


def match_eager_sequence(root: Any) -> list[Match]:
    """C6.S3.R1 — ``sum([x for x in ...])`` materialises a throwaway list."""
    matches: list[Match] = []
    for node in _walk(root):
        if node.type != "call":
            continue
        name = _call_name(node)
        if name not in REDUCERS:
            continue
        arguments = _positional_args(node)
        if len(arguments) != 1 or arguments[0].type != "list_comprehension":
            continue
        comprehension = arguments[0]
        body = _field(comprehension, "body")
        clause = next(
            (child for child in comprehension.named_children if child.type == "for_in_clause"),
            None,
        )
        if body is None or clause is None:
            continue
        matches.append(
            Match(
                rule_id="C6.S3.R1",
                node=node,
                capture={
                    "reducer": name,
                    "expression": _text(body),
                    "iterable": _text(_field(clause, "right")),
                    "target": _text(_field(clause, "left")),
                },
                guards=[
                    Guard("collection_consumed_once", PASSED, ""),
                    Guard("no_index_needed", PASSED, ""),
                ],
                rewrite_hint=f"{name}({_text(body)} for {_text(_field(clause, 'left'))} in {_text(_field(clause, 'right'))})",
            )
        )
    return matches


MATCHERS: tuple[Callable[[Any], list[Match]], ...] = (
    match_index_based_iteration,
    match_repeated_list_append,
    match_dict_keys,
    match_manual_reduction,
    match_boolean_scan,
    match_empty_container_check,
    match_string_concatenation,
    match_eager_sequence,
)

# One loop can satisfy a general rule and a more specific one. Report only the
# specific rule, otherwise the generator is asked to apply two conflicting
# rewrites to the same statement (direct iteration *and* a comprehension).
SPECIFICITY_OVERRIDES: dict[str, set[str]] = {
    "C3.S1.R3": {"C3.S1.R2"},
}

IMPLEMENTED_RULE_IDS: tuple[str, ...] = (
    "C3.S1.R1",
    "C3.S1.R2",
    "C3.S1.R3",
    "C3.S1.R4",
    "C3.S5.R2",
    "C4.S8.R1",
    "C10.S4.R1",
    "C6.S3.R1",
)


def _singular(name: str) -> str:
    """A safe placeholder item name for a rewrite hint (no linguistic claims)."""
    base = name.split(".")[-1]
    if base.endswith("ies"):
        return base[:-3] + "y"
    if base.endswith("s") and len(base) > 1:
        return base[:-1]
    return "item"


# ============================================================
# PUBLIC API
# ============================================================

def identify_issues(
    source: str,
    path: str = "<string>",
    language: str = "python",
) -> dict[str, Any]:
    """Identify rule matches in ``source``.

    Returns ``{"file", "language", "issues", "summary"}``. Every issue carries
    the matched rule id, the captured names, the guard status and the strategy
    text from ``okeb.json``. Nothing here measures energy.
    """
    if language != "python":
        raise ValueError(
            "Structural matchers are Python-only; the rule base is "
            "language-agnostic but the AST shapes are not."
        )

    adapter = get_adapter(language)
    from tree_sitter import Parser

    root = Parser(adapter.grammar).parse(source.encode("utf-8")).root_node
    state = parse_code(source, path, language)
    functions = sorted(state.functions, key=lambda item: item.start_line)

    kb = load_kb()
    raw: list[Match] = []
    failures: list[dict[str, str]] = []
    for matcher in MATCHERS:
        try:
            raw.extend(matcher(root))
        except Exception as error:  # a broken matcher must not hide the others
            failures.append({"matcher": matcher.__name__, "error": str(error)})

    rules_by_node: dict[int, set[str]] = {}
    for match in raw:
        rules_by_node.setdefault(match.node.start_byte, set()).add(match.rule_id)

    seen: set[tuple[str, int]] = set()
    issues: list[dict[str, Any]] = []
    for match in sorted(raw, key=lambda item: (_line(item.node), item.rule_id)):
        key = (match.rule_id, match.node.start_byte)
        if key in seen:
            continue
        seen.add(key)

        winners = rules_by_node.get(match.node.start_byte, set())
        superseded = {
            loser
            for winner, losers in SPECIFICITY_OVERRIDES.items()
            if winner in winners
            for loser in losers
        }
        if match.rule_id in superseded:
            continue

        rule = kb.rule(match.rule_id)
        derived = (rule or {}).get("derived") or {}
        line = _line(match.node)
        issues.append(
            {
                "rule_id": canonical_rule_id(match.rule_id),
                "category_id": (rule or {}).get("category_id"),
                "category_name": (rule or {}).get("category_name"),
                "subcategory_id": (rule or {}).get("subcategory_id"),
                "subcategory_name": (rule or {}).get("subcategory_name"),
                "pattern": (rule or {}).get("pattern", ""),
                "location": {
                    "file": path,
                    "line": line,
                    "end_line": _end_line(match.node),
                    "function": _enclosing_function(line, functions),
                },
                "capture": dict(match.capture),
                "rewrite_hint": match.rewrite_hint,
                "guards": [guard.to_dict() for guard in match.guards],
                "guard_status": match.guard_status,
                "confidence": match.confidence,
                # Evidence strength comes from the knowledge base, not the matcher.
                "evidence_strength": derived.get("detection_mode", "static"),
                "evidence": "static structural match",  # never a measurement
                "strategy": (rule or {}).get("strategy", ""),
                "preconditions": (rule or {}).get("preconditions", ""),
                "expected_benefit": (rule or {}).get("expected_benefit", ""),
                "fix_mode": derived.get("fix_mode", ""),
                "kb_rule_found": rule is not None,
            }
        )

    summary = {
        "issue_count": len(issues),
        "rule_count": len({issue["rule_id"] for issue in issues}),
        "by_rule": _count(issue["rule_id"] for issue in issues),
        "by_category": _count(str(issue["category_id"]) for issue in issues),
        "requires_measurement": True,
        "matcher_failures": failures,
    }
    return {"file": path, "language": language, "issues": issues, "summary": summary}


def _count(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _enclosing_function(line: int, functions: list[Any]) -> str | None:
    best: Any = None
    for function in functions:
        if function.start_line <= line <= function.end_line:
            if best is None or (
                function.end_line - function.start_line < best.end_line - best.start_line
            ):
                best = function
    return None if best is None else best.name


if __name__ == "__main__":  # pragma: no cover - manual demo entry point
    import json
    import sys
    from pathlib import Path

    if len(sys.argv) < 2:
        raise SystemExit("usage: python -m modules.energy_detection.matcher <file.py>")
    target = Path(sys.argv[1])
    print(
        json.dumps(
            identify_issues(target.read_text(encoding="utf-8"), str(target)),
            indent=2,
        )
    )


__all__ = [
    "IMPLEMENTED_RULE_IDS",
    "MATCHERS",
    "identify_issues",
]
