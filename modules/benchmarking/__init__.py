"""Benchmarking Module

Compares energy measurements between original and optimized implementations
and generates reports with statistical analysis.

Based on: SMART-Dal/codegreen MeasurementEngine (MPL-2.0).

``service.py`` runs the actual original-vs-candidate experiment; ``comparator``
provides the measurement records and ranking helpers.
"""

from .comparator import (
    ComparisonResult,
    MeasurementRecord,
    compare_measurements,
    generate_report,
    report_to_csv,
)
from .service import BenchmarkResult, BenchmarkService, RunMeasurement

__all__ = [
    "BenchmarkResult",
    "BenchmarkService",
    "ComparisonResult",
    "MeasurementRecord",
    "RunMeasurement",
    "compare_measurements",
    "generate_report",
    "report_to_csv",
]
