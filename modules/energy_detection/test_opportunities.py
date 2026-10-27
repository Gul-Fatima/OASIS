"""Tests for the developer-facing analysis layer."""

from __future__ import annotations

from modules.energy_detection.opportunities import analyze, collect_issues

SAMPLE = """\
def squares(numbers):
    result = []
    for n in numbers:
        result.append(n * n)
    return result


def keys_of(config):
    keys = []
    for key in config.keys():
        keys.append(key)
    return keys
"""


def test_issues_carry_taxonomy_labels_and_strategies() -> None:
    report = analyze(SAMPLE, "sample.py", "python")

    assert report["issue_count"] >= 2
    rule_ids = {issue["rule_id"] for issue in report["issues"] if issue["rule_id"]}
    assert "C3.S1.R2" in rule_ids
    assert "C3.S1.R3" in rule_ids

    for issue in report["issues"]:
        assert issue["subcategory_id"], issue
        assert issue["subcategory_name"], issue
        assert issue["line"], issue
        assert issue["strategy"], issue


def test_prompt_contains_every_issue_and_the_source() -> None:
    report = analyze(SAMPLE, "sample.py", "python")
    prompt = report["prompt"]

    assert prompt
    assert "def squares" in prompt
    assert "C3.S1.R2" in prompt
    for issue in report["issues"]:
        marker = issue["rule_id"] or issue["subcategory_id"]
        assert marker in prompt, issue
    # The prompt is pasted into third-party tools; keep it ASCII-safe.
    assert all(ord(character) < 128 for character in prompt)


def test_clean_file_produces_no_prompt() -> None:
    report = analyze("def add(a, b):\n    return a + b\n", "clean.py", "python")

    assert report["issue_count"] == 0
    assert report["prompt"] == ""


def test_issues_are_not_duplicated_by_the_pattern_detector() -> None:
    issues = collect_issues(SAMPLE, "sample.py", "python")

    identifiers = [issue["id"] for issue in issues]
    assert len(identifiers) == len(set(identifiers))
