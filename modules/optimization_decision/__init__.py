"""Optimization Decision Module

Combines correctness, benchmarking and measured energy results to determine
the outcome of an optimization candidate. Final adoption always remains a
human decision.
"""

from .service import (
    ACCEPTED,
    DEFAULT_MIN_IMPROVEMENT_PERCENT,
    FAILED,
    IMPROVED,
    NEUTRAL,
    REGRESSED,
    REJECTED,
    DecisionResult,
    decide,
    load_decision_history,
    noise_floor_percent,
    record_decision,
)

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
