"""Verification Module

Validates functional correctness of code candidates by executing them
against test inputs and comparing outputs.

Based on: SMART-Dal/Energy-Smells validate_correctness.py

``service.py`` adds the orchestration layer used by the backend: syntax
checking, behaviour comparison and the mapped verification statuses.
"""

from .service import Check, VerificationResult, VerificationService
from .validator import ValidationResult, validate_code, validate_pair, warmup_cpu

__all__ = [
    "Check",
    "ValidationResult",
    "VerificationResult",
    "VerificationService",
    "validate_code",
    "validate_pair",
    "warmup_cpu",
]
