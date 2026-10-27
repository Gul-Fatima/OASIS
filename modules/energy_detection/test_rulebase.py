"""Tests for the OKEB loader and the structural matcher.

Run from the OASIS root:

    python -m pytest modules/energy_detection/test_rulebase.py -q
"""

from __future__ import annotations

import pytest

from modules.energy_detection.matcher import IMPLEMENTED_RULE_IDS, identify_issues
from modules.energy_detection.selftest import RULE_CASES, run_selftest
from modules.energy_detection.okeb_align import align
from modules.energy_detection.rulebase import OkebKnowledgeBase, canonical_rule_id
from modules.energy_detection.taxonomy import ENERGY_SMELL_CATEGORIES

SAMPLE = '''\
def total_and_max(numbers):
    total = 0
    best = 0
    for i in range(len(numbers)):
        total = total + numbers[i]
        if numbers[i] > best:
            best = numbers[i]
    return total, best


def squares(numbers):
    result = []
    for n in numbers:
        result.append(n * n)
    return result


def keys_of(config):
    out = []
    for key in config.keys():
        out.append(key)
    return out


def contains_negative(values):
    for value in values:
        if value < 0:
            return True
    return False


def describe(items):
    if len(items) == 0:
        return "empty"
    return "filled"


def join_words(words):
    text = ""
    for word in words:
        text += " "
    return text


def sum_squares(values):
    return sum([v * v for v in values])
'''

INDEX_NEEDED = '''\
def label(values):
    out = []
    for i in range(len(values)):
        out.append(str(i))
    return out
'''


@pytest.fixture(scope="module")
def kb() -> OkebKnowledgeBase:
    return OkebKnowledgeBase()


def test_kb_loads_every_rule(kb: OkebKnowledgeBase) -> None:
    assert len(kb.rules) == 160
    assert len(kb.by_id) == 160
    assert len(kb.categories) == 12


def test_canonical_ids_collapse_both_styles(kb: OkebKnowledgeBase) -> None:
    assert canonical_rule_id("OKEB-C1-S1-R01") == "C1.S1.R1"
    assert canonical_rule_id("C3.S1.R1") == "C3.S1.R1"
    assert kb.rule("OKEB-C1-S1-R01") is kb.rule("C1.S1.R1")


def test_null_subcategory_is_recovered_from_the_id(kb: OkebKnowledgeBase) -> None:
    rule = kb.rule("OKEB-C1-S4-R02")
    assert rule is not None
    assert rule["subcategory_id"] == "C1.S4"


def test_validation_has_no_problems(kb: OkebKnowledgeBase) -> None:
    # The rule base must be aligned with taxonomy.py: no errors, no drift.
    assert kb.validate() == []


def test_taxonomy_matches_its_source_document() -> None:
    # C11/C12 drifted once before (invented categories + a C12.S5 that does not
    # exist upstream), which left 7 rules unlabelled. Pin the shape.
    assert [category.id for category in ENERGY_SMELL_CATEGORIES] == [
        f"C{number}" for number in range(1, 13)
    ]
    assert sum(len(category.subcategories) for category in ENERGY_SMELL_CATEGORIES) == 65
    c11 = {sub.id: sub.name for sub in ENERGY_SMELL_CATEGORIES[10].subcategories}
    c12 = {sub.id: sub.name for sub in ENERGY_SMELL_CATEGORIES[11].subcategories}
    assert c11["C11.S4"] == "Blocking The Main Thread"
    assert list(c12) == ["C12.S1", "C12.S2", "C12.S3", "C12.S4"]
    assert c12["C12.S1"] == "Inefficient Large-Stride Traversal"


def test_every_rule_carries_taxonomy_labels(kb: OkebKnowledgeBase) -> None:
    for rule in kb.rules:
        assert rule["subcategory_id"], rule["canonical_id"]
        assert rule["category_name"], rule["canonical_id"]
        assert rule["subcategory_name"], rule["canonical_id"]


def test_c1_rules_have_a_stored_subcategory(kb: OkebKnowledgeBase) -> None:
    for rule in kb.rules:
        if rule["category"] == "C1":
            assert rule["subcategory"], rule["id"]  # not just recovered at runtime
            assert rule["subcategory_id"].startswith("C1.S")


def test_aligner_is_idempotent(kb: OkebKnowledgeBase) -> None:
    aligned, report = align(kb.data)
    assert report == []
    assert aligned["rules"] == kb.data["rules"]
    assert aligned["categories"] == kb.data["categories"]


def test_coverage_counts_implemented_matchers(kb: OkebKnowledgeBase) -> None:
    coverage = kb.coverage(IMPLEMENTED_RULE_IDS)
    assert coverage["rule_count"] == 160
    assert coverage["implemented_count"] == 8
    assert coverage["implemented_unknown_ids"] == []
    assert coverage["per_category"]["C1"] == {"rules": 24, "implemented": 0}


def test_every_implemented_rule_exists_in_the_kb(kb: OkebKnowledgeBase) -> None:
    for rule_id in IMPLEMENTED_RULE_IDS:
        assert kb.rule(rule_id) is not None, rule_id


def test_matcher_finds_every_supported_rule() -> None:
    result = identify_issues(SAMPLE, "sample.py")
    found = {issue["rule_id"] for issue in result["issues"]}
    assert found == set(IMPLEMENTED_RULE_IDS)
    assert result["summary"]["matcher_failures"] == []


def test_issue_carries_strategy_and_bindings() -> None:
    result = identify_issues(SAMPLE, "sample.py")
    issue = next(item for item in result["issues"] if item["rule_id"] == "C3.S1.R1")
    assert issue["capture"]["collection"] == "numbers"
    assert issue["capture"]["index"] == "i"
    assert issue["location"]["function"] == "total_and_max"
    assert issue["kb_rule_found"] is True
    assert issue["strategy"]  # prose comes from okeb.json, not the matcher
    assert issue["preconditions"]
    assert issue["evidence"] == "static structural match"


def test_index_reduction_uses_the_reduced_collection() -> None:
    result = identify_issues(SAMPLE, "sample.py")
    issue = next(item for item in result["issues"] if item["rule_id"] == "C3.S1.R4")
    assert issue["capture"]["accumulator"] == "best"
    assert issue["rewrite_hint"] == "best = max(numbers)"


def test_specific_rule_supersedes_the_general_one() -> None:
    result = identify_issues(SAMPLE, "sample.py")
    loop_rules = {
        issue["rule_id"]
        for issue in result["issues"]
        if issue["location"]["function"] == "keys_of"
    }
    assert loop_rules == {"C3.S1.R3"}


def test_guard_rejects_index_that_is_actually_needed() -> None:
    result = identify_issues(INDEX_NEEDED, "needed.py")
    rule_ids = {issue["rule_id"] for issue in result["issues"]}
    assert "C3.S1.R1" not in rule_ids
    assert "C3.S1.R2" in rule_ids


def test_unresolved_guard_is_reported_not_hidden() -> None:
    result = identify_issues(SAMPLE, "sample.py")
    issue = next(item for item in result["issues"] if item["rule_id"] == "C3.S5.R2")
    assert issue["guard_status"] == "unresolved"
    assert issue["confidence"] == "medium"


def test_selftest_cases_all_pass() -> None:
    report = run_selftest()

    assert report["failed_count"] == 0, [
        result for result in report["results"] if not result["passed"]
    ]
    assert report["passed_count"] == report["case_count"]


def test_every_implemented_rule_has_a_positive_and_negative_case() -> None:
    by_rule: dict[str, set[bool]] = {}
    for case in RULE_CASES:
        by_rule.setdefault(case.rule_id, set()).add(case.should_match)

    for rule_id in IMPLEMENTED_RULE_IDS:
        assert rule_id in by_rule, f"{rule_id} has no self-test case"
        assert by_rule[rule_id] == {True, False}, (
            f"{rule_id} needs both a positive and a negative case"
        )
    assert set(by_rule) <= set(IMPLEMENTED_RULE_IDS), (
        "cases reference rules that have no matcher"
    )


def test_non_python_is_rejected_explicitly() -> None:
    with pytest.raises(ValueError, match="Python-only"):
        identify_issues("int main() { return 0; }", "main.c", "c")
