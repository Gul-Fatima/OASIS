from pathlib import Path
import json
import queue
import threading
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from modules.energy_estimation.project import Project
from modules.energy_estimation.executor import ProjectExecutor
from modules.energy_estimation.estimator import EnergyEstimator
from modules.code_understanding import folder as folder_analysis
from modules.code_understanding.parser import parse_code
from modules.code_understanding.language_config import get_language_config_manager
from modules.code_understanding.adapters import get_supported_languages, ADAPTERS
from modules.energy_detection.taxonomy import (
    ENERGY_SMELL_CATEGORIES,
    get_category,
    get_subcategory,
    format_categories_for_prompt,
    format_subcategories_for_prompt,
)
from modules.energy_detection.prompts import PROMPT_STEP_1, PROMPT_STEP_2, PROMPT_STEP_3
from modules.energy_detection.detector import detect_smells, summarise_detections
from modules.energy_detection.matcher import IMPLEMENTED_RULE_IDS, identify_issues
from modules.energy_detection.rulebase import load_kb
from modules.energy_detection.selftest import run_selftest
from modules.energy_detection.opportunities import analyze as analyze_opportunities

from backend.routes_candidates import router as candidates_router


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="OASIS Energy Estimation API",
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Candidate pipeline routes (generate → rank → verify → benchmark → decide).
app.include_router(candidates_router)


# ============================================================
# ACTIVE RUN REGISTRY
#
# Lets the Stop endpoint reach the measurement that is
# currently running (needed for infinite processes like a
# PHP website).
# ============================================================

_active_run = {
    "estimator": None,
    "executor": None,
}

_active_run_lock = threading.Lock()


def _set_active_run(estimator, executor):
    with _active_run_lock:
        _active_run["estimator"] = estimator
        _active_run["executor"] = executor


def _clear_active_run():
    with _active_run_lock:
        _active_run["estimator"] = None
        _active_run["executor"] = None


# ============================================================
# REQUEST MODEL
# ============================================================

class EnergyRequest(BaseModel):
    project_path: str
    command: str
    timeout: int = 300
    # For PHP servers / other infinite processes:
    # flush CodeCarbon metrics every N seconds while running.
    continuous: bool = False
    interval_seconds: int = Field(default=10, ge=1, le=300)


class CodeAnalysisRequest(BaseModel):

    file_path: str

    language: str = "auto"


class EnergyDetectRequest(BaseModel):

    file_path: str

    language: str = "auto"


class RuleTestRequest(BaseModel):
    """Pasted source for trying the structural matcher without writing a file."""

    source: str

    path: str = "<pasted source>"


class OptimizeRequest(BaseModel):
    """A file to analyse, either uploaded as text or read from disk."""

    source: str | None = None

    file_path: str | None = None

    filename: str = ""


class FolderAnalysisRequest(BaseModel):
    """Static analysis of a whole project folder (or a single file)."""

    project_path: str

    language: str = "auto"

    # Walk sub-directories (ignoring dependency/build folders).
    recursive: bool = True

    # Upper bound on files to parse, so a scan always finishes.
    max_files: int = Field(default=500, ge=1, le=5000)


class CandidateGenerateRequest(BaseModel):

    file_path: str

    language: str = "auto"

    detections: list[dict] = Field(default_factory=list)

    num_candidates: int = Field(default=1, ge=1, le=5)


# ============================================================
# FRONTEND STATIC FILES
# ============================================================

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

# The UI is a Next.js application. Anything it needs to serve itself lives in
# frontend/public, so that is the only directory the API should mount.
FRONTEND_PUBLIC_DIR = FRONTEND_DIR / "public"


def _frontend_hint() -> dict:
    """Where to find the UI once it is served by Next.js instead of FastAPI."""
    return {
        "application": "OASIS",
        "status": "running",
        "api_docs": "/docs",
        "health": "/api/health",
        "ui": (
            "Next.js app in OASIS/frontend — run `npm install && npm run dev` and "
            "open http://localhost:3000 (set NEXT_PUBLIC_API_BASE_URL to this server)."
        ),
    }


@app.get("/", response_class=HTMLResponse)
def root():
    """Serve the legacy dashboard if present, otherwise point at the UI."""
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return index.read_text(encoding="utf-8")
    return _frontend_hint()


@app.get("/analysis", response_class=HTMLResponse)
def analysis_page():
    page = FRONTEND_DIR / "analysis.html"
    if page.exists():
        return page.read_text(encoding="utf-8")
    return _frontend_hint()


if FRONTEND_PUBLIC_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(FRONTEND_PUBLIC_DIR)),
        name="static",
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/api/health")
def health():
    return {"status": "healthy"}


def _enrich_with_project(result: dict, project: Project) -> dict:
    result["project_path"] = str(project.project_path)
    result["file_count"] = project.get_file_count()
    return result


def _finite_estimate_events(estimator, executor, poll_seconds: float = 1.0):
    """Measure a finite process while emitting heartbeat snapshots.

    The measurement itself blocks until the process exits, so it runs in
    a worker thread and this generator yields a heartbeat every
    ``poll_seconds`` until the real result arrives. Without the
    heartbeats a long execution produces no output at all and the
    dashboard looks frozen.
    """

    results: "queue.Queue" = queue.Queue(maxsize=1)
    started = time.perf_counter()

    def run_measurement():
        try:
            results.put(("ok", estimator.estimate(executor)))
        except Exception as exc:  # reported to the client via the stream
            results.put(("error", exc))

    worker = threading.Thread(
        target=run_measurement,
        name="oasis-finite-estimator",
        daemon=True,
    )
    worker.start()

    heartbeat_index = 0
    while True:
        try:
            status, payload = results.get(timeout=poll_seconds)
        except queue.Empty:
            heartbeat_index += 1
            yield {
                "continuous": False,
                "final": False,
                "execution_status": "measuring",
                "snapshot_index": heartbeat_index,
                "execution_time_seconds": time.perf_counter() - started,
                "process_running": executor.is_running(),
                "stdout": "",
                "stderr": "",
            }
            continue

        if status == "error":
            raise payload

        yield payload
        return


# ============================================================
# ENERGY ESTIMATION (finite processes)
# ============================================================

@app.post("/api/energy/estimate")
def estimate_energy(request: EnergyRequest):
    try:
        print()
        print("=" * 70)
        print("                 OASIS API REQUEST")
        print("=" * 70)
        print(f"Project Path : {request.project_path}")
        print(f"Command      : {request.command}")
        print(f"Timeout      : {request.timeout}")
        print(f"Continuous   : {request.continuous}")

        if request.continuous:
            raise HTTPException(
                status_code=400,
                detail=(
                    "For continuous / infinite processes use "
                    "POST /api/energy/estimate/stream"
                ),
            )

        project = Project(request.project_path)

        executor = ProjectExecutor(
            command=request.command,
            working_directory=str(project.project_path),
            timeout=request.timeout,
        )

        estimator = EnergyEstimator(output_dir="results")
        result = estimator.estimate(executor)
        result = _enrich_with_project(result, project)

        print()
        print("Returning CodeCarbon measurement to frontend...")
        print("=" * 70)

        return result

    except HTTPException:
        raise

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        print()
        print("OASIS BACKEND ERROR:", str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# CONTINUOUS ENERGY ESTIMATION (infinite processes)
# Emits one SSE event every interval_seconds (default 10s)
# ============================================================

@app.post("/api/energy/estimate/stream")
def estimate_energy_stream(request: EnergyRequest):
    """
    Stream live CodeCarbon metrics while a project is measured.

    Works for both workloads:

    * ``continuous=true`` — long-running / infinite processes (PHP
      built-in server, Flask, ...): one snapshot every
      ``interval_seconds`` until the duration elapses or Stop is hit.
    * ``continuous=false`` — finite processes: the command runs in a
      worker thread while heartbeat events keep the connection (and
      the dashboard progress bar) alive, then the measured result is
      streamed as the final event.

    Each Server-Sent Event is a JSON metrics snapshot.
    The last event has ``final: true``.
    """

    try:
        print()
        print("=" * 70)
        print("           OASIS CONTINUOUS API REQUEST")
        print("=" * 70)
        print(f"Project Path : {request.project_path}")
        print(f"Command      : {request.command}")
        print(f"Duration     : {request.timeout}s")
        print(f"Continuous   : {request.continuous}")
        print(f"Interval     : {request.interval_seconds}s")

        project = Project(request.project_path)

        executor = ProjectExecutor(
            command=request.command,
            working_directory=str(project.project_path),
            timeout=request.timeout,
        )

        estimator = EnergyEstimator(output_dir="results")

        def event_generator():
            _set_active_run(estimator, executor)
            try:
                if request.continuous:
                    snapshots = estimator.estimate_continuous(
                        executor,
                        interval_seconds=request.interval_seconds,
                        duration_seconds=request.timeout,
                    )
                else:
                    snapshots = _finite_estimate_events(
                        estimator,
                        executor,
                        poll_seconds=1.0,
                    )

                for snapshot in snapshots:
                    snapshot = _enrich_with_project(
                        snapshot,
                        project,
                    )
                    payload = json.dumps(snapshot, default=str)
                    yield f"data: {payload}\n\n"

            except Exception as e:
                error_payload = json.dumps(
                    {
                        "error": str(e),
                        "final": True,
                        "execution_status": "failed",
                    }
                )
                yield f"data: {error_payload}\n\n"

            finally:
                _clear_active_run()

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        print()
        print("OASIS BACKEND ERROR:", str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# STOP A RUNNING CONTINUOUS MEASUREMENT
# ============================================================

@app.post("/api/energy/stop")
def stop_energy_measurement():
    """
    Stop the currently running continuous measurement.

    The measured process (e.g. a PHP website) and its whole
    process tree are terminated, CodeCarbon performs a final
    flush, and the stream emits its final snapshot.
    """

    with _active_run_lock:
        estimator = _active_run["estimator"]
        executor = _active_run["executor"]

    if estimator is None:
        raise HTTPException(
            status_code=409,
            detail="No energy measurement is currently running.",
        )

    print()
    print("=" * 70)
    print("           OASIS STOP REQUEST RECEIVED")
    print("=" * 70)

    # Signal the measurement loop to finish.
    estimator.request_stop()

    # Stop the measured process so a sleeping measurement loop can finish.
    if executor is not None and executor.is_running():
        try:
            executor.stop()
        except Exception as e:
            print("Executor stop warning:", e)

    return {
        "status": "stopping",
        "detail": (
            "Measurement is stopping. Final metrics follow "
            "on the measurement stream."
        ),
    }


# ============================================================
# SUPPORTED LANGUAGES
# ============================================================

@app.get("/api/languages")
def supported_languages():
    """Return list of supported languages and their configs."""
    mgr = get_language_config_manager()
    return {
        "supported": get_supported_languages(),
        "config Languages": mgr.get_supported_languages(),
        "extensions": mgr.get_supported_extensions(),
    }


# ============================================================
# ENERGY SMELL TAXONOMY
# ============================================================

@app.get("/api/taxonomy")
def get_taxonomy():
    """Return the full energy smell taxonomy."""
    categories = []
    for cat in ENERGY_SMELL_CATEGORIES:
        categories.append({
            "id": cat.id,
            "name": cat.name,
            "description": cat.description,
            "subcategories": [
                {"id": s.id, "name": s.name, "description": s.description}
                for s in cat.subcategories
            ],
        })
    return {
        "categories": categories,
        "total_categories": len(categories),
        "total_subcategories": sum(len(c["subcategories"]) for c in categories),
    }


# ============================================================
# ENERGY SMELL DETECTION
# ============================================================

@app.post("/api/detect")
def detect_energy_smells(request: EnergyDetectRequest):
    """
    Analyze code and detect potential energy smells using the
    12-category, 65-subcategory taxonomy.

    This is a static analysis — it identifies patterns that are
    commonly associated with energy waste. It does NOT measure
    actual energy consumption.
    """
    try:
        print()
        print("=" * 70)
        print("         ENERGY SMELL DETECTION REQUEST")
        print("=" * 70)
        print(f"File Path  : {request.file_path}")
        print(f"Language   : {request.language}")

        file_path = Path(request.file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {request.file_path}")

        source = file_path.read_text(encoding="utf-8")

        # Detect language
        language = request.language
        if language == "auto":
            mgr = get_language_config_manager()
            language = mgr.detect_language_from_filename(str(file_path))
            if language is None:
                language = mgr.detect_language_from_content(source)
            if language is None:
                language = "python"
            print(f"  Auto-detected language: {language}")

        # Parse code structure
        state = parse_code(source, path=str(file_path), language=language)

        # Detect energy smells based on code patterns
        detections = detect_smells(state, source, language)

        print(f"  Detected {len(detections)} potential energy smells")
        print("=" * 70)

        return {
            "file_path": str(file_path),
            "language": language,
            "line_count": len(source.splitlines()),
            "function_count": len(state.functions),
            "class_count": len(state.classes),
            "loop_count": len(state.loops),
            "detections": detections,
            "detection_count": len(detections),
            "detection_summary": summarise_detections(detections),
            "taxonomy_summary": {
                "categories_detected": list(set(d["category_id"] for d in detections)),
                "total_categories": len(ENERGY_SMELL_CATEGORIES),
            },
        }

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print()
        print("OASIS BACKEND ERROR:", str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# OPTIMIZE — developer-facing analysis + copyable prompt
# ============================================================

@app.post("/api/optimize")
def optimize_file(request: OptimizeRequest):
    """Analyse one file and return taxonomy-labelled issues plus a ready prompt."""
    try:
        if request.source is not None:
            source = request.source
            filename = request.filename or "pasted.py"
        elif request.file_path:
            path = Path(request.file_path)
            if not path.exists():
                raise FileNotFoundError(f"File not found: {request.file_path}")
            source = path.read_text(encoding="utf-8")
            filename = request.filename or path.name
        else:
            raise HTTPException(
                status_code=400,
                detail="Provide a file path or upload source code.",
            )

        if not source.strip():
            raise HTTPException(status_code=400, detail="The file is empty.")

        manager = get_language_config_manager()
        language = manager.detect_language_from_filename(filename)
        if language is None:
            language = manager.detect_language_from_content(source) or "python"

        result = analyze_opportunities(source, filename, language)
        result["file_path"] = request.file_path

        print()
        print("=" * 70)
        print("                 OASIS OPTIMIZE REQUEST")
        print("=" * 70)
        print(f"File     : {filename}")
        print(f"Language : {language}")
        print(f"Issues   : {result['issue_count']}")
        print("=" * 70)

        return result

    except HTTPException:
        raise
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        print("OASIS OPTIMIZE ERROR:", str(error))
        raise HTTPException(status_code=500, detail=str(error))


# ============================================================
# RULE BASE (okeb.json) + STRUCTURAL MATCHER
# ============================================================

@app.get("/api/rules")
def get_rules():
    """The knowledge base as the application sees it.

    Exposes every rule (aligned onto the taxonomy) and which of them have a
    runnable structural matcher, so the UI can show coverage instead of
    implying the whole rule base is enforced.
    """
    kb = load_kb()
    coverage = kb.coverage(IMPLEMENTED_RULE_IDS)
    supported = set(IMPLEMENTED_RULE_IDS)

    rules = []
    for rule in kb.rules:
        rules.append(
            {
                "rule_id": rule["canonical_id"],
                "source_id": rule.get("id"),
                "category_id": rule.get("category_id"),
                "category_name": rule.get("category_name"),
                "subcategory_id": rule.get("subcategory_id"),
                "subcategory_name": rule.get("subcategory_name"),
                "pattern": rule.get("pattern", ""),
                "strategy": rule.get("strategy", ""),
                "preconditions": rule.get("preconditions", ""),
                "detection_mode": (rule.get("derived") or {}).get(
                    "detection_mode", "static"
                ),
                "has_matcher": rule["canonical_id"] in supported,
                "duplicate_of": rule.get("duplicate_of"),
            }
        )

    return {
        "rule_count": coverage["rule_count"],
        "implemented_count": coverage["implemented_count"],
        "implemented_rule_ids": list(IMPLEMENTED_RULE_IDS),
        "per_category": coverage["per_category"],
        "subcategories_without_rules": coverage["subcategories_without_rules"],
        "subcategories_without_matcher": coverage["subcategories_without_matcher"],
        "categories": [
            {
                "id": category.id,
                "name": category.name,
                "subcategory_count": len(category.subcategories),
            }
            for category in ENERGY_SMELL_CATEGORIES
        ],
        "validation": [
            {"level": problem.level, "code": problem.code, "message": problem.message}
            for problem in kb.validate()
        ],
        "rules": rules,
    }


@app.get("/api/rules/selftest")
def rule_selftest():
    """Run the per-rule positive/negative examples against the matcher.

    This is the regression bench for the knowledge base: a failing case means a
    matcher fires on code it should leave alone (or misses code it should flag).
    """
    return run_selftest()


@app.post("/api/rules/test")
def test_rules(request: RuleTestRequest):
    """Match pasted Python source against the implemented structural rules."""
    if not request.source.strip():
        raise HTTPException(status_code=400, detail="Provide some Python source to test.")

    try:
        print()
        print("=" * 70)
        print("            RULE MATCHER TEST REQUEST")
        print("=" * 70)
        print(f"Path       : {request.path}")
        print(f"Characters : {len(request.source)}")

        result = identify_issues(request.source, request.path)
        matched = sorted({issue["rule_id"] for issue in result["issues"]})

        print(f"Issues     : {len(result['issues'])} ({len(matched)} rule ids)")
        print("=" * 70)

        return {
            **result,
            "supported_rule_ids": list(IMPLEMENTED_RULE_IDS),
            "matched_rule_ids": matched,
            "unmatched_rule_ids": [
                rule_id for rule_id in IMPLEMENTED_RULE_IDS if rule_id not in matched
            ],
        }

    except HTTPException:
        raise
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        print("OASIS RULE MATCHER ERROR:", str(error))
        raise HTTPException(status_code=500, detail=str(error))


# ============================================================
# CODE UNDERSTANDING
# ============================================================

@app.post("/api/code/analyze")
def analyze_code(
    request: CodeAnalysisRequest
):

    try:

        print()
        print("=" * 70)
        print("           CODE UNDERSTANDING REQUEST")
        print("=" * 70)

        print(
            f"File Path  : {request.file_path}"
        )

        print(
            f"Language   : {request.language}"
        )


        # ----------------------------------------------------
        # 1. READ FILE
        # ----------------------------------------------------

        file_path = Path(
            request.file_path
        )

        if not file_path.exists():
            raise FileNotFoundError(
                f"File not found: {request.file_path}"
            )

        source = file_path.read_text(
            encoding="utf-8"
        )


        # ----------------------------------------------------
        # 2. DETECT LANGUAGE (if auto)
        # ----------------------------------------------------

        language = request.language
        if language == "auto":
            mgr = get_language_config_manager()
            language = mgr.detect_language_from_filename(str(file_path))
            if language is None:
                language = mgr.detect_language_from_content(source)
            if language is None:
                language = "python"  # fallback
            print(f"  Auto-detected language: {language}")


        # ----------------------------------------------------
        # 3. PARSE CODE
        # ----------------------------------------------------

        state = parse_code(
            source,
            path=str(file_path),
            language=language
        )


        # ----------------------------------------------------
        # 3. RETURN STRUCTURED RESULT
        # ----------------------------------------------------

        result = state.to_dict()

        result["file_size"] = len(
            source.encode("utf-8")
        )

        result["line_count"] = len(
            source.splitlines()
        )

        print()
        print(
            f"Parsed: {len(state.functions)} functions, "
            f"{len(state.classes)} classes, "
            f"{len(state.loops)} loops"
        )

        print("=" * 70)


        return result


    except FileNotFoundError as e:

        raise HTTPException(

            status_code=404,

            detail=str(e)
        )

    except ValueError as e:

        raise HTTPException(

            status_code=400,

            detail=str(e)
        )

    except Exception as e:

        print()
        print(
            "OASIS BACKEND ERROR:",
            str(e)
        )

        raise HTTPException(

            status_code=500,

            detail=str(e)
        )


# ============================================================
# PROJECT (FOLDER) CODE UNDERSTANDING
#
# Parses every supported source file under a directory and
# aggregates the result. A single file path is accepted too.
# ============================================================

@app.post("/api/code/analyze/folder")
def analyze_folder_route(request: FolderAnalysisRequest):
    """Blocking folder analysis (no progress events)."""

    try:
        print()
        print("=" * 70)
        print("        PROJECT CODE UNDERSTANDING REQUEST")
        print("=" * 70)
        print(f"Project Path : {request.project_path}")
        print(f"Language     : {request.language}")
        print(f"Recursive    : {request.recursive}")

        target = Path(request.project_path)
        if not target.exists():
            raise FileNotFoundError(f"Path not found: {request.project_path}")

        result = None
        for event in folder_analysis.analyze_folder(
            target,
            language=request.language,
            max_files=request.max_files,
            recursive=request.recursive,
        ):
            if event.get("type") == "result":
                result = event["result"]

        if result is None:
            raise RuntimeError("Folder analysis produced no result.")

        print(
            f"Parsed {result['analyzed_files']} file(s) "
            f"({result['failed_files']} failed)"
        )
        print("=" * 70)

        return result

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        print()
        print("OASIS BACKEND ERROR:", str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# PROJECT CODE UNDERSTANDING (STREAMED)
#
# Same work as above, but emits one SSE event per file so the
# dashboard can show a live progress bar instead of appearing
# to hang on large projects.
# ============================================================

@app.post("/api/code/analyze/stream")
def analyze_code_stream(request: FolderAnalysisRequest):
    """Stream progress events while a project/file is parsed.

    Event shapes:

    * ``{"type": "progress", "stage", "percent", "current",
      "total", "file", "message"}``
    * ``{"type": "result", "result": {...aggregated CodeState...}}``
    * ``{"type": "error", "message": "..."}``
    """

    print()
    print("=" * 70)
    print("      PROJECT CODE UNDERSTANDING REQUEST (STREAM)")
    print("=" * 70)
    print(f"Project Path : {request.project_path}")
    print(f"Language     : {request.language}")

    target = Path(request.project_path)
    if not target.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Path not found: {request.project_path}",
        )

    def event_generator():
        try:
            for event in folder_analysis.analyze_folder(
                target,
                language=request.language,
                max_files=request.max_files,
                recursive=request.recursive,
            ):
                yield f"data: {json.dumps(event, default=str)}\n\n"

        except Exception as e:
            print()
            print("OASIS FOLDER ANALYSIS ERROR:", str(e))
            error_event = json.dumps(
                {"type": "error", "message": str(e), "done": True},
                default=str,
            )
            yield f"data: {error_event}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
