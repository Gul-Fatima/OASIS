"""Candidate prioritisation.

Ranking decides which candidates deserve the expensive verification and
benchmarking steps. It is prioritisation, never validation: a top-ranked
candidate can still fail verification or measure worse (CLAUDE.md section 7).

Deliberately not a single LLM-confidence number — energy potential, smell
coverage, code-change risk and the model's own confidence all contribute, and
missing values degrade gracefully rather than crash.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

IMPACT_SCORES = {"low": 0.4, "medium": 0.7, "high": 1.0}


@dataclass
class RankWeights:
    """Configurable weights for the ranking score (CLAUDE.md section 7)."""

    energy_potential: float = 0.35
    correctness_confidence: float = 0.20
    smell_coverage: float = 0.15
    low_risk: float = 0.30

    def to_dict(self) -> dict[str, float]:
        return asdict(self)

    def normalised(self) -> "RankWeights":
        total = (
            self.energy_potential
            + self.correctness_confidence
            + self.smell_coverage
            + self.low_risk
        )
        if total <= 0:
            return RankWeights()
        return RankWeights(
            energy_potential=self.energy_potential / total,
            correctness_confidence=self.correctness_confidence / total,
            smell_coverage=self.smell_coverage / total,
            low_risk=self.low_risk / total,
        )


def estimate_risk(candidate: dict[str, Any], original_code: str = "") -> float:
    """Heuristic transformation risk in the range 0 (safe) .. 1 (risky).

    Proxies: how much larger the rewrite is than the original, and how many
    discrete changes the model reported. Larger rewrites are harder to review.
    """
    candidate_code = str(candidate.get("source_code") or "")
    if not candidate_code.strip():
        return 1.0

    original_lines = max(1, len(original_code.splitlines())) if original_code else 0
    candidate_lines = len(candidate_code.splitlines())

    size_risk = 0.0
    if original_lines:
        growth = (candidate_lines - original_lines) / original_lines
        size_risk = min(1.0, max(0.0, growth))

    changes = candidate.get("changes_made") or []
    change_risk = min(1.0, len(changes) * 0.12) if isinstance(changes, list) else 0.0

    return round(min(1.0, size_risk * 0.5 + change_risk * 0.5), 4)


def score_candidate(
    candidate: dict[str, Any],
    original_code: str = "",
    detection_count: int = 0,
    weights: RankWeights | None = None,
) -> dict[str, Any]:
    """Score one candidate and explain the score.

    Returns the candidate's ``score`` (0..100), the individual ``factors``
    and a human-readable ``rationale``.
    """
    weights = (weights or RankWeights()).normalised()

    impact = str(candidate.get("predicted_impact") or "unknown").lower()
    energy_potential = IMPACT_SCORES.get(impact)
    missing: list[str] = []
    if energy_potential is None:
        energy_potential = 0.0
        missing.append("predicted impact")

    confidence = candidate.get("confidence")
    try:
        confidence = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        confidence = 0.0
        missing.append("model confidence")

    target_smells = candidate.get("target_smells") or []
    if detection_count > 0 and isinstance(target_smells, list):
        coverage = min(1.0, len(target_smells) / detection_count)
    else:
        coverage = 0.5 if target_smells else 0.0
        if not target_smells:
            missing.append("target smells")

    risk = float(candidate.get("risk", estimate_risk(candidate, original_code)))
    low_risk = 1.0 - risk

    score = (
        weights.energy_potential * energy_potential
        + weights.correctness_confidence * confidence
        + weights.smell_coverage * coverage
        + weights.low_risk * low_risk
    ) * 100.0

    rationale: list[str] = [
        f"Predicted energy impact: {impact} ({energy_potential:.2f})",
        f"Model confidence: {confidence:.2f}",
        f"Smell coverage: {coverage:.2f}"
        + (f" of {detection_count} detected" if detection_count else ""),
        f"Transformation risk: {risk:.2f} (lower is safer)",
    ]
    if missing:
        rationale.append("Missing inputs defaulted to 0: " + ", ".join(missing))

    return {
        "score": round(score, 2),
        "factors": {
            "energy_potential": round(energy_potential, 4),
            "correctness_confidence": round(confidence, 4),
            "smell_coverage": round(coverage, 4),
            "transformation_risk": round(risk, 4),
            "low_risk": round(low_risk, 4),
        },
        "weights": weights.to_dict(),
        "rationale": rationale,
        "missing_inputs": missing,
    }


def rank_candidates(
    candidates: list[dict[str, Any]],
    original_code: str = "",
    detection_count: int = 0,
    weights: RankWeights | None = None,
) -> list[dict[str, Any]]:
    """Return candidates ordered by descending score, with rank annotations."""
    weights = weights or RankWeights()
    scored: list[dict[str, Any]] = []

    for candidate in candidates:
        result = score_candidate(
            candidate,
            original_code=original_code,
            detection_count=detection_count,
            weights=weights,
        )
        enriched = dict(candidate)
        enriched.update(result)
        scored.append(enriched)

    scored.sort(key=lambda item: item["score"], reverse=True)
    for index, item in enumerate(scored, start=1):
        item["rank"] = index

    return scored


__all__ = ["RankWeights", "estimate_risk", "rank_candidates", "score_candidate"]
