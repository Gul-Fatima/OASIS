"""Detection results shaped for a developer, plus a copyable LLM prompt.

This is the product-facing layer over the two detectors:

* ``matcher.identify_issues`` supplies structural matches joined to ``okeb.json``
  (rule id, taxonomy labels, strategy, rewrite hint).
* ``detector.detect_smells`` supplies the broader pattern detections for code
  the structural matchers cannot see yet.

Both are merged into one list keyed by subcategory + line so the same statement
is not reported twice. Nothing here measures energy; the prompt is for a manual
LLM round-trip until the generation pipeline is wired in.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from modules.code_understanding.parser import parse_code
from modules.energy_detection.detector import detect_smells
from modules.energy_detection.matcher import identify_issues
from modules.energy_detection.prompts import PROMPT_MANUAL_OPTIMIZATION


def _issue_from_structural(issue: dict[str, Any]) -> dict[str, Any]:
    location = issue.get("location") or {}
    line = location.get("line")
    identifier = issue.get("subcategory_id") or issue.get("category_id")
    return {
        "id": f"{identifier}:{line}",
        "rule_id": issue.get("rule_id"),
        "category_id": issue.get("category_id"),
        "category_name": issue.get("category_name"),
        "subcategory_id": issue.get("subcategory_id"),
        "subcategory_name": issue.get("subcategory_name"),
        "title": issue.get("pattern", ""),
        "line": line,
        "function": location.get("function"),
        "strategy": issue.get("strategy", ""),
        "example": issue.get("rewrite_hint", ""),
        "origin": "structural",
    }


def _issue_from_detection(detection: dict[str, Any]) -> dict[str, Any]:
    location = detection.get("location") or {}
    line = location.get("line")
    identifier = detection.get("subcategory_id") or detection.get("category_id")
    return {
        "id": f"{identifier}:{line}",
        "rule_id": None,
        "category_id": detection.get("category_id"),
        "category_name": detection.get("category_name"),
        "subcategory_id": detection.get("subcategory_id"),
        "subcategory_name": detection.get("subcategory_name"),
        "title": detection.get("description", ""),
        "line": line,
        "function": location.get("function"),
        "strategy": detection.get("suggestion", ""),
        "example": "",
        "origin": "pattern",
    }


def collect_issues(
    source: str,
    filename: str = "<source>",
    language: str = "python",
) -> list[dict[str, Any]]:
    """Merge structural and pattern detections into one developer-facing list."""
    issues: list[dict[str, Any]] = []
    seen: set[tuple[str | None, int | None]] = set()

    if language == "python":
        for raw in identify_issues(source, filename, language)["issues"]:
            issue = _issue_from_structural(raw)
            seen.add((issue["subcategory_id"], issue["line"]))
            issues.append(issue)

    state = parse_code(source, filename, language)
    for detection in detect_smells(state, source, language):
        if detection.get("category_id") == "C0":  # detector failure, not a smell
            continue
        issue = _issue_from_detection(detection)
        key = (issue["subcategory_id"], issue["line"])
        if key in seen:
            continue
        seen.add(key)
        issues.append(issue)

    issues.sort(key=lambda item: (item["line"] or 0, str(item["id"])))
    return issues


def _render_issue(index: int, issue: dict[str, Any]) -> str:
    subcategory = issue.get("subcategory_id") or issue.get("category_id") or "issue"
    rule_id = issue.get("rule_id")
    identifier = f"{rule_id} ({subcategory})" if rule_id else subcategory
    name = issue.get("subcategory_name") or issue.get("category_name") or ""
    where = f"line {issue['line']}" if issue.get("line") else "unknown line"
    if issue.get("function"):
        where = f"{where}, in {issue['function']}()"

    lines = [f"{index}. [{identifier}] {name} ({where})"]
    if issue.get("title"):
        lines.append(f"   Issue: {issue['title']}")
    if issue.get("strategy"):
        lines.append(f"   Strategy: {issue['strategy']}")
    if issue.get("example"):
        lines.append(f"   Suggested rewrite: {issue['example']}")
    return "\n".join(lines)


def build_prompt(
    source: str,
    filename: str,
    language: str,
    issues: list[dict[str, Any]],
) -> str:
    """The prompt a developer copies into their own LLM."""
    if not issues:
        return ""

    rendered = "\n\n".join(
        _render_issue(index, issue) for index, issue in enumerate(issues, start=1)
    )
    return PROMPT_MANUAL_OPTIMIZATION.format(
        issues=rendered,
        filename=Path(filename).name,
        language=language,
        code=source,
    )


def analyze(
    source: str,
    filename: str = "file.py",
    language: str = "python",
) -> dict[str, Any]:
    """Everything the Analyze screen needs for one file."""
    issues = collect_issues(source, filename, language)
    return {
        "filename": Path(filename).name,
        "language": language,
        "line_count": len(source.splitlines()),
        "issue_count": len(issues),
        "issues": issues,
        "prompt": build_prompt(source, filename, language, issues),
    }


__all__ = ["analyze", "build_prompt", "collect_issues"]
