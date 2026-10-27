"""LLM Prompts for Candidate Generation

Prompts that take energy smell detections and produce optimized code
candidates. Each candidate must preserve functional correctness.
"""

PROMPT_SYSTEM = (
    "You are an expert in energy-efficient software engineering. "
    "You produce ONLY valid code. No markdown fences, no explanations outside "
    "the requested JSON structure."
)


PROMPT_OPTIMIZATION = """\
You are an energy optimization expert. A code analysis has detected potential \
energy smells in the following code. Generate an optimized version that \
addresses the detected issues while preserving EXACT functional correctness.

Detected Energy Smells:
{detections}

Original Code ({language}):
```{language}
{original_code}
```

RULES:
- The optimized code MUST produce identical outputs for all valid inputs.
- Address each detected energy smell specifically.
- Do NOT change the function signatures or public API.
- Do NOT add new dependencies unless strictly necessary.
- Prefer standard library optimizations over external packages.
- Preserve all comments and docstrings.

Return ONLY this JSON:
{{
  "optimized_code": "the complete optimized source code",
  "changes_made": [
    {{
      "smell_id": "C#.S#",
      "description": "What was changed and why",
      "before": "relevant snippet from original",
      "after": "relevant snippet from optimized"
    }}
  ],
  "estimated_impact": "low|medium|high",
  "confidence": 0.0 to 1.0
}}
"""


PROMPT_EXPLANATION = """\
Explain WHY the following optimization saves energy, referencing the \
specific energy smell categories.

Original Code:
```{language}
{original_code}
```

Optimized Code:
```{language}
{optimized_code}
```

Changes Made:
{changes}

Provide a clear, technical explanation suitable for a software engineer.
Focus on:
1. Which energy smell categories are addressed
2. Why the original was inefficient
3. How the optimization reduces energy consumption
4. Any trade-offs (readability, memory, etc.)
"""


PROMPT_MULTI_CANDIDATE = """\
You are an energy optimization expert. Generate MULTIPLE alternative \
optimizations for the following code, each targeting different energy smells.

Detected Energy Smells:
{detections}

Original Code ({language}):
```{language}
{original_code}
```

Generate {num_candidates} distinct optimization candidates, each targeting \
a different combination of energy smells.

RULES:
- Each candidate MUST produce identical outputs for all valid inputs.
- Each candidate should target DIFFERENT energy smells.
- Do NOT change function signatures or public API.
- Rank candidates by expected energy improvement.

Return ONLY this JSON:
{{
  "candidates": [
    {{
      "candidate_id": 1,
      "optimized_code": "complete optimized source code",
      "target_smells": ["C#.S#", "C#.S#"],
      "description": "Brief description of the optimization strategy",
      "estimated_impact": "low|medium|high",
      "confidence": 0.0 to 1.0
    }}
  ]
}}
"""
