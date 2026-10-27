# OASIS — Optimizing Algorithms for Sustainable Intelligent Systems

> **An AI-assisted software energy optimization and empirical validation framework.**

OASIS is a research project (SE-499 Final Year Design) that analyzes source code,
identifies potential energy optimization opportunities, generates alternative
implementations, verifies functional correctness, measures actual energy
consumption under controlled execution, and presents evidence to the developer
for an accept/reject decision.

**Core principle: _Prediction is not measurement._**
The system never claims an optimization saves energy based solely on prediction.
Actual improvement must be empirically validated.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Core Pipeline](#core-pipeline)
- [Project Structure](#project-structure)
- [Modules](#modules)
- [Frontend (Next.js)](#frontend-nextjs)
- [Backend API](#backend-api)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Running the Application](#running-the-application)
- [Usage Examples](#usage-examples)
- [Configuration](#configuration)
- [How It Works](#how-it-works)
- [Research Integrity](#research-integrity)
- [Known Limitations](#known-limitations)

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                       │
│        Next.js app (frontend/) — App Router + Tailwind       │
│   dashboard · combined analysis · energy · detection ·       │
│   optimization pipeline · taxonomy · history · settings      │
└───────────────────────────┬──────────────────────────────────┘
                            │  HTTP / JSON + SSE
┌───────────────────────────▼──────────────────────────────────┐
│                     APPLICATION LAYER                        │
│                FastAPI backend (backend/)                    │
│   main.py              energy + code understanding routes     │
│   routes_candidates.py candidate pipeline + SSE orchestrator  │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│                       DOMAIN MODULES                         │
│  code_understanding → energy_detection → candidate_generation │
│  → candidate_ranking → verification → benchmarking →          │
│  optimization_decision                                        │
│  energy_estimation (CodeCarbon) · analysis (CFG/EFG)          │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│                         DATA LAYER                           │
│     CodeState JSON · emissions.csv · decisions.jsonl         │
└──────────────────────────────────────────────────────────────┘
```

---

## Core Pipeline

```
Source Code
    ↓
Code Parser (tree-sitter)
    ↓
Code Understanding (CodeState)
    ↓
Energy Smell Detection        ← hypothesis, never proof
    ↓
Baseline Measurement (CodeCarbon)
    ↓
Candidate Generation (LLM)
    ↓
Candidate Ranking             ← prioritisation, never validation
    ↓
Correctness Verification      ← gate 1
    ↓
Energy Benchmarking           ← gate 2, measured
    ↓
Optimization Decision         ← measured energy vs noise floor
    ↓
Human Accept / Reject
```

---

## Project Structure

```
OASIS/
├── README.md
├── claude.md
├── requirements.txt
├── .env.example
├── run.sh
│
├── frontend/                     Next.js application
│   ├── app/                      routes (App Router)
│   │   ├── page.tsx              dashboard
│   │   ├── analyze/              combined analysis
│   │   ├── energy/               energy measurement
│   │   ├── detect/               energy smell detection
│   │   ├── candidates/           optimization pipeline
│   │   ├── taxonomy/             taxonomy browser
│   │   ├── history/              decision history
│   │   └── settings/             configuration
│   ├── components/               AppShell, Disclosure, ui, per-page views
│   ├── lib/                      api client, types, formatting
│   └── README.md / claude.md
│
├── backend/
│   ├── main.py                   energy + code understanding routes
│   ├── routes_candidates.py      candidate pipeline routes + SSE orchestrator
│   └── claude.md
│
├── modules/
│   ├── config.py                 .env loading + env accessors
│   ├── main.py                   CLI entry point for energy estimation
│   │
│   ├── code_understanding/       parser, adapters, folder scan, CodeState model
│   ├── energy_estimation/        CodeCarbon estimator, executor, project
│   ├── energy_detection/         taxonomy, OKEB rule base, matcher, detector, prompts
│   ├── candidate_generation/     Gemini client, generator, prompts
│   ├── candidate_ranking/        ranking weights + scoring
│   ├── verification/             validator + orchestration service
│   ├── benchmarking/             comparator + original-vs-candidate service
│   ├── optimization_decision/    decision rules + decision history
│   └── analysis/                 CFG / EFG data structures (library only)
│
├── database/  experiments/  results/  docs/  third_party/
```

---

## Modules

| Module | Responsibility | Status |
|--------|---------------|--------|
| **Code Understanding** | Parse source code into a structured `CodeState` (tree-sitter, multi-language, folder scan) | ✅ Implemented |
| **Energy Detection** | Rule-based detection of energy smells mapped to the taxonomy | ✅ Implemented |
| **Energy Estimation** | Execute code and measure energy consumption via CodeCarbon | ✅ Implemented |
| **Candidate Generation** | LLM-assisted generation of alternative implementations (Google Gemini) | ✅ Implemented |
| **Candidate Ranking** | Prioritise candidates by predicted impact, confidence, coverage and rewrite risk | ✅ Implemented |
| **Verification** | Syntax + behaviour comparison of candidate against original | ✅ Implemented |
| **Benchmarking** | Warm-up then N measured runs of original vs candidate, with spread analysis | ✅ Implemented |
| **Optimization Decision** | Combine correctness + measured energy into an outcome and record the developer decision | ✅ Implemented |
| **Analysis (CFG/EFG)** | Control-flow and energy-flow graph structures | ⚠️ Library only — not wired into the pipeline |

---

## Frontend (Next.js)

The UI is a Next.js (App Router, TypeScript, Tailwind CSS v4) application in
`frontend/`. It replaces the earlier static HTML dashboards.

| Route | Purpose |
|---|---|
| `/` | **Optimize**: choose a file, review issues + strategies, copy the LLM prompt |
| `/analyze` | Parse a file or folder, then measure its energy in one run |
| `/energy` | CodeCarbon measurement, including continuous mode for servers |
| `/detect` | Static energy smell detection, grouped by taxonomy category |
| `/candidates` | Full pipeline: generate → rank → verify → benchmark → decide → accept/reject |
| `/taxonomy` | The 12-category, 65-subcategory energy smell taxonomy |
| `/history` | Recorded accept/reject decisions |
| `/settings` | Backend, LLM and language configuration |

The sidebar deliberately exposes only `/` (Optimize), `/history` and
`/settings`; the remaining routes are deeper tooling, reachable by URL rather
than part of the day-to-day flow.

**Layout rule:** every dashboard is summary-first — headline metric cards at the
top, detailed tables and raw payloads inside collapsed disclosures (native
`<details>`, nested where useful). The candidate cards deliberately render
*predicted* impact and *measured* improvement as separate, differently styled
figures.

---

## Backend API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | API status (or the legacy dashboard if present) |
| `GET` | `/api/health` | Health check |
| `POST` | `/api/optimize` | Analyse a file (`file_path` or uploaded `source`) and return issues + a copyable LLM prompt |
| `GET` | `/api/languages` | Supported languages and file extensions |
| `GET` | `/api/taxonomy` | Full energy smell taxonomy |
| `POST` | `/api/detect` | Detect energy smells in a single file |
| `POST` | `/api/code/analyze` | Parse a file into `CodeState` |
| `POST` | `/api/code/analyze/folder` | Parse every supported file under a folder (aggregated) |
| `POST` | `/api/code/analyze/stream` | Folder scan with SSE progress events |
| `POST` | `/api/energy/estimate` | Execute a project and measure energy |
| `POST` | `/api/energy/estimate/stream` | Stream live/heartbeat energy metrics (SSE) |
| `POST` | `/api/energy/stop` | Stop the running measurement (continuous mode) |
| `GET` | `/api/llm/status` | Whether candidate generation is configured (never the key) |
| `GET` | `/api/llm/models` | Models available to the configured key |
| `POST` | `/api/candidates/generate` | Detect (optional) + generate optimization candidates |
| `POST` | `/api/candidates/rank` | Re-rank candidates, optionally with custom weights |
| `POST` | `/api/candidates/verify` | Check that a candidate still behaves like the original |
| `POST` | `/api/candidates/benchmark` | Measure energy for original vs candidate |
| `POST` | `/api/candidates/decision` | Classify a candidate from its evidence |
| `POST` | `/api/candidates/decision/record` | Store a developer accept/reject action |
| `GET` | `/api/candidates/history` | Recent optimization decisions |
| `POST` | `/api/pipeline/run/stream` | Whole pipeline as SSE progress events |

---

## Prerequisites

- **Python 3.10+** (developed on Python 3.14)
- **Node.js 18+** and npm (developed on Node 24) — for the frontend only

---

## Installation

### Backend

```bash
cd OASIS
pip install -r requirements.txt

# Optional: extra language grammars for Java / C / C++ / JavaScript
pip install tree-sitter-java tree-sitter-c tree-sitter-cpp tree-sitter-javascript
```

### Frontend

```bash
cd OASIS/frontend
npm install
```

### Configuration

```bash
cd OASIS
cp .env.example .env      # then add your GEMINI_API_KEY
```

Without an API key everything still works except candidate generation: detection,
energy measurement and benchmarking all run normally.

---

## Running the Application

Two processes: the API and the UI. Start the backend from the **OASIS root**,
not from inside `backend/`.

```bash
# terminal 1 — from OASIS/
uvicorn backend.main:app --port 8000 --reload

# terminal 2 — from OASIS/frontend/
npm run dev
```

| Service | URL |
|---|---|
| UI | http://localhost:3000 |
| API | http://localhost:8000 |
| Interactive API docs | http://localhost:8000/docs |

`./run.sh` starts the backend and opens the API docs.

The UI is one workflow: **Optimize** (http://localhost:3000) — choose a Python
file, review the issues with their taxonomy label and knowledge-base strategy,
then copy the generated prompt into an LLM. The file is analysed, never run.

The matcher itself is still verifiable from the command line: every implemented
rule has one snippet it must flag and one it must leave alone
(`modules/energy_detection/selftest.py`), enforced by `pytest`.

### CLI tools

```bash
cd modules
python code_understanding/main.py    # parse a file
python main.py                       # measure energy

# from the OASIS root — match one file against the structural rules
python -m modules.energy_detection.matcher path/to/file.py
```

---

## Usage Examples

### Energy smell detection

```bash
curl -X POST http://localhost:8000/api/detect \
  -H "Content-Type: application/json" \
  -d '{"file_path": "D:/projects/my_project/main.py", "language": "auto"}'
```

### Optimize a file (issues + copyable prompt)

```bash
curl -X POST http://localhost:8000/api/optimize \
  -H "Content-Type: application/json" \
  -d '{"file_path": "D:/projects/my_project/main.py"}'
```

Returns `issues[]` (taxonomy label, location, strategy, example rewrite) and a
`prompt` string ready for an LLM. Pass `{"source": "...", "filename": "main.py"}`
instead of `file_path` to analyse text that is not on disk.

### Rule base (developer tooling)

```bash
curl http://localhost:8000/api/rules                    # rules + matcher coverage
curl http://localhost:8000/api/rules/selftest           # matcher self-test
```

### Full optimization pipeline (SSE)

```bash
curl -N -X POST http://localhost:8000/api/pipeline/run/stream \
  -H "Content-Type: application/json" \
  -d '{
        "file_path": "D:/projects/my_project/main.py",
        "command": "python main.py",
        "project_path": "D:/projects/my_project",
        "num_candidates": 2,
        "runs": 3,
        "warmup_runs": 1,
        "min_improvement_percent": 5
      }'
```

Events are streamed as `{"type": "progress" | "partial" | "result" | "error"}`.

### Generate candidates only

```bash
curl -X POST http://localhost:8000/api/candidates/generate \
  -H "Content-Type: application/json" \
  -d '{"file_path": "D:/projects/my_project/main.py", "num_candidates": 2}'
```

### Measure a project

```bash
curl -X POST http://localhost:8000/api/energy/estimate \
  -H "Content-Type: application/json" \
  -d '{"project_path": "D:/projects/my_project", "command": "python main.py", "timeout": 300}'
```

---

## Configuration

Environment variables are read from `OASIS/.env` (see `.env.example`).

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | — | Required for candidate generation |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Model used for generation |
| `GEMINI_API_BASE` | Google Generative Language API | Override for a proxy/gateway |
| `GEMINI_TIMEOUT_SECONDS` | `120` | Per-request timeout |
| `GEMINI_MAX_OUTPUT_TOKENS` | `8192` | Output cap (truncation is reported as an error) |
| `NEXT_PUBLIC_API_BASE_URL` | `http://127.0.0.1:8000` | Frontend → backend base URL (in `frontend/.env.local`) |

---

## How It Works

### 1. Code understanding
`modules/code_understanding` parses source with tree-sitter into a `CodeState`
(functions, classes, loops, conditionals, calls, I/O operations, dependencies,
complexity). This representation makes **no energy claims**.

### 2. Energy smell detection

There are two detectors, sharing one taxonomy:

* `modules/energy_detection/detector.py` runs small, individually testable rules
  over the `CodeState` and labels each match with a taxonomy subcategory. Each
  detection records `evidence: "static pattern match"`. This is what
  `/api/detect` uses today.
* `modules/energy_detection/matcher.py` matches tree-sitter node shapes, binds
  the names the strategy needs, checks the rule's preconditions and attaches the
  strategy text from `okeb.json` (`rulebase.py` indexes it). It is Python-only
  and covers 8 of the 160 knowledge-base rules so far; it is not yet wired into
  `/api/detect`.

`okeb.json` is aligned one-way onto `modules/energy_detection/taxonomy.py`, which
mirrors `third_party/energy-smells/taxonomy.md` (12 categories, 65
subcategories). Every rule stores its `category_name`/`subcategory_name`, so
labels never have to be re-derived. To verify or re-apply the alignment after
editing the rule base:

```bash
python -m modules.energy_detection.okeb_align --check   # exit 1 on drift
python -m modules.energy_detection.okeb_align --write   # rewrite okeb.json
```

### 3. Candidate generation
`modules/candidate_generation` renders the detections into a prompt and asks
Gemini for an optimized version that preserves functional correctness. The
model's `estimated_impact` is stored as `predicted_impact` — a prediction, with
`measurement_available: false`.

### 4. Ranking
`modules/candidate_ranking` scores candidates from predicted impact, model
confidence, how much of the detected smell set they address, and a rewrite-risk
proxy. Ranking is prioritisation, not validation.

### 5. Verification (gate 1)
`modules/verification` compiles the candidate, then executes the original and the
candidate in isolated subprocesses with the same input and compares stdout and
exit status. When the comparison produces no usable signal the result is
**inconclusive**, never "verified".

### 6. Benchmarking (gate 2)
`modules/benchmarking` copies the project into a temporary workspace, writes the
candidate over the target file there, and runs warm-up plus N measured
executions of both versions, reporting mean/min/max energy and the spread
between runs.

### 7. Decision
`modules/optimization_decision` applies correctness first. Only a verified
candidate with a measured improvement larger than the threshold (which rises
with the observed measurement spread) is `IMPROVED`. Differences inside the
noise floor are `NEUTRAL`; worse measurements are `REGRESSED`. The developer's
accept/reject action is appended to `results/decisions.jsonl`.

---

## Research Integrity

- Predicted and measured values are stored in separate fields and displayed with
  different labels and styling. Nothing converts a prediction into a measurement.
- Every measurement records energy, duration, CO₂, hardware and tracker metadata
  so the experiment can be reproduced.
- Neutral, regressed and failed candidates are kept and displayed alongside
  successful ones. The decision history is not filtered to wins.
- Detection results are hypotheses from static pattern matching; they are never
  presented as proof of energy inefficiency.

---

## Known Limitations

- **Verification is not a container sandbox.** Candidates run in a subprocess with
  a timeout and UTF-8 pinning, but without OS-level isolation. Only analyse code
  you are willing to execute on this machine.
- **Behaviour comparison is limited** to programs that run standalone and produce
  deterministic stdout. Files needing arguments, stdin or external services yield
  an inconclusive result unless test cases are supplied.
- **Benchmarks are single-machine.** Small differences between runs are
  environmental noise; the decision threshold accounts for this rather than
  reporting a saving that is not real.
- **`modules/analysis` (CFG/EFG) is a library** and is not yet connected to the
  pipeline.
