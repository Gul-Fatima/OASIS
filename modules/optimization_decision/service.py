"""Optimization decision — the only place a candidate is called successful.

Decision hierarchy (module CLAUDE.md):

    Correctness → Benchmark validity → Measured energy → Performance → Resources

A candidate is IMPROVED only when it is verified *and* an empirical benchmark
shows a measured energy reduction larger than the measurement noise. Predicted
values never enter this calculation.

Adoption itself stays with the developer: ``record_decision`` stores an
ACCEPTED/REJECTED action in ``results/decisions.jsonl`` (experiment history).
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from modules.config import results_dir

# Outcomes (module CLAUDE.md).
IMPROVED = "IMPROVED"
NEUTRAL = "NEUTRAL"
REGRESSED = "REGRESSED"
FAILED = "FAILED"
REJECTED = "REJECTED"
ACCEPTED = "ACCEPTED"

DEFAULT_MIN_IMPROVEMENT_PERCENT = 5.0
MIN_NOISE_FLOOR_PERCENT = 2.0
MAX_NOISE_FLOOR_PERCENT = 25.0


@dataclass
class DecisionResult:
    """Outcome plus the evidence trail behind it."""

    status: str
    recommendation: str
    rationale: list[str] = field(default_factory=list)
    measured_improvement_percent: float | None = None
    predicted_impact: str | None = None
    considered_noise_floor_percent: float = MIN_NOISE_FLOOR_PERCENT
    correctness_status: str | None = None
    benchmark_status: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    decided_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def noise_floor_percent(benchmark: dict[str, Any] | None) -> float:
    """Estimate the measurement noise floor from the benchmark spread.

    Small differences between runs are environmental noise; the threshold for
    calling something an improvement grows with the observed spread.
    """
    if not benchmark:
        return MIN_NOISE_FLOOR_PERCENT

    spreads = [
        benchmark.get("original_summary", {}).get("energy_spread_percent"),
        benchmark.get("candidate_summary", {}).get("energy_spread_percent"),
    ]
    observed = [float(s) for s in spreads if isinstance(s, (int, float))]
    if not observed:
        return MIN_NOISE_FLOOR_PERCENT

    return round(
        min(MAX_NOISE_FLOOR_PERCENT, max(MIN_NOISE_FLOOR_PERCENT, max(observed))), 2
    )


def decide(
    candidate: dict[str, Any] | None = None,
    verification: dict[str, Any] | None = None,
    benchmark: dict[str, Any] | None = None,
    min_improvement_percent: float = DEFAULT_MIN_IMPROVEMENT_PERCENT,
) -> DecisionResult:
    """Classify a candidate using correctness first, then measured energy."""
    candidate = candidate or {}
    rationale: list[str] = []

    predicted_impact = candidate.get("predicted_impact")

    # ----------------------------------------------------------
    # 1. CORRECTNESS GATE
    # ----------------------------------------------------------
    if verification is None:
        return DecisionResult(
            status="VERIFICATION_PENDING",
            recommendation="Run correctness verification before any energy claim.",
            rationale=["No verification result supplied."],
            predicted_impact=predicted_impact,
            benchmark_status=(benchmark or {}).get("status"),
        )

    correctness_status = verification.get("status")
    if not verification.get("passed"):
        if verification.get("inconclusive"):
            rationale.append(
                "Correctness could not be established automatically, so the "
                "candidate cannot be promoted."
            )
            rationale.append("Supply test cases or run the project's test suite.")
            return DecisionResult(
                status="VERIFICATION_PENDING",
                recommendation="Collect stronger correctness evidence.",
                rationale=rationale,
                predicted_impact=predicted_impact,
                correctness_status=correctness_status,
                benchmark_status=(benchmark or {}).get("status"),
                evidence={"verification": verification},
            )

        rationale.append("Candidate failed correctness verification.")
        rationale.append("Correctness has priority over energy: the candidate is rejected.")
        return DecisionResult(
            status=FAILED,
            recommendation="Discard the candidate — behaviour changed.",
            rationale=rationale,
            predicted_impact=predicted_impact,
            correctness_status=correctness_status,
            benchmark_status=(benchmark or {}).get("status"),
            evidence={"verification": verification},
        )

    rationale.append("Correctness verification passed.")

    # ----------------------------------------------------------
    # 2. BENCHMARK VALIDITY GATE
    # ----------------------------------------------------------
    if benchmark is None:
        return DecisionResult(
            status="BENCHMARK_PENDING",
            recommendation="Correct — now measure energy before claiming a saving.",
            rationale=rationale + ["No benchmark has been run yet."],
            predicted_impact=predicted_impact,
            correctness_status=correctness_status,
            evidence={"verification": verification},
        )

    benchmark_status = benchmark.get("status")
    improvement = benchmark.get("improvement_percent")

    if benchmark_status != "MEASURED" or improvement is None:
        rationale.append(
            f"Benchmark did not produce usable measurements (status: {benchmark_status})."
        )
        errors = benchmark.get("errors") or []
        rationale.extend(str(error) for error in errors[:3])
        return DecisionResult(
            status=FAILED,
            recommendation="Fix the benchmark before drawing conclusions.",
            rationale=rationale,
            predicted_impact=predicted_impact,
            correctness_status=correctness_status,
            benchmark_status=benchmark_status,
            evidence={"verification": verification, "benchmark": benchmark},
        )

    # ----------------------------------------------------------
    # 3. MEASURED ENERGY
    # ----------------------------------------------------------
    floor = noise_floor_percent(benchmark)
    threshold = round(max(float(min_improvement_percent), floor), 2)

    rationale.append(
        f"Measured energy change: {improvement:+.2f}% "
        f"(positive means the candidate used less energy)."
    )
    rationale.append(
        f"Decision threshold: {threshold:.2f}% (measurement noise floor {floor:.2f}%)."
    )

    if improvement >= threshold:
        status = IMPROVED
        recommendation = "Measured improvement exceeds the noise floor — safe to review."
    elif improvement <= -threshold:
        status = REGRESSED
        recommendation = "Measured regression — do not adopt."
    else:
        status = NEUTRAL
        recommendation = (
            "Difference is within measurement noise; not evidence of a real saving."
        )

    # ----------------------------------------------------------
    # 4. PERFORMANCE / RESOURCE TRADE-OFFS (context, never the decider)
    # ----------------------------------------------------------
    original_summary = benchmark.get("original_summary") or {}
    candidate_summary = benchmark.get("candidate_summary") or {}
    original_time = original_summary.get("mean_duration_seconds")
    candidate_time = candidate_summary.get("mean_duration_seconds")

    time_change = None
    if original_time and candidate_time and original_time > 0:
        time_change = (original_time - candidate_time) / original_time * 100

    if time_change is not None:
        rationale.append(f"Execution time change: {time_change:+.2f}% (faster is positive).")
        if status == IMPROVED and time_change < -threshold:
            rationale.append(
                "The candidate saved energy but ran measurably slower — confirm the "
                "trade-off is acceptable."
            )
        if status != IMPROVED and time_change > threshold and improvement <= 0:
            rationale.append(
                "The candidate is faster but used no less energy: performance alone "
                "does not imply an energy improvement."
            )

    if predicted_impact and predicted_impact != "unknown":
        rationale.append(
            f"Note: the model predicted '{predicted_impact}' impact. Prediction is "
            "recorded for comparison only and did not affect this verdict."
        )

    return DecisionResult(
        status=status,
        recommendation=recommendation,
        rationale=rationale,
        measured_improvement_percent=round(float(improvement), 4),
        predicted_impact=predicted_impact,
        considered_noise_floor_percent=threshold,
        correctness_status=correctness_status,
        benchmark_status=benchmark_status,
        evidence={
            "verification": verification,
            "benchmark": benchmark,
            "time_change_percent": time_change,
        },
    )


def record_decision(
    candidate_id: str,
    status: str,
    developer_action: str,
    rationale: list[str] | None = None,
    measured_improvement_percent: float | None = None,
) -> dict[str, Any]:
    """Persist a human accept/reject decision to the experiment history."""
    action = developer_action.strip().upper()
    if action not in {ACCEPTED, REJECTED}:
        raise ValueError("developer_action must be ACCEPTED or REJECTED.")

    record = {
        "candidate_id": candidate_id,
        "status": status,
        "measured_improvement_percent": measured_improvement_percent,
        "rationale": rationale or [],
        "developer_action": action,
        "timestamp": time.time(),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }

    history_file = results_dir() / "decisions.jsonl"
    with history_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")

    record["history_file"] = str(history_file)
    return record


def load_decision_history(limit: int = 50) -> list[dict[str, Any]]:
    """Read the most recent decisions (newest first)."""
    history_file = results_dir() / "decisions.jsonl"
    if not history_file.exists():
        return []

    records: list[dict[str, Any]] = []
    for line in history_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    records.reverse()
    return records[:limit]


__all__ = [
    "ACCEPTED",
    "DEFAULT_MIN_IMPROVEMENT_PERCENT",
    "DecisionResult",
    "FAILED",
    "IMPROVED",
    "NEUTRAL",
    "REGRESSED",
    "REJECTED",
    "decide",
    "load_decision_history",
    "noise_floor_percent",
    "record_decision",
]
