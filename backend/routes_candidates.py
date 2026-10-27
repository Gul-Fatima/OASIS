"""Candidate pipeline API: generate → rank → verify → benchmark → decide.

Kept out of ``main.py`` on purpose (backend/CLAUDE.md: do not put the pipeline
inside one API route). Each endpoint is a thin wrapper around a domain module;
the orchestration that the dashboard needs lives in ``/api/pipeline/run/stream``.

Status codes:

* 400 — bad input (missing detections, no execution command, bad language)
* 404 — file or project path does not exist
* 409 — the LLM is not configured, so generation cannot run
* 502 — the LLM provider failed
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from modules.candidate_generation import (
    CandidateGenerator,
    GeminiClient,
    LLMError,
    LLMNotConfigured,
)
from modules.candidate_ranking import RankWeights, rank_candidates
from modules.code_understanding.language_config import get_language_config_manager
from modules.code_understanding.parser import parse_code
from modules.energy_detection.detector import detect_smells, summarise_detections
from modules.optimization_decision import decide as decide_optimization
from modules.optimization_decision import (
    load_decision_history,
    record_decision,
)
from modules.verification import VerificationService

router = APIRouter(prefix="/api", tags=["candidates"])


# ============================================================
# REQUEST MODELS
# ============================================================

class GenerateRequest(BaseModel):
    file_path: str
    language: str = "auto"
    # Optional pre-computed detections; when omitted the detector runs.
    detections: list[dict] = Field(default_factory=list)
    num_candidates: int = Field(default=1, ge=1, le=5)
    run_detection: bool = True


class RankRequest(BaseModel):
    candidates: list[dict]
    original_code: str = ""
    detection_count: int = 0
    weights: dict[str, float] | None = None


class VerifyRequest(BaseModel):
    candidate_code: str
    file_path: str | None = None
    original_code: str | None = None
    language: str = "auto"
    # Optional dataset for stronger evidence.
    test_inputs: list[str] = Field(default_factory=list)
    test_outputs: list[str] = Field(default_factory=list)
    timeout: float = Field(default=20.0, gt=0, le=600)


class BenchmarkRequest(BaseModel):
    candidate_code: str
    command: str
    file_path: str
    project_path: str | None = None
    language: str = "auto"
    runs: int = Field(default=2, ge=1, le=10)
    warmup_runs: int = Field(default=1, ge=0, le=5)
    timeout: int = Field(default=300, ge=1, le=3600)


class DecisionRequest(BaseModel):
    candidate: dict = Field(default_factory=dict)
    verification: dict | None = None
    benchmark: dict | None = None
    min_improvement_percent: float = Field(default=5.0, ge=0, le=100)


class DecisionRecordRequest(BaseModel):
    candidate_id: str
    status: str
    developer_action: str
    rationale: list[str] = Field(default_factory=list)
    measured_improvement_percent: float | None = None


class PipelineRequest(BaseModel):
    file_path: str
    language: str = "auto"
    command: str = ""
    project_path: str | None = None
    num_candidates: int = Field(default=1, ge=1, le=5)
    runs: int = Field(default=1, ge=1, le=10)
    warmup_runs: int = Field(default=1, ge=0, le=5)
    timeout: int = Field(default=300, ge=1, le=3600)
    min_improvement_percent: float = Field(default=5.0, ge=0, le=100)
    skip_benchmark: bool = False


# ============================================================
# SHARED HELPERS
# ============================================================

def _resolve_language(path: Path, source: str, requested: str) -> str:
    if requested and requested != "auto":
        return requested

    manager = get_language_config_manager()
    return (
        manager.detect_language_from_filename(str(path))
        or manager.detect_language_from_content(source)
        or "python"
    )


def _read_target(file_path: str, language: str) -> tuple[Path, str, str, Any, list[dict]]:
    """Read a file, resolve its language, parse it and detect smells."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    source = path.read_text(encoding="utf-8")
    resolved_language = _resolve_language(path, source, language)
    state = parse_code(source, path=str(path), language=resolved_language)
    detections = detect_smells(state, source, resolved_language)

    return path, source, resolved_language, state, detections


def _llm_error_to_http(error: LLMError) -> HTTPException:
    if isinstance(error, LLMNotConfigured):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=502, detail=f"LLM generation failed: {error}")


def _candidate_dicts(candidates: list[Any]) -> list[dict]:
    return [
        candidate.to_dict() if hasattr(candidate, "to_dict") else dict(candidate)
        for candidate in candidates
    ]


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


# ============================================================
# LLM STATUS
# ============================================================

@router.get("/llm/status")
def llm_status() -> dict:
    """Report whether candidate generation is configured (never the key)."""
    return GeminiClient().status()


@router.get("/llm/models")
def llm_models() -> dict:
    """List models available to the configured key (diagnostics)."""
    client = GeminiClient()
    if not client.is_configured:
        raise HTTPException(
            status_code=409,
            detail="No Gemini API key configured. Set GEMINI_API_KEY in OASIS/.env.",
        )

    try:
        return {"models": client.list_models(), "configured_model": client.model}
    except LLMError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


# ============================================================
# 1. DETECT + GENERATE
# ============================================================

@router.post("/candidates/generate")
def generate_candidates(request: GenerateRequest) -> dict:
    """Detect energy smells (optional) and generate optimization candidates."""
    try:
        path, source, language, state, detections = _read_target(
            request.file_path, request.language
        )
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except UnicodeDecodeError as error:
        raise HTTPException(
            status_code=400, detail=f"Could not decode {request.file_path} as UTF-8: {error}"
        ) from error

    # Pre-supplied detections take precedence, so the UI can re-generate from
    # a user-edited selection without re-running the detector.
    if request.detections:
        detections = request.detections

    if not detections:
        raise HTTPException(
            status_code=400,
            detail=(
                "No energy smells were detected, so there is nothing to optimise. "
                "Detection is a hypothesis — no candidate is generated without one."
            ),
        )

    generator = CandidateGenerator()
    if not generator.is_available:
        raise _llm_error_to_http(LLMNotConfigured(generator.client.status()["hint"] or ""))

    try:
        candidates = generator.generate(
            source_code=source,
            detections=detections,
            language=language,
            num_candidates=request.num_candidates,
            path=str(path),
        )
    except LLMError as error:
        raise _llm_error_to_http(error) from error

    ranked = rank_candidates(
        _candidate_dicts(candidates),
        original_code=source,
        detection_count=len(detections),
    )

    return {
        "file_path": str(path),
        "language": language,
        "model": generator.client.model,
        "detections": detections,
        "detection_summary": summarise_detections(detections),
        "candidates": ranked,
        "candidate_count": len(ranked),
        "note": "Predicted impact only — verify and benchmark before trusting any saving.",
    }


@router.post("/candidates/rank")
def rank(request: RankRequest) -> dict:
    """Re-rank a set of candidates with optional custom weights."""
    try:
        weights = RankWeights(**request.weights) if request.weights else None
    except TypeError as error:
        raise HTTPException(status_code=400, detail=f"Invalid weights: {error}") from error

    ranked = rank_candidates(
        [dict(candidate) for candidate in request.candidates],
        original_code=request.original_code,
        detection_count=request.detection_count,
        weights=weights,
    )
    return {"candidates": ranked, "count": len(ranked)}


# ============================================================
# 2. VERIFY
# ============================================================

@router.post("/candidates/verify")
def verify_candidate(request: VerifyRequest) -> dict:
    """Check that a candidate still behaves like the original."""
    original_code = request.original_code
    language = request.language

    if original_code is None:
        if not request.file_path:
            raise HTTPException(
                status_code=400,
                detail="Provide either file_path or original_code to verify against.",
            )
        path = Path(request.file_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {request.file_path}")
        original_code = path.read_text(encoding="utf-8")
        language = _resolve_language(path, original_code, request.language)

    if request.language == "auto" and not request.file_path and request.original_code:
        raise HTTPException(
            status_code=400,
            detail="Specify the language when verifying raw original_code.",
        )

    service = VerificationService(timeout=request.timeout)
    result = service.verify(
        original_code=original_code,
        candidate_code=request.candidate_code,
        language=language,
        test_inputs=request.test_inputs,
        test_outputs=request.test_outputs,
    )
    return result.to_dict()


# ============================================================
# 3. BENCHMARK
# ============================================================

@router.post("/candidates/benchmark")
def benchmark_candidate(request: BenchmarkRequest) -> dict:
    """Measure energy for the original and the candidate under one command."""
    # Imported here so the heavy CodeCarbon/pandas chain is not loaded for the
    # generation-only endpoints.
    from modules.benchmarking import BenchmarkService

    candidate_file = Path(request.file_path)
    if not candidate_file.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.file_path}")

    project_path = request.project_path or str(candidate_file.parent)
    if not Path(project_path).exists():
        raise HTTPException(status_code=404, detail=f"Project not found: {project_path}")

    if not request.command.strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "An execution command is required. Static analysis cannot produce "
                "measured energy values (CLAUDE.md: prediction is not measurement)."
            ),
        )

    service = BenchmarkService()
    try:
        result = service.benchmark(
            project_path=project_path,
            target_file=str(candidate_file),
            candidate_code=request.candidate_code,
            command=request.command,
            runs=request.runs,
            warmup_runs=request.warmup_runs,
            timeout=request.timeout,
            language=request.language,
        )
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return result.to_dict()


# ============================================================
# 4. DECIDE
# ============================================================

@router.post("/candidates/decision")
def decide(request: DecisionRequest) -> dict:
    """Classify a candidate from its correctness and measurement evidence."""
    result = decide_optimization(
        candidate=request.candidate,
        verification=request.verification,
        benchmark=request.benchmark,
        min_improvement_percent=request.min_improvement_percent,
    )
    return result.to_dict()


@router.post("/candidates/decision/record")
def record(request: DecisionRecordRequest) -> dict:
    """Store a developer accept/reject action in the experiment history."""
    try:
        return record_decision(
            candidate_id=request.candidate_id,
            status=request.status,
            developer_action=request.developer_action,
            rationale=request.rationale,
            measured_improvement_percent=request.measured_improvement_percent,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/candidates/history")
def history(limit: int = 50) -> dict:
    """Return recent optimization decisions (newest first)."""
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500.")
    records = load_decision_history(limit=limit)
    return {"decisions": records, "count": len(records)}


# ============================================================
# 5. FULL PIPELINE (SSE)
# ============================================================

@router.post("/pipeline/run/stream")
def run_pipeline(request: PipelineRequest) -> StreamingResponse:
    """Run detect → generate → rank → verify → (benchmark) → decide, streamed.

    Emits one SSE event per step:

    * ``{"type": "progress", "stage", "percent", "message"}``
    * ``{"type": "partial", "stage", "payload"}`` for each finished stage
    * ``{"type": "result", "result": {...}}`` as the final event
    * ``{"type": "error", "message"}`` on failure
    """

    def event_generator() -> Iterator[str]:
        try:
            percent = 2
            yield _sse({"type": "progress", "stage": "detect", "percent": percent,
                        "message": "Parsing file and detecting energy smells…"})

            path, source, language, state, detections = _read_target(
                request.file_path, request.language
            )
            yield _sse({
                "type": "partial",
                "stage": "detect",
                "payload": {
                    "language": language,
                    "detections": detections,
                    "detection_summary": summarise_detections(detections),
                },
            })

            if not detections:
                yield _sse({
                    "type": "result",
                    "result": {
                        "file_path": str(path),
                        "language": language,
                        "detections": [],
                        "candidates": [],
                        "stopped_reason": "no_detections",
                        "message": "No energy smells detected — nothing to optimise.",
                    },
                })
                return

            percent = 15
            yield _sse({"type": "progress", "stage": "generate", "percent": percent,
                        "message": f"Asking the model for {request.num_candidates} candidate(s)…"})

            generator = CandidateGenerator()
            if not generator.is_available:
                yield _sse({
                    "type": "error",
                    "message": (
                        "Candidate generation is not configured. Set GEMINI_API_KEY "
                        "in OASIS/.env and restart the backend."
                    ),
                })
                return

            candidates = _candidate_dicts(
                generator.generate(
                    source_code=source,
                    detections=detections,
                    language=language,
                    num_candidates=request.num_candidates,
                    path=str(path),
                )
            )

            percent = 28
            yield _sse({"type": "progress", "stage": "rank", "percent": percent,
                        "message": "Ranking candidates by predicted impact and risk…"})
            candidates = rank_candidates(
                candidates, original_code=source, detection_count=len(detections)
            )
            yield _sse({"type": "partial", "stage": "generate",
                        "payload": {"candidates": candidates}})

            verification_service = VerificationService(timeout=min(request.timeout, 60))
            benchmark_service = None
            if not request.skip_benchmark and request.command.strip():
                from modules.benchmarking import BenchmarkService

                benchmark_service = BenchmarkService()

            project_path = request.project_path or str(path.parent)
            total = len(candidates)

            for position, candidate in enumerate(candidates, start=1):
                base = 28 + (position - 1) / max(1, total) * 55
                share = 55 / max(1, total)

                # --- VERIFY -------------------------------------------------
                yield _sse({
                    "type": "progress", "stage": "verify", "percent": round(base),
                    "message": f"Verifying candidate {position}/{total}…",
                })
                candidate["candidate_index"] = position
                verification = verification_service.verify(
                    original_code=source,
                    candidate_code=candidate.get("source_code", ""),
                    language=language,
                ).to_dict()
                candidate["verification"] = verification
                candidate["correctness_status"] = verification["status"]
                yield _sse({"type": "partial", "stage": "verify",
                            "payload": {"candidate_id": candidate.get("candidate_id"),
                                        "verification": verification}})

                # --- BENCHMARK ----------------------------------------------
                benchmark = None
                if benchmark_service is not None:
                    if verification["passed"]:
                        yield _sse({
                            "type": "progress", "stage": "benchmark",
                            "percent": round(base + share * 0.35),
                            "message": f"Measuring energy for candidate {position}/{total} "
                                       f"({request.runs} run(s) + {request.warmup_runs} warm-up)…",
                        })
                        try:
                            benchmark = benchmark_service.benchmark(
                                project_path=project_path,
                                target_file=str(path),
                                candidate_code=candidate.get("source_code", ""),
                                command=request.command,
                                runs=request.runs,
                                warmup_runs=request.warmup_runs,
                                timeout=request.timeout,
                                language=language,
                            ).to_dict()
                        except Exception as error:  # a failed benchmark is evidence, not a crash
                            benchmark = {"status": "BENCHMARK_FAILED", "errors": [str(error)]}
                    else:
                        benchmark = {
                            "status": "BENCHMARK_PENDING",
                            "errors": ["Skipped: correctness verification did not pass."],
                        }

                if benchmark is not None:
                    candidate["benchmark"] = benchmark
                    candidate["benchmark_status"] = benchmark.get("status")
                    candidate["measured_energy"] = {
                        "original_mean_joules": (
                            benchmark.get("original_summary") or {}
                        ).get("mean_energy_joules"),
                        "candidate_mean_joules": (
                            benchmark.get("candidate_summary") or {}
                        ).get("mean_energy_joules"),
                        "improvement_percent": benchmark.get("improvement_percent"),
                    }
                    candidate["measured_time"] = {
                        "original_mean_seconds": (
                            benchmark.get("original_summary") or {}
                        ).get("mean_duration_seconds"),
                        "candidate_mean_seconds": (
                            benchmark.get("candidate_summary") or {}
                        ).get("mean_duration_seconds"),
                    }

                # --- DECIDE --------------------------------------------------
                yield _sse({
                    "type": "progress", "stage": "decide",
                    "percent": round(base + share * 0.85),
                    "message": f"Deciding on candidate {position}/{total}…",
                })
                decision = decide_optimization(
                    candidate=candidate,
                    verification=verification,
                    benchmark=benchmark,
                    min_improvement_percent=request.min_improvement_percent,
                ).to_dict()
                candidate["decision"] = decision
                candidate["final_status"] = decision["status"]

                yield _sse({"type": "partial", "stage": "decide",
                            "payload": {"candidate_id": candidate.get("candidate_id"),
                                        "decision": decision}})

            yield _sse({"type": "progress", "stage": "report", "percent": 99,
                        "message": "Summarising results…"})

            measured = [c for c in candidates if (c.get("benchmark") or {}).get("status") == "MEASURED"]
            improved = [c for c in candidates if c.get("final_status") == "IMPROVED"]

            yield _sse({
                "type": "result",
                "result": {
                    "file_path": str(path),
                    "project_path": project_path,
                    "language": language,
                    "model": generator.client.model,
                    "detections": detections,
                    "detection_summary": summarise_detections(detections),
                    "candidates": candidates,
                    "benchmark_ran": benchmark_service is not None,
                    "command": request.command,
                    "summary": {
                        "candidates_generated": len(candidates),
                        "verified": sum(
                            1 for c in candidates if c.get("correctness_status") == "VERIFIED"
                        ),
                        "measured": len(measured),
                        "improved": len(improved),
                        "best_improvement_percent": (
                            max(
                                (c["measured_energy"]["improvement_percent"] for c in measured
                                 if c.get("measured_energy", {}).get("improvement_percent") is not None),
                                default=None,
                            )
                        ),
                    },
                    "note": (
                        "Outcomes are based on measured energy only. Predictions are "
                        "reported separately and never counted as savings."
                    ),
                },
            })

        except FileNotFoundError as error:
            yield _sse({"type": "error", "message": str(error)})
        except ValueError as error:
            yield _sse({"type": "error", "message": str(error)})
        except LLMError as error:
            yield _sse({"type": "error", "message": f"LLM failure: {error}"})
        except Exception as error:  # keep the stream contract intact
            yield _sse({"type": "error", "message": f"Pipeline failed: {error}"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
