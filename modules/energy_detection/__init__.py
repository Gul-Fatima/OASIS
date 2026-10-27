"""Energy Detection Module

Detects potential energy optimization opportunities in source code using the
Energy Smells taxonomy (12 categories, 65 subcategories).

Based on: SMART-Dal/Energy-Smells taxonomy and classification pipeline.

Detection is a hypothesis, never proof of energy inefficiency.
"""

from .detector import (
    RULES,
    detect_smells,
    detect_smells_from_code_state,
    summarise_detections,
)
from .prompts import PROMPT_STEP_1, PROMPT_STEP_2, PROMPT_STEP_3
from .taxonomy import (
    ENERGY_SMELL_CATEGORIES,
    get_category,
    get_subcategories,
    get_subcategory,
)

__all__ = [
    "ENERGY_SMELL_CATEGORIES",
    "PROMPT_STEP_1",
    "PROMPT_STEP_2",
    "PROMPT_STEP_3",
    "RULES",
    "detect_smells",
    "detect_smells_from_code_state",
    "get_category",
    "get_subcategories",
    "get_subcategory",
    "summarise_detections",
]
