"""Executable examples for the rules that actually have a matcher.

A matcher that runs is not the same as a matcher that is correct. Each case
below is a minimal Python snippet with an explicit expectation:

* ``should_match=True``  — the rule must be reported for this snippet.
* ``should_match=False`` — the rule must *not* be reported (the shape is
  there, but a guard or an extra statement makes the rewrite unsafe).

Negative cases matter more than positive ones: they are what stops a matcher
from firing on code it would break. Run them from the Rule Base page
(``GET /api/rules/selftest``) or from pytest::

    python -m pytest modules/energy_detection/test_rulebase.py -q
"""

from __future__ import annotations

from dataclasses import dataclass

from modules.energy_detection.matcher import IMPLEMENTED_RULE_IDS, identify_issues


@dataclass(frozen=True)
class RuleCase:
    rule_id: str
    name: str
    source: str
    should_match: bool
    note: str = ""


RULE_CASES: tuple[RuleCase, ...] = (
    # ------------------------------------------------------------
    # C3.S1.R1 — index-based iteration
    # ------------------------------------------------------------
    RuleCase(
        "C3.S1.R1",
        "index only used to subscript",
        """\
def firsts(items):
    for i in range(len(items)):
        print(items[i])
""",
        True,
        "The index exists only to read items[i], so direct iteration is safe.",
    ),
    RuleCase(
        "C3.S1.R1",
        "index used for arithmetic",
        """\
def labels(items):
    for i in range(len(items)):
        print(i + 1)
""",
        False,
        "The index carries meaning of its own; replacing it would change output.",
    ),
    # ------------------------------------------------------------
    # C3.S1.R2 — append inside a loop
    # ------------------------------------------------------------
    RuleCase(
        "C3.S1.R2",
        "loop body is only an append",
        """\
def squares(numbers):
    result = []
    for n in numbers:
        result.append(n * n)
    return result
""",
        True,
        "A single append per iteration is exactly a comprehension.",
    ),
    RuleCase(
        "C3.S1.R2",
        "append plus side effect",
        """\
def squares(numbers):
    result = []
    for n in numbers:
        result.append(n * n)
        print(n)
    return result
""",
        False,
        "The body does more than append, so a comprehension would drop the print.",
    ),
    # ------------------------------------------------------------
    # C3.S1.R3 — dict.keys()
    # ------------------------------------------------------------
    RuleCase(
        "C3.S1.R3",
        "iterate over keys()",
        """\
def keys_of(config):
    keys = []
    for key in config.keys():
        keys.append(key)
    return keys
""",
        True,
        "Iterating the mapping yields the same keys.",
    ),
    RuleCase(
        "C3.S1.R3",
        "iterate items()",
        """\
def pairs(config):
    for key, value in config.items():
        print(key, value)
""",
        False,
        "keys() is not used here, so there is nothing to simplify.",
    ),
    # ------------------------------------------------------------
    # C3.S1.R4 — manual max()/min()
    # ------------------------------------------------------------
    RuleCase(
        "C3.S1.R4",
        "single-branch accumulator",
        """\
def largest(values):
    best = values[0]
    for value in values:
        if value > best:
            best = value
    return best
""",
        True,
        "This is max(values) written by hand.",
    ),
    RuleCase(
        "C3.S1.R4",
        "accumulator with an else branch",
        """\
def largest(values):
    best = values[0]
    for value in values:
        if value > best:
            best = value
        else:
            best = best
    return best
""",
        False,
        "The else branch means the loop is not a plain reduction.",
    ),
    # ------------------------------------------------------------
    # C3.S5.R2 — boolean scan
    # ------------------------------------------------------------
    RuleCase(
        "C3.S5.R2",
        "scan returning True then False",
        """\
def contains_negative(values):
    for value in values:
        if value < 0:
            return True
    return False
""",
        True,
        "any(...) short-circuits exactly like this loop.",
    ),
    RuleCase(
        "C3.S5.R2",
        "scan returning None",
        """\
def contains_negative(values):
    for value in values:
        if value < 0:
            return True
    return None
""",
        False,
        "The fallback is not False, so any() would change the return value.",
    ),
    # ------------------------------------------------------------
    # C4.S8.R1 — len(x) == 0
    # ------------------------------------------------------------
    RuleCase(
        "C4.S8.R1",
        "empty check with len()",
        """\
def first(items):
    if len(items) == 0:
        return None
    return items[0]
""",
        True,
        "Emptiness is what is being tested, so truthiness is equivalent.",
    ),
    RuleCase(
        "C4.S8.R1",
        "non-empty check",
        """\
def first(items):
    if len(items) > 0:
        return items[0]
    return None
""",
        True,
        "len(x) > 0 is equivalent to truthiness, so this is the same rule.",
    ),
    RuleCase(
        "C4.S8.R1",
        "single-element check",
        """\
def only(items):
    if len(items) == 1:
        return items[0]
    return None
""",
        False,
        "len(x) == 1 is not emptiness; rewriting it to `if x:` would accept "
        "containers with more than one element.",
    ),
    # ------------------------------------------------------------
    # C10.S4.R1 — repeated string concatenation
    # ------------------------------------------------------------
    RuleCase(
        "C10.S4.R1",
        "string += inside a loop",
        """\
def join_words(words):
    text = ""
    for word in words:
        text += " "
    return text
""",
        True,
        "Repeated += on a string rebuilds the string every iteration.",
    ),
    RuleCase(
        "C10.S4.R1",
        "numeric += inside a loop",
        """\
def count(numbers):
    total = 0
    for number in numbers:
        total += 1
    return total
""",
        False,
        "The accumulator is numeric, not a string.",
    ),
    # ------------------------------------------------------------
    # C6.S3.R1 — eager list in a reducer
    # ------------------------------------------------------------
    RuleCase(
        "C6.S3.R1",
        "sum over a list comprehension",
        """\
def sum_squares(values):
    return sum([v * v for v in values])
""",
        True,
        "The list is built only to be consumed once.",
    ),
    RuleCase(
        "C6.S3.R1",
        "sum over a generator",
        """\
def sum_squares(values):
    return sum(v * v for v in values)
""",
        False,
        "The code already uses a generator; there is no throwaway list.",
    ),
)


def run_selftest(cases: tuple[RuleCase, ...] = RULE_CASES) -> dict:
    """Run every case and report pass/fail per rule.

    The result is deliberately explicit about which implemented rules have no
    case: silence there means "untested", not "correct".
    """
    results: list[dict] = []

    for case in cases:
        try:
            report = identify_issues(case.source, f"<case: {case.name}>")
            detected_rules = sorted({issue["rule_id"] for issue in report["issues"]})
            detected = case.rule_id in detected_rules
            error = None
        except Exception as exc:  # a matcher crash is a failing test, not a skip
            detected_rules = []
            detected = False
            error = str(exc)

        passed = error is None and detected == case.should_match
        results.append(
            {
                "rule_id": case.rule_id,
                "name": case.name,
                "should_match": case.should_match,
                "expected": "match" if case.should_match else "no match",
                "detected": detected,
                "detected_rules": detected_rules,
                "passed": passed,
                "note": case.note,
                "source": case.source,
                "error": error,
            }
        )

    covered = {case.rule_id for case in cases}
    implemented = set(IMPLEMENTED_RULE_IDS)
    passed_count = sum(1 for result in results if result["passed"])

    return {
        "case_count": len(results),
        "passed_count": passed_count,
        "failed_count": len(results) - passed_count,
        "results": results,
        "implemented_rule_ids": list(IMPLEMENTED_RULE_IDS),
        "rules_with_cases": sorted(covered & implemented),
        "rules_without_cases": sorted(implemented - covered),
        "requires_measurement": True,
        "note": (
            "Self-test cases exercise the matcher only. A passing case means the "
            "rule was (or was not) reported as expected; it does not measure energy."
        ),
    }


__all__ = ["RULE_CASES", "RuleCase", "run_selftest"]
