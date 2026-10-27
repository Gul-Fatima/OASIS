"""LLM-assisted candidate generation.

Takes the energy smells detected in a file and asks the LLM for alternative
implementations that preserve functional correctness.

Design rules from CLAUDE.md:

* The LLM is an assistant, never an authority: an "estimated_impact" from the
  model is recorded as a *prediction* and never as a measured saving.
* Generated code is untrusted input — nothing here executes it. Execution
  belongs to the verification and benchmarking services.
* Every candidate carries enough metadata to be reproduced and audited
  (see CLAUDE.md section 13).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from modules.candidate_generation.llm_client import (
    LLMError,
    GeminiClient,
    LLMNotConfigured,
)
from modules.candidate_generation.prompts import (
    PROMPT_MULTI_CANDIDATE,
    PROMPT_OPTIMIZATION,
    PROMPT_SYSTEM,
)

# Predicted impact tiers -> a coarse numeric weight used by the ranker.
IMPACT_WEIGHTS = {"low": 0.4, "medium": 0.7, "high": 1.0}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def code_fingerprint(code: str) -> str:
    """Stable short id for a piece of source code."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()[:12]


@dataclass
class Candidate:
    """One generated optimization candidate (CLAUDE.md section 13)."""

    candidate_id: str
    source_code: str
    parent_code_id: str
    opportunity_id: str
    strategy: str
    generation_method: str
    model: str
    target_smells: list[str] = field(default_factory=list)
    changes_made: list[dict[str, Any]] = field(default_factory=list)
    explanation: str = ""
    predicted_impact: str = "unknown"
    predicted_impact_score: float = 0.0
    confidence: float = 0.0
    correctness_status: str = "VERIFICATION_PENDING"
    benchmark_status: str = "BENCHMARK_PENDING"
    measured_energy: dict[str, Any] | None = None
    measured_time: dict[str, Any] | None = None
    measured_resources: dict[str, Any] | None = None
    final_status: str = "PREDICTED"
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_code": self.source_code,
            "parent_code_id": self.parent_code_id,
            "opportunity_id": self.opportunity_id,
            "strategy": self.strategy,
            "generation_method": self.generation_method,
            "model": self.model,
            "target_smells": self.target_smells,
            "changes_made": self.changes_made,
            "explanation": self.explanation,
            "predicted_impact": self.predicted_impact,
            "predicted_impact_score": self.predicted_impact_score,
            "confidence": self.confidence,
            "correctness_status": self.correctness_status,
            "benchmark_status": self.benchmark_status,
            "measured_energy": self.measured_energy,
            "measured_time": self.measured_time,
            "measured_resources": self.measured_resources,
            "final_status": self.final_status,
            "created_at": self.created_at,
            # Explicit reminder for the UI: nothing measured yet.
            "measurement_available": self.measured_energy is not None,
        }


def format_detections(detections: list[dict[str, Any]]) -> str:
    """Render detections as the compact text block the prompts expect."""
    if not detections:
        return "No specific energy smells were detected."

    lines: list[str] = []
    for index, detection in enumerate(detections, start=1):
        identifier = detection.get("subcategory_id") or detection.get("category_id")
        name = detection.get("subcategory_name") or detection.get("category_name")
        location = detection.get("location") or {}
        where = location.get("function") or location.get("file") or "file"
        line_no = location.get("line")
        position = f"{where} line {line_no}" if line_no else str(where)

        # The regex detector emits description/suggestion; the structural
        # matcher emits pattern/strategy from okeb.json. Accept both rather than
        # handing the model an empty Issue line.
        description = detection.get("description") or detection.get("pattern") or ""
        direction = detection.get("suggestion") or detection.get("strategy") or ""

        lines.append(
            f"{index}. [{identifier}] {name} ({detection.get('severity', 'unknown')} severity)\n"
            f"   Location: {position}\n"
            f"   Issue: {description}\n"
            f"   Suggested direction: {direction}"
        )

    return "\n".join(lines)


class CandidateGenerator:
    """Generates optimization candidates with the configured LLM."""

    def __init__(self, client: GeminiClient | None = None) -> None:
        self.client = client or GeminiClient()

    @property
    def is_available(self) -> bool:
        return self.client.is_configured

    # ------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------

    def generate(
        self,
        source_code: str,
        detections: list[dict[str, Any]],
        language: str = "python",
        num_candidates: int = 1,
        path: str = "<unknown>",
    ) -> list[Candidate]:
        """Generate ``num_candidates`` optimization candidates.

        Raises ``LLMNotConfigured`` when no API key is set and ``LLMError``
        when the provider fails, so the caller can pick the right HTTP status.
        """
        if not detections:
            raise ValueError(
                "No energy smell detections were provided; nothing to optimise."
            )

        num_candidates = max(1, min(int(num_candidates), 5))
        parent_code_id = code_fingerprint(source_code)
        detections_text = format_detections(detections)
        opportunity_id = f"opp-{parent_code_id}"

        if num_candidates == 1:
            payload = self.client.generate_json(
                PROMPT_OPTIMIZATION.format(
                    detections=detections_text,
                    language=language,
                    original_code=source_code,
                ),
                system_instruction=PROMPT_SYSTEM,
            )
            raw_candidates = [payload]
        else:
            payload = self.client.generate_json(
                PROMPT_MULTI_CANDIDATE.format(
                    detections=detections_text,
                    language=language,
                    original_code=source_code,
                    num_candidates=num_candidates,
                ),
                system_instruction=PROMPT_SYSTEM,
            )
            raw_candidates = payload.get("candidates") or []
            if not raw_candidates:
                raise LLMError("The model returned no candidates.")

        candidates: list[Candidate] = []
        for index, raw in enumerate(raw_candidates, start=1):
            if not isinstance(raw, dict):
                continue
            candidate = self._build_candidate(
                raw=raw,
                index=index,
                source_code=source_code,
                parent_code_id=parent_code_id,
                opportunity_id=opportunity_id,
                language=language,
                path=path,
            )
            if candidate is not None:
                candidates.append(candidate)

        if not candidates:
            raise LLMError("The model response contained no usable candidate code.")

        return candidates

    def explain(
        self,
        original_code: str,
        candidate: Candidate,
        language: str = "python",
    ) -> str:
        """Ask the model for a human-readable rationale (optional extra call)."""
        from modules.candidate_generation.prompts import PROMPT_EXPLANATION

        prompt = PROMPT_EXPLANATION.format(
            language=language,
            original_code=original_code,
            optimized_code=candidate.source_code,
            changes=json.dumps(candidate.changes_made, indent=2, default=str),
        )
        return self.client.generate_text(prompt, system_instruction=PROMPT_SYSTEM)

    # ------------------------------------------------------------
    # INTERNALS
    # ------------------------------------------------------------

    def _build_candidate(
        self,
        raw: dict[str, Any],
        index: int,
        source_code: str,
        parent_code_id: str,
        opportunity_id: str,
        language: str,
        path: str,
    ) -> Candidate | None:
        optimized_code = raw.get("optimized_code") or raw.get("code")
        if not isinstance(optimized_code, str) or not optimized_code.strip():
            return None

        impact = str(raw.get("estimated_impact", "unknown")).strip().lower()
        if impact not in IMPACT_WEIGHTS:
            impact = "unknown"

        confidence = _clamp_float(raw.get("confidence"), 0.0, 1.0)

        target_smells = raw.get("target_smells") or []
        if not isinstance(target_smells, list):
            target_smells = [str(target_smells)]

        changes = raw.get("changes_made") or []
        if not isinstance(changes, list):
            changes = []

        return Candidate(
            candidate_id=f"cand-{uuid.uuid4().hex[:10]}",
            source_code=optimized_code.strip(),
            parent_code_id=parent_code_id,
            opportunity_id=opportunity_id,
            strategy=str(raw.get("description") or raw.get("strategy") or "LLM optimization"),
            generation_method="llm",
            model=self.client.model,
            target_smells=[str(s) for s in target_smells],
            changes_made=[c for c in changes if isinstance(c, dict)],
            explanation=str(raw.get("explanation", "")),
            predicted_impact=impact,
            predicted_impact_score=IMPACT_WEIGHTS.get(impact, 0.0),
            confidence=confidence,
            # Predictions are not measurements: nothing is verified or measured yet.
            correctness_status="VERIFICATION_PENDING",
            benchmark_status="BENCHMARK_PENDING",
            final_status="PREDICTED",
        )


def _clamp_float(value: Any, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return low
    return max(low, min(high, number))


__all__ = [
    "Candidate",
    "CandidateGenerator",
    "LLMError",
    "LLMNotConfigured",
    "code_fingerprint",
    "format_detections",
]
