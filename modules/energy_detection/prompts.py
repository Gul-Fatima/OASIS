"""LLM Prompts for Energy Smell Classification

Three-step classification pipeline:
  Step 1: Root cause analysis (what changed and why it's inefficient)
  Step 2: Category triage (map to one or more of 12 parent categories)
  Step 3: Subcategory classification (precise root-cause labels)

Source: SMART-Dal/Energy-Smells (CC-BY-4.0)
"""

PROMPT_SYSTEM = "Return ONLY valid JSON. No markdown. No extra text."


PROMPT_STEP_1 = """\
You are an expert in Python energy inefficiency analysis. Energy inefficiency \
can be correlated to performance inefficiency (time and memory) sometimes.

Goal:
Extract the TRUE root cause(s) of inefficiency (energy/performance) between \
two functionally equivalent solutions. You will be given the energy \
consumption, execution time, and memory usage of both codes. Based on the \
energy consumption variance and auxiliary metrics, identify the root cause(s) \
of energy inefficiency.
BOTH codes produce the same outputs for all valid inputs.

IMPORTANT RULES:
- Use the problem description to infer constraints and intended behavior.
- Identify what *changed* and which change(s) plausibly explain the measured \
metric lifts.
- Analyze the code changes carefully and think deeply about root causes.
- Output MUST be a single valid JSON object (no markdown, no extra text).

Now analyze THIS pair:

Problem Description (may be truncated):
{problem_description}

Code A (Inefficient):
- energy_joules: {energy_ineff}
- time_seconds: {time_ineff}
- memory_kb: {mem_ineff}
```python
{code_ineff}
```

Code B (Efficient):
- energy_joules: {energy_eff}
- time_seconds: {time_eff}
- memory_kb: {mem_eff}
```python
{code_eff}
```

Return ONLY this JSON schema:
{{
  "inefficiency_summary": "3-5 sentences. Describe the root cause clearly."
}}
"""


PROMPT_STEP_2 = """\
You are Step 2 (Triage): choose the best matching PARENT energy-smell categories.

Context:
- You already saw the problem description and both code versions above.
- Step 1 output (root cause analysis):
{step1_output}

RULES:
- Focus on the ROOT CAUSE(S), not downstream effects.
- You may select MULTIPLE categories.
- You MUST return at least 1 category.
- Output MUST be strict JSON only.

Parent Categories (C1-C12):
{categories_list}

Return ONLY this JSON:
{{
  "candidate_categories": ["C#"...],
  "category_rationales": {{
    "C#": "2-4 sentences explaining why this category matches."
  }}
}}
Constraints:
- candidate_categories must be unique.
"""


PROMPT_MANUAL_OPTIMIZATION = """\
You are an energy optimization expert working on a {language} file.

The static analysis below found the issues listed. Each entry names the energy
smell taxonomy subcategory, the concrete code location, and the optimization
strategy from the knowledge base.

Detected issues:
{issues}

File: {filename}
```{language}
{code}
```

Apply the listed strategies where they are safe for this code. Requirements:
- Preserve exact behaviour for all valid inputs.
- Do not change public function or class signatures.
- Keep comments, docstrings and formatting style.
- Do not add dependencies.
- If a strategy does not apply, leave that code unchanged.

Return the complete optimized file in one code block. After it, list the changes
you made, one line per issue number.
"""


PROMPT_STEP_3 = """\
You are Step 3 (Specialist): select final subcategory labels.

Context:
- You already saw the problem and both code versions above.
- Step 1 and Step 2 outputs are in the conversation history.

RULES (follow strictly):
- Each sample MUST have at least ONE (category_id, subcategory_id) pair.
- Focus on Root Causes: Do NOT label downstream effects.
- For EACH candidate subcategory, compare its definition with the code changes.
- Strict Parent Discarding: If NONE of a parent's subcategories fit, DISCARD it.
- Strict Independence: Multiple subcategories allowed ONLY if truly independent.

Candidate parents from Step 2:
{selected_parents}

Available Subcategories (ONLY for candidate parents):
{subcategories_list}

Return ONLY this JSON:
{{
  "final_classification": [
    {{
      "category_id": "C#",
      "subcategory_id": "C#.S#",
      "justification": "2-4 sentences explaining the match."
    }}
  ]
}}
Constraints:
- final_classification must have length >= 1.
"""
