"""OASIS Energy-Optimization Knowledge Base (OKEB) loader.

``okeb.json`` holds 160 optimization rules. Its ``detection``, ``strategy`` and
``preconditions`` fields are prose written for humans: they describe *what to
look for* and *what to do*, but they cannot be executed. This module turns the
document into an indexed object that a detector can cite and a prompt builder
can retrieve strategy text from.

Two things are deliberately *not* done here:

* No rule is treated as proven. Every rule is a hypothesis about a pattern;
  measurement is a separate stage (see ``modules/benchmarking``).
* No severity is invented. ``okeb.json`` has no impact or severity field, so
  this module exposes only what the file actually contains.

The structural repairs applied here are deliberately minimal:

* id canonicalisation: 24 C1 rules use the ``OKEB-C1-S1-R01`` style. ``okeb.json``
  keeps those source ids (they appear in prompts and audit logs), and
  ``canonical_id`` normalises every style to ``C1.S1.R1`` so there is one
  namespace at runtime.
* ``subcategory_id`` falls back to the id when ``subcategory`` is absent, which
  is how the C1 rules lost their label in the first place. ``okeb_align.py``
  has since written the field into the file; the fallback stays as a guard for
  hand-edited entries.

Category titles and every subcategory id/name follow
``third_party/energy-smells/taxonomy.md`` through ``taxonomy.py``;
``validate()`` reports any drift between the file and that module.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from modules.energy_detection.taxonomy import ENERGY_SMELL_CATEGORIES

DEFAULT_KB_PATH = Path(__file__).resolve().parents[2] / "okeb.json"

_ID_DOTTED = re.compile(r"^C(\d+)\.S(\d+)\.R(\d+)$")
_ID_OKEB = re.compile(r"^OKEB-C(\d+)-S(\d+)-R(\d+)$")

DETECTION_MODES = {"static", "hybrid", "profiling"}
FIX_MODES = {"suggest-only", "auto-fix-candidate"}
CLAIM_STRENGTHS = {"plausible-needs-measurement", "unproven"}

REQUIRED_FIELDS = ("id", "category", "pattern", "detection", "strategy", "preconditions")

# The knowledge base and ``taxonomy.py`` used to disagree about C11 and C12
# (an earlier taxonomy revision replaced both categories with different
# subjects). That split is resolved: both now mirror
# ``third_party/energy-smells/taxonomy.md``. Anything still diverging is
# reported by ``validate()`` as plain drift, not as an accepted conflict.


@dataclass(frozen=True)
class Problem:
    """One validation finding, safe to serialize to JSON."""

    level: str  # "error" | "warning"
    code: str
    message: str


def canonical_rule_id(rule_id: str) -> str:
    """Normalise ``OKEB-C1-S1-R01`` and ``C1.S1.R01`` to ``C1.S1.R1``."""
    value = str(rule_id).strip()
    for pattern in (_ID_DOTTED, _ID_OKEB):
        match = pattern.match(value)
        if match:
            category, subcategory, number = (int(part) for part in match.groups())
            return f"C{category}.S{subcategory}.R{number}"
    return value


def subcategory_id_from_rule_id(rule_id: str) -> str | None:
    """Recover ``C1.S1`` from either id style, or None when unparseable."""
    canonical = canonical_rule_id(rule_id)
    match = re.match(r"^(C\d+\.S\d+)\.R\d+$", canonical)
    return match.group(1) if match else None


def _category_number(category_id: str) -> int | None:
    match = re.match(r"^C(\d+)$", str(category_id))
    return int(match.group(1)) if match else None


class OkebKnowledgeBase:
    """Indexed, validated view of ``okeb.json``."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT_KB_PATH
        with self.path.open("r", encoding="utf-8") as handle:
            self.data: dict[str, Any] = json.load(handle)

        self.categories: dict[str, str] = {
            str(category["id"]): str(category["title"])
            for category in self.data.get("categories", [])
        }
        self._taxonomy_categories = {c.id: c.name for c in ENERGY_SMELL_CATEGORIES}
        self._taxonomy_subcategories = {
            sub.id: sub for cat in ENERGY_SMELL_CATEGORIES for sub in cat.subcategories
        }
        self._taxonomy_subcategory_names = {
            sub_id: sub.name for sub_id, sub in self._taxonomy_subcategories.items()
        }

        self.rules: list[dict[str, Any]] = [self._enrich(rule) for rule in self.data["rules"]]
        self.by_id: dict[str, dict[str, Any]] = {
            str(rule["canonical_id"]): rule for rule in self.rules
        }
        self.by_subcategory: dict[str, list[dict[str, Any]]] = {}
        for rule in self.rules:
            subcategory = rule.get("subcategory_id")
            if subcategory:
                self.by_subcategory.setdefault(str(subcategory), []).append(rule)

    # ------------------------------------------------------------
    # LOADING
    # ------------------------------------------------------------

    def _enrich(self, rule: dict[str, Any]) -> dict[str, Any]:
        """Copy a rule and add the derived identifiers used by detectors."""
        enriched = dict(rule)
        source_id = str(rule.get("id", ""))
        canonical = canonical_rule_id(source_id)
        subcategory = rule.get("subcategory") or subcategory_id_from_rule_id(source_id)
        enriched["canonical_id"] = canonical
        enriched["subcategory_id"] = subcategory
        enriched["category_id"] = str(rule.get("category", ""))
        enriched["category_title"] = self.categories.get(str(rule.get("category", "")))
        enriched["category_name"] = self._taxonomy_categories.get(
            str(rule.get("category", ""))
        )
        enriched["subcategory_name"] = self._taxonomy_subcategory_names.get(
            str(subcategory or "")
        )
        return enriched

    # ------------------------------------------------------------
    # ACCESS
    # ------------------------------------------------------------

    def rule(self, rule_id: str) -> dict[str, Any] | None:
        """Look up one rule by any accepted id style."""
        return self.by_id.get(canonical_rule_id(rule_id))

    def rules_for_subcategory(self, subcategory_id: str) -> list[dict[str, Any]]:
        return list(self.by_subcategory.get(subcategory_id, []))

    def strategy(self, rule_id: str) -> str | None:
        """The strategy text for a rule, or None when the id is unknown."""
        rule = self.rule(rule_id)
        return None if rule is None else str(rule.get("strategy", ""))

    # ------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------

    def validate(self) -> list[Problem]:
        """Structural checks over the knowledge base.

        Errors mean a consumer cannot trust the index (duplicate ids, unknown
        category). Warnings mean the data is readable but ambiguous, which is
        the case for the C11/C12 category conflict.
        """
        problems: list[Problem] = []

        seen: dict[str, str] = {}
        for rule in self.rules:
            source_id = str(rule.get("id", ""))
            canonical = str(rule["canonical_id"])
            if canonical in seen:
                problems.append(
                    Problem(
                        "error",
                        "duplicate_rule_id",
                        f"{source_id} and {seen[canonical]} both canonicalise to {canonical}.",
                    )
                )
            else:
                seen[canonical] = source_id

        for rule in self.rules:
            canonical = str(rule["canonical_id"])
            missing = [field for field in REQUIRED_FIELDS if not str(rule.get(field) or "").strip()]
            if missing:
                problems.append(
                    Problem(
                        "error",
                        "missing_field",
                        f"{canonical} is missing: {', '.join(missing)}.",
                    )
                )

            category = str(rule.get("category", ""))
            if category not in self.categories:
                problems.append(
                    Problem(
                        "error",
                        "unknown_category",
                        f"{canonical} references category {category!r}, which is not declared.",
                    )
                )

            subcategory = rule.get("subcategory_id")
            if not subcategory:
                problems.append(
                    Problem(
                        "warning",
                        "unknown_subcategory",
                        f"{canonical} has no subcategory and none can be inferred from its id.",
                    )
                )
            elif subcategory not in self._taxonomy_subcategories:
                problems.append(
                    Problem(
                        "error",
                        "unknown_subcategory",
                        f"{canonical} references {subcategory}, which taxonomy.py does not define.",
                    )
                )
            elif not str(subcategory).startswith(category + "."):
                problems.append(
                    Problem(
                        "error",
                        "subcategory_category_mismatch",
                        f"{canonical} is in {category} but maps to {subcategory}.",
                    )
                )

        for rule in self.rules:
            canonical = str(rule["canonical_id"])
            category = str(rule.get("category", ""))
            subcategory = str(rule.get("subcategory_id") or "")
            expected_subcategory = self._taxonomy_subcategory_names.get(subcategory)

            for field, expected, label in (
                ("category_name", self._taxonomy_categories.get(category), "category"),
                ("subcategory_name", expected_subcategory, "subcategory"),
            ):
                stored = rule.get(field)
                if stored is None:
                    problems.append(
                        Problem(
                            "warning",
                            "taxonomy_label_missing",
                            f"{canonical} has no {field}; run okeb_align.py --write.",
                        )
                    )
                elif expected is not None and stored != expected:
                    problems.append(
                        Problem(
                            "warning",
                            "taxonomy_label_drift",
                            f"{canonical} stores {label} name {stored!r}; "
                            f"taxonomy.py says {expected!r}.",
                        )
                    )

            derived = rule.get("derived") or {}
            for field, allowed in (
                ("detection_mode", DETECTION_MODES),
                ("fix_mode", FIX_MODES),
                ("energy_claim_strength", CLAIM_STRENGTHS),
            ):
                value = derived.get(field)
                if value is not None and value not in allowed:
                    problems.append(
                        Problem(
                            "warning",
                            "unknown_derived_value",
                            f"{canonical} has {field}={value!r}; expected one of {sorted(allowed)}.",
                        )
                    )

        problems.extend(self._check_counts())
        problems.extend(self._check_category_titles())
        problems.extend(self._check_duplicate_patterns())
        return problems

    def _check_counts(self) -> list[Problem]:
        problems: list[Problem] = []
        declared_total = self.data.get("meta", {}).get("rule_count")
        if declared_total is not None and int(declared_total) != len(self.rules):
            problems.append(
                Problem(
                    "warning",
                    "rule_count_mismatch",
                    f"meta.rule_count={declared_total} but {len(self.rules)} rules are present.",
                )
            )

        counts: dict[str, int] = {}
        for rule in self.rules:
            category = str(rule.get("category", ""))
            counts[category] = counts.get(category, 0) + 1

        for category in self.data.get("categories", []):
            declared = category.get("rule_count")
            actual = counts.get(str(category.get("id")), 0)
            if declared is not None and int(declared) != actual:
                problems.append(
                    Problem(
                        "warning",
                        "category_count_mismatch",
                        f"{category['id']} declares {declared} rules but {actual} are present.",
                    )
                )
        return problems

    def _check_category_titles(self) -> list[Problem]:
        """The file's category titles must be the taxonomy's titles."""
        problems: list[Problem] = []
        if self.data.get("meta", {}).get("taxonomy", {}).get("source") is None:
            problems.append(
                Problem(
                    "warning",
                    "taxonomy_source_missing",
                    "meta.taxonomy.source is unset; run okeb_align.py --write.",
                )
            )
        for category_id, okeb_title in self.categories.items():
            taxonomy_title = self._taxonomy_categories.get(category_id)
            if taxonomy_title is None:
                problems.append(
                    Problem(
                        "warning",
                        "category_not_in_taxonomy",
                        f"{category_id} ('{okeb_title}') is not defined by taxonomy.py.",
                    )
                )
            elif taxonomy_title != okeb_title:
                problems.append(
                    Problem(
                        "warning",
                        "category_title_mismatch",
                        f"{category_id}: okeb.json '{okeb_title}' vs "
                        f"taxonomy '{taxonomy_title}'.",
                    )
                )
        return problems

    def _check_duplicate_patterns(self) -> list[Problem]:
        """One pattern, one canonical rule; declared aliases are not duplicates."""
        problems: list[Problem] = []
        for rule in self.rules:
            alias = rule.get("duplicate_of")
            if alias and canonical_rule_id(str(alias)) not in self.by_id:
                problems.append(
                    Problem(
                        "error",
                        "unknown_duplicate_target",
                        f"{rule['canonical_id']} is an alias of {alias}, which is not a rule.",
                    )
                )

        groups: dict[str, list[str]] = {}
        for rule in self.rules:
            if rule.get("duplicate_of"):
                continue
            key = re.sub(r"[^a-z0-9]+", " ", str(rule.get("pattern", "")).lower()).strip()
            groups.setdefault(key, []).append(str(rule["canonical_id"]))

        for key, ids in groups.items():
            if key and len(ids) > 1:
                problems.append(
                    Problem(
                        "warning",
                        "duplicate_pattern",
                        f"'{key}' appears in {', '.join(sorted(ids))}; decide which one is canonical.",
                    )
                )
        return problems

    # ------------------------------------------------------------
    # COVERAGE
    # ------------------------------------------------------------

    def coverage(self, implemented: Iterable[str]) -> dict[str, Any]:
        """How much of the knowledge base can a detector actually evaluate.

        ``implemented`` is the set of canonical rule ids that have a runnable
        matcher. Rules without one are still retrievable strategy text; they
        simply cannot be *identified* from code yet.
        """
        executed = {canonical_rule_id(rule_id) for rule_id in implemented}
        known = set(self.by_id)
        per_category: dict[str, dict[str, int]] = {}
        for rule in self.rules:
            category = str(rule["category"])
            bucket = per_category.setdefault(category, {"rules": 0, "implemented": 0})
            bucket["rules"] += 1
            if str(rule["canonical_id"]) in executed:
                bucket["implemented"] += 1

        taxonomy_subcategories = set(self._taxonomy_subcategories)
        with_rules = set(self.by_subcategory)
        return {
            "rule_count": len(self.rules),
            "implemented_count": len(executed & known),
            "implemented_unknown_ids": sorted(executed - known),
            "per_category": per_category,
            "subcategories_without_rules": sorted(taxonomy_subcategories - with_rules),
            "subcategories_without_matcher": sorted(
                subcategory
                for subcategory in with_rules
                if not any(
                    str(rule["canonical_id"]) in executed
                    for rule in self.by_subcategory[subcategory]
                )
            ),
        }


# ------------------------------------------------------------
# MODULE-LEVEL HELPERS
# ------------------------------------------------------------

_KB: OkebKnowledgeBase | None = None


def load_kb(path: str | Path | None = None, *, refresh: bool = False) -> OkebKnowledgeBase:
    """Load (and cache) the knowledge base."""
    global _KB
    if _KB is None or refresh or path is not None:
        _KB = OkebKnowledgeBase(path)
    return _KB


__all__ = [
    "DEFAULT_KB_PATH",
    "OkebKnowledgeBase",
    "Problem",
    "canonical_rule_id",
    "load_kb",
    "subcategory_id_from_rule_id",
]
