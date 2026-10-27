"""Align ``okeb.json`` onto the canonical taxonomy in ``taxonomy.py``.

The knowledge base and the taxonomy came from two different editorial passes:
category titles were worded differently (``Redundant / Dead Computation and
Data Flow`` vs ``Redundant Computation``), the 24 C1 rules carried
``subcategory: null`` and ``OKEB-C1-S1-R01`` ids, and no rule stored the
taxonomy *name* of its category or subcategory. Downstream code therefore had
to re-derive labels at runtime, which is where the C11/C12 confusion came from.

This module is the single, repeatable repair. It does four things:

1. Rewrites every ``categories[]`` entry so ``title``/``description`` are the
   taxonomy's, keeping the original wording in ``okeb_title`` for traceability.
2. Fills ``subcategory`` on every rule (recovered from the id where it was
   ``null``) and adds ``category_name``/``subcategory_name`` from the taxonomy.
3. Recomputes ``rule_count`` on every category and in ``meta``.
4. Records where the taxonomy came from, so the file is self-describing.

Rule ids are left alone: ``OKEB-C1-S1-R01`` stays, because the id is the join
key used in Git history, prompts and audit logs; ``rulebase.canonical_rule_id``
already normalises it to ``C1.S1.R1``.

Usage (from the OASIS root)::

    python -m modules.energy_detection.okeb_align --check   # exit 1 on drift
    python -m modules.energy_detection.okeb_align --write   # rewrite okeb.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from modules.energy_detection.rulebase import DEFAULT_KB_PATH, canonical_rule_id
from modules.energy_detection.rulebase import subcategory_id_from_rule_id
from modules.energy_detection.taxonomy import ENERGY_SMELL_CATEGORIES

TAXONOMY_SOURCE = "third_party/energy-smells/taxonomy.md"

# The source document files the same optimization twice. ``C3.S2`` is literally
# "Recomputing Loop-Invariant Values", so it keeps the canonical entry; the
# generic ``C1.S4`` (Repeated Computation) twin is recorded as an alias rather
# than deleted, so its citations and prompt text stay retrievable.
RULE_ALIASES = {"C1.S4.R2": "C3.S2.R2"}

# Field order for rewritten rules. Unknown keys are appended after these, so a
# future hand-added field survives an alignment run instead of being dropped.
RULE_FIELD_ORDER = (
    "id",
    "source_id",
    "category",
    "category_name",
    "subcategory",
    "subcategory_name",
    "duplicate_of",
    "pattern",
    "detection",
    "strategy",
    "preconditions",
    "expected_benefit",
    "references_raw",
    "references",
    "reference_urls",
    "derived",
)

CATEGORY_FIELD_ORDER = (
    "id",
    "title",
    "okeb_title",
    "description",
    "taxonomy_alignment",
    "rule_count",
    "subcategories",
    "references",
)

_TAXONOMY_CATEGORIES = {category.id: category for category in ENERGY_SMELL_CATEGORIES}
_TAXONOMY_SUBCATEGORIES = {
    subcategory.id: subcategory
    for category in ENERGY_SMELL_CATEGORIES
    for subcategory in category.subcategories
}


def _ordered(source: dict[str, Any], order: tuple[str, ...]) -> dict[str, Any]:
    """``source`` with ``order`` first, then any extra keys in their old order."""
    result = {key: source[key] for key in order if key in source}
    for key, value in source.items():
        if key not in result:
            result[key] = value
    return result


def align_categories(data: dict[str, Any], report: list[str]) -> None:
    counts: dict[str, int] = {}
    for rule in data["rules"]:
        category_id = str(rule.get("category", ""))
        counts[category_id] = counts.get(category_id, 0) + 1

    by_id = {str(category.get("id")): category for category in data["categories"]}
    missing = [category_id for category_id in _TAXONOMY_CATEGORIES if category_id not in by_id]
    for category_id in missing:
        report.append(f"added missing category entry {category_id}")
        by_id[category_id] = {"id": category_id, "references": []}
    unknown = [category_id for category_id in by_id if category_id not in _TAXONOMY_CATEGORIES]
    for category_id in unknown:
        report.append(f"kept category {category_id}; the taxonomy does not define it")

    aligned: list[dict[str, Any]] = []
    for category_id, category in _TAXONOMY_CATEGORIES.items():
        entry = dict(by_id[category_id])
        original_title = str(entry.get("title", "")).strip()

        if original_title and original_title != category.name:
            # Preserve the first-seen wording; never overwrite it on re-runs.
            entry.setdefault("okeb_title", original_title)
            report.append(f"{category_id} title: {original_title!r} -> {category.name!r}")
        entry["title"] = category.name
        entry["description"] = category.description
        entry["taxonomy_alignment"] = (
            "renamed" if entry.get("okeb_title") else "identical"
        )
        entry["subcategories"] = [
            {"id": subcategory.id, "name": subcategory.name}
            for subcategory in category.subcategories
        ]
        entry["rule_count"] = counts.get(category_id, 0)
        if entry["rule_count"] == 0:
            report.append(f"{category_id} has no rules in the knowledge base")
        aligned.append(_ordered(entry, CATEGORY_FIELD_ORDER))

    data["categories"] = aligned


def align_rules(data: dict[str, Any], report: list[str]) -> None:
    aligned: list[dict[str, Any]] = []
    for rule in data["rules"]:
        entry = dict(rule)
        rule_id = str(entry.get("id", ""))
        category_id = str(entry.get("category", ""))

        subcategory_id = entry.get("subcategory") or subcategory_id_from_rule_id(rule_id)
        if not entry.get("subcategory") and subcategory_id:
            report.append(f"{rule_id}: subcategory recovered from id ({subcategory_id})")
            entry["subcategory"] = subcategory_id

        category = _TAXONOMY_CATEGORIES.get(category_id)
        if category is None:
            report.append(f"{rule_id}: category {category_id!r} is not in the taxonomy")
        else:
            entry["category_name"] = category.name

        alias = RULE_ALIASES.get(canonical_rule_id(rule_id))
        if alias:
            entry["duplicate_of"] = alias
        elif "duplicate_of" in entry:
            # An alias that was withdrawn must not linger in the file.
            entry.pop("duplicate_of")

        subcategory = _TAXONOMY_SUBCATEGORIES.get(str(subcategory_id or ""))
        if subcategory is None:
            report.append(
                f"{rule_id}: subcategory {subcategory_id!r} is not in the taxonomy"
            )
        else:
            if not str(subcategory_id).startswith(category_id + "."):
                report.append(
                    f"{rule_id}: subcategory {subcategory_id} is outside {category_id}"
                )
            entry["subcategory_name"] = subcategory.name

        aligned.append(_ordered(entry, RULE_FIELD_ORDER))

    data["rules"] = aligned


def align_meta(data: dict[str, Any], report: list[str]) -> None:
    meta = dict(data.get("meta") or {})
    rule_count = len(data["rules"])
    if meta.get("rule_count") != rule_count:
        report.append(f"meta.rule_count: {meta.get('rule_count')} -> {rule_count}")
    meta["rule_count"] = rule_count

    # Keep the import-time notes, but drop the ones this alignment resolved.
    # Alignment-owned notes are rewritten (not appended) so re-runs are stable.
    resolved = (
        "C1 uses OKEB- prefix in source IDs; normalized to C1.Sx.Ry.",
        "C11 contains only subcategory S4 (S1-S3 not in source).",
    )
    alignment_notes = [
        "C1 rules keep their OKEB-Cx-Sy-Rzz source ids; subcategory is stored "
        "explicitly and the dotted form is derived by canonical_rule_id.",
        "Category titles and all subcategory ids/names follow "
        f"{TAXONOMY_SOURCE} via modules/energy_detection/taxonomy.py.",
        "C11 rules exist only for S4; S1, S2, S3 and S5 have no rules in the "
        "source document (reported by OkebKnowledgeBase.coverage).",
    ]
    owned = tuple(resolved) + tuple(alignment_notes)
    issues = [
        note
        for note in meta.get("known_source_issues") or []
        if not any(note.startswith(prefix.rstrip(".")) for prefix in owned)
    ]
    issues.extend(alignment_notes)
    if meta.get("known_source_issues") != issues:
        report.append("meta.known_source_issues updated")
    meta["known_source_issues"] = issues

    taxonomy = {
        "source": TAXONOMY_SOURCE,
        "module": "modules/energy_detection/taxonomy.py",
        "categories": len(ENERGY_SMELL_CATEGORIES),
        "subcategories": len(_TAXONOMY_SUBCATEGORIES),
        "alignment_tool": "modules/energy_detection/okeb_align.py",
    }
    if meta.get("taxonomy") != taxonomy:
        report.append("meta.taxonomy recorded")
    meta["taxonomy"] = taxonomy

    data["meta"] = meta


def align(data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Return an aligned copy of ``data`` plus a human-readable change report."""
    result = json.loads(json.dumps(data))  # deep copy, keeps key order
    report: list[str] = []
    align_meta(result, report)
    align_categories(result, report)
    align_rules(result, report)
    return result, report


def _render(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--path", default=str(DEFAULT_KB_PATH))
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="report drift, do not write")
    group.add_argument("--write", action="store_true", help="rewrite the rule base")
    args = parser.parse_args(argv)

    path = Path(args.path)
    data = json.loads(path.read_text(encoding="utf-8"))
    aligned, report = align(data)

    for line in report:
        print(line)

    if args.check:
        unchanged = _render(aligned) == path.read_text(encoding="utf-8")
        print("okeb.json matches the taxonomy" if unchanged else "okeb.json is out of sync")
        return 0 if unchanged else 1

    path.write_text(_render(aligned), encoding="utf-8", newline="\n")
    print(f"wrote {path} ({len(report)} changes, {len(aligned['rules'])} rules)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
