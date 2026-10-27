"""Candidate Generation Module

Generates alternative energy-efficient implementations using LLM-assisted
optimization. Takes energy smell detections and produces candidate fixes.

Pipeline: Detection → Prompts → LLM → Candidates → Verification

The LLM never decides whether an optimization succeeded — see
``modules/optimization_decision`` for that.
"""

from .generator import (
    Candidate,
    CandidateGenerator,
    code_fingerprint,
    format_detections,
)
from .llm_client import GeminiClient, LLMError, LLMNotConfigured
from .prompts import (
    PROMPT_EXPLANATION,
    PROMPT_MULTI_CANDIDATE,
    PROMPT_OPTIMIZATION,
    PROMPT_SYSTEM,
)

__all__ = [
    "Candidate",
    "CandidateGenerator",
    "GeminiClient",
    "LLMError",
    "LLMNotConfigured",
    "PROMPT_EXPLANATION",
    "PROMPT_MULTI_CANDIDATE",
    "PROMPT_OPTIMIZATION",
    "PROMPT_SYSTEM",
    "code_fingerprint",
    "format_detections",
]
