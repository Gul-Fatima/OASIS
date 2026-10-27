"""Functional correctness validator.

Executes code against test inputs and compares outputs to verify
that optimized candidates produce the same results as the original.

Adapted from SMART-Dal/Energy-Smells validate_correctness.py (CC-BY-4.0).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of a correctness validation run."""
    passed: bool
    total_tests: int
    passed_tests: int
    failed_tests: int
    errors: list[str]


def validate_code(
    code_str: str,
    input_file_path: str,
    expected_output_str: str,
    tmp_dir: str,
    timeout: float = 4.0,
) -> tuple[bool, str]:
    """Execute code against one test input and check the output.

    Args:
        code_str: Source code to execute.
        input_file_path: Path to the input file.
        expected_output_str: Expected output string.
        tmp_dir: Directory for temporary files.
        timeout: Execution timeout in seconds.

    Returns:
        (passed, error_message) tuple.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", dir=tmp_dir, suffix=".py", delete=False
    ) as temp_code:
        temp_code.write(code_str)
        temp_code_path = temp_code.name

    try:
        with open(input_file_path, "r") as f_in:
            result = subprocess.run(
                [sys.executable, temp_code_path],
                stdin=f_in,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

        if result.returncode != 0:
            return False, f"Execution error: {result.stderr.strip()}"

        actual_output = result.stdout.strip()
        expected_output = expected_output_str.strip()

        if actual_output == expected_output:
            return True, ""
        else:
            return False, "Output mismatch"

    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, f"Exception: {e}"
    finally:
        if os.path.exists(temp_code_path):
            os.remove(temp_code_path)


def validate_pair(
    code_v0: str,
    code_v1: str,
    test_inputs: list[str],
    test_outputs: list[str],
    max_tests: int = 5,
) -> ValidationResult:
    """Validate that two code versions produce identical outputs.

    Args:
        code_v0: Original code version.
        code_v1: Optimized code version.
        test_inputs: List of input file paths.
        test_outputs: List of expected output strings.
        max_tests: Maximum number of test cases to run.

    Returns:
        ValidationResult with pass/fail status.
    """
    import random

    tmp_dir = tempfile.mkdtemp(prefix="oasis_verify_")
    errors: list[str] = []
    passed_count = 0

    n = min(len(test_inputs), len(test_outputs), max_tests)
    if n == 0:
        return ValidationResult(
            passed=False, total_tests=0, passed_tests=0,
            failed_tests=0, errors=["No test cases provided"],
        )

    indices = random.sample(range(n), n) if n > 5 else list(range(n))

    for idx in indices[:max_tests]:
        input_path = test_inputs[idx]
        expected = test_outputs[idx]

        v0_pass, v0_err = validate_code(code_v0, input_path, expected, tmp_dir)
        if not v0_pass:
            errors.append(f"v0 failed on test {idx}: {v0_err}")
            break

        v1_pass, v1_err = validate_code(code_v1, input_path, expected, tmp_dir)
        if not v1_pass:
            errors.append(f"v1 failed on test {idx}: {v1_err}")
            break

        passed_count += 1

    total = min(len(indices), max_tests)
    return ValidationResult(
        passed=passed_count == total and not errors,
        total_tests=total,
        passed_tests=passed_count,
        failed_tests=total - passed_count,
        errors=errors,
    )


def warmup_cpu(duration: float = 2.0) -> None:
    """Busy-wait to stabilize CPU frequency before measurement.

    Adapted from SMART-Dal/Energy-Smells warmup.py.
    """
    import time
    end_time = time.time() + duration
    while time.time() < end_time:
        pass
