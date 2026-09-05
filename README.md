# OASIS — Optimizing Algorithms for Sustainable Intelligent Systems

> **An AI-assisted software energy optimization and empirical validation framework.**

OASIS is a research project (SE-499 Final Year Design) that analyzes source code, identifies potential energy optimization opportunities, generates alternative implementations, verifies functional correctness, measures actual energy consumption under controlled execution, and presents evidence to the developer for an accept/reject decision.

**Core principle: _Prediction is not measurement._** The system never claims an optimization saves energy based solely on prediction. Actual improvement must be empirically validated.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Project Structure](#project-structure)
- [Modules](#modules)
- [Frontend Dashboards](#frontend-dashboards)
- [Backend API](#backend-api)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Running the Application](#running-the-application)
- [Usage Examples](#usage-examples)
- [API Reference](#api-reference)
- [How It Works](#how-it-works)
- [Research Integrity](#research-integrity)

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                   PRESENTATION LAYER                     │
│  index.html  ·  analysis.html  ·  style.css  ·  app.js  │
└────────────────────────┬─────────────────────────────────┘
                         │  HTTP / JSON
┌────────────────────────▼─────────────────────────────────┐
│                    APPLICATION LAYER                     │
│           FastAPI backend (backend/main.py)              │
│  ┌─────────────────────┐  ┌────────────────────────────┐ │
│  │  Code Understanding │  │   Energy Estimation        │ │
│  │  tree-sitter parser │  │   CodeCarbon tracker       │ │
│  │  AST walker         │  │   subprocess executor      │ │
│  │  feature extraction │  │   emissions measurement    │ │
│  └─────────────────────┘  └────────────────────────────┘ │
└────────────────────────┬─────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│                      DATA LAYER                          │
│        CodeState JSON · Emissions CSV · Results/         │
└──────────────────────────────────────────────────────────┘
```

### Core Pipeline

```
Source Code
    ↓
Code Parser (tree-sitter)
    ↓
Code Understanding (CodeState)
    ↓
Optimization Opportunity Detection
    ↓
Baseline Measurement (CodeCarbon)
    ↓
Candidate Generation
    ↓
Correctness Verification
    ↓
Energy Measurement
    ↓
Original vs Candidate Comparison
    ↓
Human Accept/Reject Decision
```

---

## Project Structure

```
OASIS/
│
├── README.md
├── CLAUDE.md
│
├── frontend/
│   ├── index.html          # Energy estimation dashboard
│   ├── analysis.html       # Combined analysis dashboard
│   ├── style.css           # Shared styles
│   ├── app.js              # Energy estimation logic
│   └── app_analysis.js     # Combined analysis logic
│
├── backend/
│   ├── main.py             # FastAPI server (API endpoints)
│   └── claude.md
│
├── modules/
│   ├── main.py             # CLI entry point for energy estimation
│   │
│   ├── code_understanding/
│   │   ├── __init__.py
│   │   ├── model.py        # CodeState data model
│   │   ├── parser.py       # tree-sitter based parser
│   │   ├── adapters.py     # Per-language adapters
│   │   ├── main.py         # CLI entry point
│   │   └── claude.md
│   │
│   ├── energy_estimation/
│   │   ├── __init__.py
│   │   ├── estimator.py    # CodeCarbon energy tracker
│   │   ├── executor.py     # Subprocess project executor
│   │   ├── project.py      # Project file loader
│   │   ├── report.py       # Console report display
│   │   └── claude.md
│   │
│   ├── energy_detection/
│   ├── candidate_generation/
│   ├── candidate_ranking/
│   ├── verification/
│   ├── benchmarking/
│   └── optimization_decision/
│
├── database/
├── experiments/
├── results/
├── docs/
└── tests/
```

---

## Modules

| Module | Responsibility | Status |
|--------|---------------|--------|
| **Code Understanding** | Parse source code into structured `CodeState` representation | ✅ Being Implemented |
| **Energy Estimation** | Execute code and measure energy consumption via CodeCarbon | ✅ Being Implemented |
| **Energy Detection** | Identify potential energy optimization patterns | 🔲 Planned |
| **Candidate Generation** | Generate alternative implementations | 🔲 Planned |
| **Candidate Ranking** | Prioritize candidates by energy potential and risk | 🔲 Planned |
| **Verification** | Check functional correctness of candidates | 🔲 Planned |
| **Benchmarking** | Execute and compare original vs optimized versions | 🔲 Planned |
| **Optimization Decision** | Combine results for human review | 🔲 Planned |

---

## Frontend Dashboards

### Energy Estimation Dashboard (`index.html`)
- File input with execution command and timeout
- Real-time CodeCarbon energy measurement
- Energy breakdown (CPU / RAM / GPU)
- Resource utilization metrics
- System environment and metadata

### Combined Analysis Dashboard (`analysis.html`)
- Analyzes **code structure** and **energy consumption** in one workflow
- **Step 1:** Parse file → functions, classes, loops, complexity, dependencies, IO ops
- **Step 2:** Execute file → energy, CO₂, duration, resource utilization
- Results displayed section-by-section on a single page

---

## Backend API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Application status |
| `GET` | `/api/health` | Health check |
| `POST` | `/api/code/analyze` | Parse a Python file into CodeState |
| `POST` | `/api/energy/estimate` | Execute project and measure energy |

---

## Prerequisites

- **Python 3.10+** (developed on Python 3.14)
- **pip**

### Python Dependencies

```
fastapi
uvicorn[standard]
pydantic
tree-sitter
tree-sitter-python
codecarbon
pandas
radon              (optional — for cyclomatic complexity)
```

---

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd OASIS

# Install Python dependencies
pip install fastapi uvicorn pydantic tree-sitter tree-sitter-python codecarbon pandas

# Optional: cyclomatic complexity metrics
pip install radon
```

---

## Running the Application

### Backend API Server

**Important:** Always run from the **project root directory**, not from inside `backend/`.

```bash
# From the OASIS root directory:
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`.

Interactive docs: `http://localhost:8000/docs`

### Energy Estimation Dashboard

1. Start the backend server
2. Open `frontend/index.html` in your browser
3. Enter a project path and execution command
4. Click **Run Energy Analysis**

### Combined Analysis Dashboard

1. Start the backend server
2. Open `frontend/analysis.html` in your browser
3. Enter a Python file path and execution command
4. Click **Run Combined Analysis**

### CLI Tools

**Code Understanding:**

```bash
cd modules
python code_understanding/main.py
# Enter path to a Python file when prompted
```

**Energy Estimation:**

```bash
cd modules
python main.py
# Enter project path and execution command when prompted
```

---

## Usage Examples

### Code Understanding via API

```bash
curl -X POST http://localhost:8000/api/code/analyze \
  -H "Content-Type: application/json" \
  -d '{"file_path": "D:\projects\my_script.py", "language": "python"}'
```

Response:

```json
{
  "language": "python",
  "path": "D:\projects\my_script.py",
  "functions": [
    {
      "name": "hello",
      "start_line": 1,
      "end_line": 3,
      "arguments": ["name"],
      "decorators": [],
      "complexity": 1
    }
  ],
  "classes": [],
  "loops": [],
  "conditionals": 0,
  "function_calls": [...],
  "io_operations": ["print (line 2)"],
  "complexity": {"measured": 1, "max": 1, "total": 1},
  "file_size": 1024,
  "line_count": 10
}
```

### Energy Estimation via API

```bash
curl -X POST http://localhost:8000/api/energy/estimate \
  -H "Content-Type: a
