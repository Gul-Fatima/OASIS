"""Functional correctness verification for generated candidates.

Correctness has priority over optimization (CLAUDE.md section 10). A candidate
is only ``VERIFIED`` when it parses *and* behaves identically to the original
on the available evidence.

Two layers of evidence are used:

1. **Syntax** — the candidate must compile/parse. Always run.
2. **Behaviour** — original and candidate are executed in isolated subprocesses
   with the same input and their stdout / exit codes are compared. Optional
   dataset-based tests (through ``validator.validate_pair``) can be supplied
   for stronger evidence.

Known limitation: execution uses subprocess isolation, a timeout and UTF-8
pinning, but it is *not* a container sandbox. Only run OASIS against code you
are willing to execute on this machine.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from modules.verification.validator import ValidationResult, validate_pair

EXECUTABLE_LANGUAGES = {"python"}

# Statuses come from the fixed vocabulary in CLAUDE.md section 14.
STATUS_VERIFIED = "VERIFIED"
STATUS_FAILED = "VERIFICATION_FAILED"
STATUS_PENDING = "VERIFICATION_PENDING"


@dataclass
class Check:
    """One verification check and its outcome (None = not applicable/skipped)."""

    name: str
    passed: bool | None
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


@dataclass
class VerificationResult:
    """Aggregate result of verifying one candidate."""

    status: str
    passed: bool
    inconclusive: bool = False
    syntax_ok: bool | None = None
    behaviour_ok: bool | None = None
    checks: list[Check] = field(default_factory=list)
    tests_total: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "passed": self.passed,
            "inconclusive": self.inconclusive,
            "syntax_ok": self.syntax_ok,
            "behaviour_ok": self.behaviour_ok,
            "checks": [check.to_dict() for check in self.checks],
            "tests_total": self.tests_total,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "errors": self.errors,
            "notes": self.notes,
        }


class VerificationService:
    """Verifies that a candidate preserves the original behaviour."""

    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout

    # ------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------

    def verify(
        self,
        original_code: str,
        candidate_code: str,
        language: str = "python",
        test_inputs: list[str] | None = None,
        test_outputs: list[str] | None = None,
        timeout: float | None = None,
    ) -> VerificationResult:
        """Verify ``candidate_code`` against ``original_code``."""
        timeout = timeout or self.timeout
        language = (language or "python").lower()

        result = VerificationResult(status=STATUS_PENDING, passed=False)

        if not candidate_code or not candidate_code.strip():
            result.checks.append(Check("non_empty", False, "Candidate code is empty."))
            result.errors.append("Candidate code is empty.")
            result.status = STATUS_FAILED
            return result
        result.checks.append(Check("non_empty", True, "Candidate contains code."))

        if candidate_code.strip() == original_code.strip():
            result.notes.append(
                "Candidate is byte-identical to the original — no optimization was applied."
            )

        # ------------------------------------------------------
        # 1. SYNTAX
        # ------------------------------------------------------
        syntax_check = self._check_syntax(candidate_code, language)
        result.checks.append(syntax_check)
        result.syntax_ok = syntax_check.passed

        if syntax_check.passed is False:
            result.errors.append(syntax_check.detail)
            result.status = STATUS_FAILED
            return result

        # ------------------------------------------------------
        # 2. DATASET TESTS (strongest evidence, when supplied)
        # ------------------------------------------------------
        if test_inputs and test_outputs and language in EXECUTABLE_LANGUAGES:
            dataset_result = self._check_dataset(
                original_code, candidate_code, test_inputs, test_outputs
            )
            result.tests_total = dataset_result.total_tests
            result.tests_passed = dataset_result.passed_tests
            result.tests_failed = dataset_result.failed_tests
            result.errors.extend(dataset_result.errors)
            result.checks.append(
                Check(
                    "dataset_tests",
                    dataset_result.passed,
                    f"{dataset_result.passed_tests}/{dataset_result.total_tests} test cases matched.",
                )
            )
            if not dataset_result.passed:
                result.status = STATUS_FAILED
                return result

            result.behaviour_ok = True
            result.passed = True
            result.status = STATUS_VERIFIED
            return result

        # ------------------------------------------------------
        # 3. BEHAVIOUR (execute both versions, compare output)
        # ------------------------------------------------------
        behaviour_check, inconclusive = self._check_behaviour(
            original_code, candidate_code, language, timeout
        )
        result.checks.append(behaviour_check)
        result.behaviour_ok = behaviour_check.passed

        if behaviour_check.passed is False:
            result.errors.append(behaviour_check.detail)
            result.status = STATUS_FAILED
            return result

        if inconclusive:
            # Not enough evidence to call it correct — never treat as verified.
            result.inconclusive = True
            result.passed = False
            result.status = STATUS_PENDING
            result.notes.append(
                "Behaviour could not be compared automatically; run the candidate "
                "against a test suite before accepting it."
            )
            return result

        result.passed = True
        result.status = STATUS_VERIFIED
        return result

    # ------------------------------------------------------------
    # CHECKS
    # ------------------------------------------------------------

    def _check_syntax(self, code: str, language: str) -> Check:
        if language == "python":
            try:
                compile(code, "<candidate>", "exec")
            except SyntaxError as exc:
                return Check(
                    "syntax",
                    False,
                    f"Syntax error on line {exc.lineno}: {exc.msg}",
                )
            return Check("syntax", True, "Candidate parses as valid Python.")

        return Check(
            "syntax",
            None,
            f"Syntax checking is not implemented for '{language}'; skipped.",
        )

    def _check_dataset(
        self,
        original_code: str,
        candidate_code: str,
        test_inputs: list[str],
        test_outputs: list[str],
    ) -> ValidationResult:
        return validate_pair(
            original_code,
            candidate_code,
            test_inputs,
            test_outputs,
        )

    def _check_behaviour(
        self,
        original_code: str,
        candidate_code: str,
        language: str,
        timeout: float,
    ) -> tuple[Check, bool]:
        """Run both versions and compare stdout / exit status.

        Returns ``(check, inconclusive)``. ``inconclusive`` is True when the
        comparison produced no usable signal (non-executable language, both
        versions failing identically, or a timeout).
        """
        if language not in EXECUTABLE_LANGUAGES:
            return (
                Check(
                    "behaviour",
                    None,
                    f"Automatic execution is not supported for '{language}'. "
                    "Provide test cases from the original language's toolchain.",
                ),
                True,
            )

        original_run = self._run_python(original_code, timeout)
        candidate_run = self._run_python(candidate_code, timeout)

        if original_run["timed_out"] or candidate_run["timed_out"]:
            return (
                Check(
                    "behaviour",
                    None,
                    f"Execution exceeded the {timeout:.0f}s timeout; comparison skipped.",
                ),
                True,
            )

        original_ok = original_run["return_code"] == 0
        candidate_ok = candidate_run["return_code"] == 0

        if not original_ok and not candidate_ok:
            return (
                Check(
                    "behaviour",
                    None,
                    "Both the original and the candidate failed to run standalone "
                    "(the file probably needs arguments, stdin or dependencies).",
                ),
                True,
            )

        if original_ok and not candidate_ok:
            return (
                Check(
                    "behaviour",
                    False,
                    "The candidate crashed where the original succeeded: "
                    f"{_tail(candidate_run['stderr']) or 'non-zero exit code'}",
                ),
                False,
            )

        if candidate_ok and not original_ok:
            return (
                Check(
                    "behaviour",
                    None,
                    "The original failed standalone but the candidate ran, so the "
                    "outputs are not comparable.",
                ),
                True,
            )

        if original_run["stdout"] == candidate_run["stdout"]:
            return (
                Check(
                    "behaviour",
                    True,
                    "Both versions produced identical stdout and exit code 0.",
                ),
                False,
            )

        return (
            Check(
                "behaviour",
                False,
                "Output differs between the original and the candidate. First "
                f"difference: original={_first_diff(original_run['stdout'], candidate_run['stdout'])} "
                f"candidate={_first_diff(candidate_run['stdout'], original_run['stdout'])}",
            ),
            False,
        )

    def _run_python(self, code: str, timeout: float) -> dict[str, Any]:
        """Execute Python source in a temporary directory, isolated."""
        tmp_dir = Path(tempfile.mkdtemp(prefix="oasis_verify_"))
        script = tmp_dir / "candidate.py"
        script.write_text(code, encoding="utf-8")

        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "utf-8"
        environment["PYTHONUTF8"] = "1"

        try:
            completed = subprocess.run(
                [sys.executable, str(script)],
                cwd=str(tmp_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=environment,
                timeout=timeout,
                stdin=subprocess.DEVNULL,
            )
            return {
                "return_code": completed.returncode,
                "stdout": _normalise(completed.stdout),
                "stderr": completed.stderr or "",
                "timed_out": False,
            }
        except subprocess.TimeoutExpired:
            return {"return_code": -1, "stdout": "", "stderr": "", "timed_out": True}
        except Exception as exc:  # pragma: no cover - defensive
            return {
                "return_code": -1,
                "stdout": "",
                "stderr": str(exc),
                "timed_out": False,
            }
        finally:
            for leftover in tmp_dir.glob("**/*"):
                if leftover.is_file():
                    try:
                        leftover.unlink()
                    except OSError:
                        pass
            try:
                tmp_dir.rmdir()
            except OSError:
                pass


def _normalise(text: str) -> str:
    """Compare output while ignoring trailing whitespace on each line."""
    return "\n".join(line.rstrip() for line in (text or "").splitlines()).strip()


def _first_diff(left: str, right: str) -> str:
    """First line of ``left`` that is not in ``right``, for error messages."""
    right_lines = set(right.splitlines())
    for line in left.splitlines():
        if line not in right_lines:
            return repr(line[:100])
    return repr("")


def _tail(text: str, limit: int = 200) -> str:
    return (text or "").strip()[-limit:]


__all__ = ["Check", "VerificationResult", "VerificationService"]
