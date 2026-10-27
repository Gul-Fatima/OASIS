"""Empirical benchmarking of original vs candidate code.

Measurement, not prediction (CLAUDE.md section 1). This is the only place in
OASIS that may claim a measured improvement, and only after both versions
have actually been executed under the same command and machine conditions.

Procedure (CLAUDE.md section 9):

    warm-up  →  original run 1..N  →  candidate run 1..N  →  aggregate  →  compare

The candidate never overwrites the user's file: it is written into a
temporary copy of the project.
"""

from __future__ import annotations

import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from modules.benchmarking.comparator import (
    ComparisonResult,
    MeasurementRecord,
    compare_measurements,
)
from modules.config import results_dir
from modules.energy_estimation.estimator import EnergyEstimator
from modules.energy_estimation.executor import ProjectExecutor

# Directories that are never copied into a benchmark workspace.
SKIP_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", "node_modules", ".next", ".venv",
    "venv", "env", "dist", "build", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "results", ".idea", ".vscode", "third_party",
}

KWH_TO_JOULES = 3.6e6


@dataclass
class RunMeasurement:
    """One executed run of one version."""

    label: str
    index: int
    success: bool
    energy_kwh: float | None = None
    joules: float | None = None
    duration_seconds: float | None = None
    average_watts: float | None = None
    return_code: int | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "index": self.index,
            "success": self.success,
            "energy_kwh": self.energy_kwh,
            "energy_joules": self.joules,
            "duration_seconds": self.duration_seconds,
            "average_watts": self.average_watts,
            "return_code": self.return_code,
            "error": self.error,
        }


@dataclass
class BenchmarkResult:
    """Aggregate benchmark outcome — measured values only."""

    status: str
    runs_per_version: int
    warmup_runs: int
    original: list[RunMeasurement] = field(default_factory=list)
    candidate: list[RunMeasurement] = field(default_factory=list)
    original_summary: dict[str, Any] = field(default_factory=dict)
    candidate_summary: dict[str, Any] = field(default_factory=dict)
    improvement_percent: float | None = None
    comparison: ComparisonResult | None = None
    notes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "runs_per_version": self.runs_per_version,
            "warmup_runs": self.warmup_runs,
            "original": [run.to_dict() for run in self.original],
            "candidate": [run.to_dict() for run in self.candidate],
            "original_summary": self.original_summary,
            "candidate_summary": self.candidate_summary,
            "improvement_percent": self.improvement_percent,
            "comparison": self.comparison,
            "verdict": self._verdict(),
            "notes": self.notes,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds,
        }

    def _verdict(self) -> str:
        if self.status != "MEASURED":
            return self.status
        if self.improvement_percent is None:
            return "INCONCLUSIVE"
        if self.improvement_percent > 0:
            return "CANDIDATE_LOWER_ENERGY"
        if self.improvement_percent < 0:
            return "CANDIDATE_HIGHER_ENERGY"
        return "NO_DIFFERENCE"


class BenchmarkService:
    """Executes original and candidate under identical conditions."""

    def __init__(
        self,
        output_dir: str | None = None,
        progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.output_dir = str(output_dir or results_dir("benchmark"))
        self.progress = progress

    # ------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------

    def benchmark(
        self,
        project_path: str,
        target_file: str,
        candidate_code: str,
        command: str,
        runs: int = 2,
        warmup_runs: int = 1,
        timeout: int = 300,
        language: str = "python",
    ) -> BenchmarkResult:
        """Measure ``command`` with the original file and with the candidate."""
        started = time.perf_counter()
        result = BenchmarkResult(
            status="BENCHMARK_PENDING",
            runs_per_version=max(1, runs),
            warmup_runs=max(0, warmup_runs),
        )

        project = Path(project_path)
        target = Path(target_file)

        if not project.exists():
            raise FileNotFoundError(f"Project path not found: {project_path}")
        if not target.exists():
            raise FileNotFoundError(f"Target file not found: {target_file}")
        if not command or not command.strip():
            raise ValueError(
                "An execution command is required to benchmark — static analysis "
                "cannot produce measured energy values."
            )

        workspace: Path | None = None
        try:
            self._emit("Preparing isolated benchmark workspace…")
            workspace = self._copy_project(project)
            candidate_target = workspace / target.resolve().relative_to(project.resolve())
            candidate_target.write_text(candidate_code, encoding="utf-8")

            for label, working_dir in (("original", project), ("candidate", workspace)):
                self._emit(f"Measuring {label} ({result.runs_per_version} run(s) + warm-up)…")
                measurements, errors = self._measure_version(
                    label=label,
                    working_directory=str(working_dir),
                    command=command,
                    runs=result.runs_per_version,
                    warmup_runs=result.warmup_runs,
                    timeout=timeout,
                )
                result.errors.extend(errors)

                if label == "original":
                    result.original = measurements
                else:
                    result.candidate = measurements

            original_success = [m for m in result.original if m.success and m.joules]
            candidate_success = [m for m in result.candidate if m.success and m.joules]

            if not original_success or not candidate_success:
                result.status = "BENCHMARK_FAILED"
                result.errors.append(
                    "At least one successful measurement per version is required "
                    "before an improvement can be claimed."
                )
                return result

            result.original_summary = _summarise(original_success, "original")
            result.candidate_summary = _summarise(candidate_success, "candidate")

            result.improvement_percent = _improvement_percent(
                result.original_summary, result.candidate_summary
            )

            result.comparison = compare_measurements(
                [
                    _to_record(result.original_summary, "original"),
                    _to_record(result.candidate_summary, "candidate"),
                ],
                comparison_metric="energy",
            )

            result.status = "MEASURED"
            return result

        finally:
            result.duration_seconds = time.perf_counter() - started
            if workspace is not None:
                shutil.rmtree(workspace, ignore_errors=True)

    # ------------------------------------------------------------
    # INTERNALS
    # ------------------------------------------------------------

    def _emit(self, message: str) -> None:
        if self.progress is not None:
            self.progress({"type": "progress", "stage": "benchmark", "message": message})

    def _copy_project(self, project: Path) -> Path:
        workspace = Path(tempfile.mkdtemp(prefix="oasis_bench_"))

        if project.is_file():
            shutil.copy2(project, workspace / project.name)
            return workspace

        shutil.copytree(
            project,
            workspace,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(*SKIP_DIRS),
        )
        return workspace

    def _measure_version(
        self,
        label: str,
        working_directory: str,
        command: str,
        runs: int,
        warmup_runs: int,
        timeout: int,
    ) -> tuple[list[RunMeasurement], list[str]]:
        measurements: list[RunMeasurement] = []
        errors: list[str] = []

        for warmup_index in range(warmup_runs):
            self._emit(f"Warm-up {warmup_index + 1}/{warmup_runs} ({label})…")
            run = self._run_once(label, -(warmup_index + 1), working_directory, command, timeout)
            if not run.success:
                errors.append(f"{label} warm-up failed: {run.error}")

        for index in range(1, runs + 1):
            self._emit(f"Run {index}/{runs} ({label})…")
            run = self._run_once(label, index, working_directory, command, timeout)
            measurements.append(run)
            if not run.success:
                errors.append(f"{label} run {index} failed: {run.error}")

        return measurements, errors

    def _run_once(
        self,
        label: str,
        index: int,
        working_directory: str,
        command: str,
        timeout: int,
    ) -> RunMeasurement:
        try:
            executor = ProjectExecutor(
                command=command,
                working_directory=working_directory,
                timeout=timeout,
            )
            estimator = EnergyEstimator(output_dir=self.output_dir)
            measured = estimator.estimate(executor)
        except Exception as exc:  # measurement failures must not abort the benchmark
            return RunMeasurement(
                label=label, index=index, success=False, error=str(exc)
            )

        energy_kwh = _as_float(measured.get("energy_consumed"))
        duration = _as_float(measured.get("execution_time_seconds"))
        return_code = measured.get("return_code")
        success = bool(measured.get("baseline_valid")) and energy_kwh is not None

        joules = energy_kwh * KWH_TO_JOULES if energy_kwh is not None else None
        average_watts = (
            joules / duration if joules is not None and duration and duration > 0 else None
        )

        return RunMeasurement(
            label=label,
            index=index,
            success=success,
            energy_kwh=energy_kwh,
            joules=joules,
            duration_seconds=duration,
            average_watts=average_watts,
            return_code=return_code,
            error=None if success else (measured.get("stderr") or "measurement invalid"),
        )


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _summarise(runs: list[RunMeasurement], label: str) -> dict[str, Any]:
    """Mean energy/time over successful runs, with spread information."""
    count = len(runs)
    joules = [run.joules for run in runs if run.joules is not None]
    durations = [run.duration_seconds for run in runs if run.duration_seconds is not None]

    mean_joules = sum(joules) / len(joules) if joules else None
    mean_duration = sum(durations) / len(durations) if durations else None

    return {
        "label": label,
        "runs": count,
        "mean_energy_joules": mean_joules,
        "min_energy_joules": min(joules) if joules else None,
        "max_energy_joules": max(joules) if joules else None,
        "mean_duration_seconds": mean_duration,
        "average_watts": (
            mean_joules / mean_duration
            if mean_joules is not None and mean_duration
            else None
        ),
        "energy_spread_percent": (
            ((max(joules) - min(joules)) / mean_joules * 100)
            if joules and mean_joules
            else None
        ),
    }


def _to_record(summary: dict[str, Any], session_id: str) -> MeasurementRecord:
    return MeasurementRecord(
        session_id=session_id,
        total_joules=summary.get("mean_energy_joules") or 0.0,
        average_watts=summary.get("average_watts") or 0.0,
        peak_watts=summary.get("average_watts") or 0.0,
        duration_seconds=summary.get("mean_duration_seconds") or 0.0,
        success=True,
    )


def _improvement_percent(
    original_summary: dict[str, Any],
    candidate_summary: dict[str, Any],
) -> float | None:
    """Percentage of energy saved by the candidate (positive = better)."""
    original = original_summary.get("mean_energy_joules")
    candidate = candidate_summary.get("mean_energy_joules")

    if not original or candidate is None or original <= 0:
        return None

    return (original - candidate) / original * 100.0


__all__ = ["BenchmarkResult", "BenchmarkService", "RunMeasurement"]
