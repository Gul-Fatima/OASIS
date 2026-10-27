"""Energy measurement comparison and reporting.

Extracted from SMART-Dal/codegreen MeasurementEngine (MPL-2.0).
"""

from __future__ import annotations

import csv
import io
import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class MeasurementRecord:
    """A single energy measurement record."""
    session_id: str
    total_joules: float
    average_watts: float
    peak_watts: float
    duration_seconds: float
    file_path: str = ""
    language: str = "python"
    success: bool = True
    error_message: Optional[str] = None

    @property
    def energy_per_second(self) -> float:
        return self.total_joules / self.duration_seconds if self.duration_seconds > 0 else 0.0


@dataclass
class ComparisonResult:
    """Result of comparing two or more measurements."""
    comparison_metric: str
    rankings: list[dict[str, Any]]
    best_performer: dict[str, Any]
    worst_performer: dict[str, Any]
    average_improvement: float


def compare_measurements(
    measurements: list[MeasurementRecord],
    comparison_metric: str = "energy",
) -> ComparisonResult:
    """Compare multiple measurements and rank them.

    Args:
        measurements: List of measurement records to compare.
        comparison_metric: Metric to compare ("energy", "power", "duration", "efficiency").

    Returns:
        ComparisonResult with rankings and insights.
    """
    if len(measurements) < 2:
        raise ValueError("At least 2 measurements needed for comparison")

    key_map = {
        "energy": "total_joules",
        "power": "average_watts",
        "duration": "duration_seconds",
        "efficiency": "energy_per_second",
    }
    key = key_map.get(comparison_metric, "total_joules")
    sorted_m = sorted(measurements, key=lambda m: getattr(m, key))
    best = sorted_m[0]
    worst = sorted_m[-1]

    rankings = []
    for i, m in enumerate(sorted_m):
        val = getattr(m, key)
        worst_val = getattr(worst, key)
        improvement = ((worst_val - val) / worst_val * 100) if worst_val > 0 else 0.0
        rankings.append({
            "rank": i + 1,
            "session_id": m.session_id,
            "metric_value": val,
            "improvement_vs_worst": improvement,
        })

    best_val = getattr(best, key)
    worst_val = getattr(worst, key)
    best_savings = ((worst_val - best_val) / worst_val * 100) if worst_val > 0 else 0.0

    return ComparisonResult(
        comparison_metric=comparison_metric,
        rankings=rankings,
        best_performer={
            "session_id": best.session_id,
            "value": best_val,
            "savings_vs_worst": best_savings,
        },
        worst_performer={
            "session_id": worst.session_id,
            "value": worst_val,
        },
        average_improvement=sum(r["improvement_vs_worst"] for r in rankings) / len(rankings),
    )


def generate_report(
    measurements: list[MeasurementRecord],
    output_format: str = "json",
) -> dict[str, Any]:
    """Generate a comprehensive energy measurement report.

    Args:
        measurements: List of measurement records.
        output_format: Output format ("json", "csv", "text").

    Returns:
        Report data as a dictionary.
    """
    if not measurements:
        return {"error": "No measurements provided"}

    successful = [m for m in measurements if m.success]
    total_energy = sum(m.total_joules for m in measurements)
    avg_power = sum(m.average_watts for m in measurements) / len(measurements)
    total_duration = sum(m.duration_seconds for m in measurements)

    return {
        "report_metadata": {
            "generated_at": time.time(),
            "total_measurements": len(measurements),
            "successful_measurements": len(successful),
            "failed_measurements": len(measurements) - len(successful),
        },
        "summary": {
            "total_energy_joules": total_energy,
            "average_power_watts": avg_power,
            "total_duration_seconds": total_duration,
            "average_duration_seconds": total_duration / len(measurements),
        },
        "measurements": [
            {
                "session_id": m.session_id,
                "energy_joules": m.total_joules,
                "average_watts": m.average_watts,
                "peak_watts": m.peak_watts,
                "duration_seconds": m.duration_seconds,
                "energy_per_second": m.energy_per_second,
                "file_path": m.file_path,
                "language": m.language,
                "success": m.success,
                "error_message": m.error_message,
            }
            for m in measurements
        ],
    }


def report_to_csv(report: dict[str, Any]) -> str:
    """Convert a report dict to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'session_id', 'energy_joules', 'average_watts', 'peak_watts',
        'duration_seconds', 'file_path', 'language', 'success',
    ])
    for m in report.get("measurements", []):
        writer.writerow([
            m['session_id'], m['energy_joules'], m['average_watts'],
            m['peak_watts'], m['duration_seconds'], m['file_path'],
            m['language'], m['success'],
        ])
    return output.getvalue()
