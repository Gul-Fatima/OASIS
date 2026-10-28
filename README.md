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
├── okeb.json                     the 160-rule optimization knowledge base
│
├── frontend/                     Next.js application
│   ├── app/
│   │   ├── layout.tsx            root <html>/<body> + metadata (dark theme)
│   │   ├── (public)/             no shell — the light pages
│   │   │   ├── page.tsx          landing page at "/", own inline header
│   │   │   └── home/             light project dashboard, no sidebar/footer
│   │   └── (app)/                shell group: every route below renders in AppShell
│   │       ├── layout.tsx        mounts <AppShell> (sidebar + mobile header)
│   │       ├── optimize/         optimize (issues + copyable prompt)
│   │       ├── analyze/          combined analysis
│   │       ├── energy/           energy measurement
│   │       ├── detect/           energy smell detection
│   │       ├── candidates/       optimization pipeline
│   │       ├── taxonomy/         taxonomy browser
│   │       ├── history/          decision history
│   │       └── settings/         configuration
│   ├── components/
│   │   ├── AppShell.tsx          sidebar NAV array, mobile header, health probe
│   │   ├── Disclosure.tsx        collapsible sections
│   │   ├── ui.tsx                shared primitives
│   │   └── analyze/ energy/ detect/ candidates/ optimize/   per-dashboard views
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
│   ├── energy_detection/         taxonomy, OKEB rule base + matcher, detector, opportunities, prompts
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

| Route | Purpose | Backend calls |
|---|---|---|
| `/` | Public landing page (route group `(public)`, no sidebar) | none |
| `/home` | Public light project dashboard (group `(public)`, no sidebar) | none (static) |
| `/optimize` | Optimize: choose a file, review issues + strategies, copy the LLM prompt | `POST /api/optimize` |
| `/analyze` | Parse a file or folder, then measure its energy in one run | `POST /api/code/analyze/stream`, `POST /api/energy/estimate/stream`, `POST /api/energy/stop` |
| `/energy` | CodeCarbon measurement, including continuous mode for servers | `POST /api/energy/estimate/stream`, `POST /api/energy/stop` |
| `/detect` | Static energy smell detection, grouped by taxonomy category | `POST /api/detect` |
| `/candidates` | Full pipeline: generate → rank → verify → benchmark → decide → accept/reject | `POST /api/pipeline/run/stream`, `POST /api/candidates/decision/record`, `GET /api/llm/status` |
| `/taxonomy` | The 12-category, 65-subcategory energy smell taxonomy | `GET /api/taxonomy` |
| `/history` | Recorded accept/reject decisions | `GET /api/candidates/history` |
| `/settings` | Backend, LLM and language configuration | `GET /api/llm/status`, `GET /api/llm/models`, `GET /api/languages` |

Every route under `(app)/` polls `GET /api/health` through `AppShell`, which is
where the "backend offline" banner comes from. The rule-base endpoints
(`/api/rules*`) are developer tooling and no page calls them yet.

The sidebar is the `NAV` array at the top of
`frontend/components/AppShell.tsx`; add or reorder entries there. Two groups of
routes exist, and they do not share a background:

- **`(app)/`** — dark shell (`bg-canvas` `#080c11` from `globals.css`).
  `/optimize`, `/analyze`, `/energy`, `/detect`, `/candidates`, `/taxonomy`,
  `/history`, `/settings` all render here.
- **`(public)/`** — bare layout, no sidebar, no footer. `/` (landing) and
  `/home` (light `#F7F7FC` dashboard) live here.

Because `/home` is in the public group, the sidebar's *Dashboard* link leaves the
shell — it is a full-page boundary, not an in-shell page. Any page added under
`(app)/` must use the shell's tokens (`bg-surface`, `text-ink`, `border-line`,
`text-muted`); hard-coded light colours there will only paint part of the page
and leave the dark canvas visible around it.

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
| `GET` | `/analysis` | Slot for the legacy `analysis.html`; serves the UI hint, since the Next.js app replaced that page |
| `GET` | `/api/health` | Health check |
| `POST` | `/api/optimize` | Analyse a file (`file_path` or uploaded `source`) and return issues + a copyable LLM prompt |
| `GET` | `/api/languages` | Supported languages and file extensions |
| `GET` | `/api/taxonomy` | Full energy smell taxonomy |
| `GET` | `/api/rules` | The 160-rule knowledge base, annotated with which rules have a runnable matcher |
| `GET` | `/api/rules/selftest` | Per-rule positive/negative matcher regression bench |
| `POST` | `/api/rules/test` | Match pasted Python source against the implemented structural rules |
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

### Request bodies

All bodies are JSON. Optional fields are shown with their default.

| Endpoint | Fields |
|---|---|
| `/api/optimize` | `source` (pasted text) **or** `file_path`; optional `filename` |
| `/api/detect` | `file_path`; `language` (`auto`) |
| `/api/code/analyze` | `file_path`; `language` (`auto`) |
| `/api/code/analyze/folder` · `/stream` | `project_path`; `language` (`auto`); `recursive` (`true`); `max_files` (`500`, max 5000) |
| `/api/energy/estimate` | `project_path`; `command`; `timeout` (`300`); `interval_seconds` (`10`). Rejects `continuous: true` with a 400 — use the stream endpoint |
| `/api/energy/estimate/stream` | The same, plus `continuous: true` for servers and other long-running processes |
| `/api/energy/stop` | No body; 409 when nothing is running |
| `/api/candidates/generate` | `file_path`; `language` (`auto`); optional `detections[]`; `num_candidates` (`1`, max 5); `run_detection` (`true`) |
| `/api/candidates/rank` | `candidates[]`; `original_code`; `detection_count`; optional `weights{}` |
| `/api/candidates/verify` | `candidate_code`; `file_path` **or** (`original_code` + `language`); optional `test_inputs[]` / `test_outputs[]`; `timeout` (`20.0`s) |
| `/api/candidates/benchmark` | `candidate_code`; `command`; `file_path`; optional `project_path`; `runs` (`2`, max 10); `warmup_runs` (`1`, max 5); `timeout` (`300`) |
| `/api/candidates/decision` | `candidate{}`; optional `verification{}` / `benchmark{}`; `min_improvement_percent` (`5.0`) |
| `/api/candidates/decision/record` | `candidate_id`; `status`; `developer_action`; optional `rationale[]`, `measured_improvement_percent` |
| `/api/pipeline/run/stream` | `file_path`; `language` (`auto`); `command`; optional `project_path`; `num_candidates` (`1`, max 5); `runs` (`1`, max 10); `warmup_runs` (`1`, max 5); `timeout` (`300`); `min_improvement_percent` (`5.0`); `skip_benchmark` (`false`) |
| `/api/rules/test` | `source`; optional `path` |

`GET /api/candidates/history` takes `limit` (default 50, max 500). Response
shapes are mirrored field for field in `frontend/lib/types.ts`, which is the
contract the UI compiles against.

Status codes: 400 bad input, 404 missing file or project, 409 candidate
generation is not configured, 502 the LLM provider failed.

### Streaming (SSE)

| Endpoint | Events |
|---|---|
| `/api/code/analyze/stream` | `{"type":"progress","stage","percent","current","total","file"}` · `{"type":"result","result":{…}}` · `{"type":"error","message"}` |
| `/api/energy/estimate/stream` | One CodeCarbon metrics snapshot per event, `{"final":true}` on the last; heartbeat snapshots with `execution_status:"measuring"` while a finite process runs; `{"error":…,"final":true}` on failure |
| `/api/pipeline/run/stream` | `{"type":"progress","stage","percent","message"}` · `{"type":"partial","stage","payload"}` per finished stage · `{"type":"result","result":{…}}` · `{"type":"error","message"}` |

These are POST endpoints, so `EventSource` cannot be used: `frontend/lib/api.ts#streamPost`
reads the body with a streaming reader and parses the `data:` frames itself.

---

## Prerequisites

- **Python 3.10+** (developed on Python 3.14)
- **Node.js 20.9+** and npm (developed on Node 24) — for the frontend only.
  Next.js 16 rejects Node 18 and older.

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

`./run.sh` starts the backend and, when `frontend/node_modules` exists, the
Next.js UI as well, then opens the UI (or the API docs when the UI is skipped).

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
| `GOOGLE_API_KEY` | — | Alternative name for the same key; either one enables generation |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Model used for generation |
| `GEMINI_API_BASE` | Google Generative Language API | Override for a proxy/gateway |
| `GEMINI_TIMEOUT_SECONDS` | `120` | Per-request timeout |
| `GEMINI_MAX_OUTPUT_TOKENS` | `8192` | Output cap (truncation is reported as an error) |
| `CODECARBON_API_KEY` | — | Optional Electricity Maps key so CodeCarbon resolves region-aware carbon intensity |
| `NEXT_PUBLIC_API_BASE_URL` | `http://127.0.0.1:8000` | Frontend → backend base URL (in `frontend/.env.local`) |

---

## How It Works

### 1. Code understanding
`modules/code_understanding` parses source with tree-sitter into a `CodeState`
(functions, classes, loops, conditionals, calls, I/O operations, dependencies,
complexity). This representation makes **no energy claims**.

A syntax error does not abort the analysis: the file is still walked on
tree-sitter's recovered tree and the first error is returned as
`state.syntax_error`, so the UI should show it as a warning next to a result
rather than treat the request as failed.

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

`POST /api/optimize` merges the two: structural matches first, then the pattern
detections not already reported at the same subcategory and line, sorted by
line. Every issue carries `origin: "structural" | "pattern"` so the UI can say
which detector produced it.

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


Verified (not just edited): rule base is 160 rules with 8 matcher-implemented, taxonomy is 12 categories / 65 subcategories,  okeb.json  validation is clean, and  python -m pytest modules/energy_detection -q  → 23 passed, so the README's "matcher is enforced by pytest" claim holds. CLI entry points named in the README all have  __main__  blocks. Every endpoint, request model and frontend call site was checked against the code; nothing failed or was left unverifiable. I did not change any application code.

One gap the README now exposes: it tells the UI to surface  syntax_error  as a warning, but  frontend/lib/types.ts  doesn't include that field yet, so the parse view can't display it.#   O A S I S  
 