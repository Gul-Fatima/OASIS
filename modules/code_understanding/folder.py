
"""Folder-level code understanding.

Parses supported source files under a directory and merges per-file
CodeState objects into a project-level summary.

A single file path is also accepted.

Files that cannot be read or parsed are recorded as failures rather
than aborting the entire scan.

analyze_folder() is a generator that yields progress events followed
by one result event. This supports streaming progress through the API.

This module does not make energy-consumption claims.
"""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Iterator, Optional

from .adapters import ADAPTERS
from .language_config import get_language_config_manager
from .model import CodeState
from .parser import parse_code


# ============================================================
# CONFIGURATION
# ============================================================

IGNORED_DIRECTORIES = frozenset({
    ".git", ".hg", ".svn", ".idea", ".vscode", ".vs",
    "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", ".tox", ".nox", ".venv", "venv", "env",
    "virtualenv", "site-packages", "dist", "build", "target",
    "out", "vendor", ".next", ".gradle", ".terraform",
    "coverage", "htmlcov",
})

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_FILES = 1000

MAX_FUNCTIONS = 2000
MAX_CLASSES = 1000
MAX_LOOPS = 2000
MAX_CALLS = 500
MAX_IO_OPERATIONS = 200
MAX_FILE_DETAIL = 500


# ============================================================
# PATH HELPERS
# ============================================================

def relative_name(path: Path, root: Path) -> str:
    """Return a display-friendly path relative to the scan root."""
    path = Path(path).resolve()
    root = Path(root).resolve()

    # For single-file analysis, display only the filename.
    if root.is_file():
        return path.name

    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        # Defensive fallback if the file is outside the scan root.
        return path.as_posix()


# ============================================================
# SOURCE FILE DISCOVERY
# ============================================================

def discover_source_files(
    root: Path,
    language: str = "auto",
    max_files: int = MAX_FILES,
    recursive: bool = True,
) -> tuple[list[tuple[Path, str]], int]:
    """Discover supported source files under a file or directory.

    Returns:
        A tuple containing:
        - A list of (file_path, detected_language) pairs, capped at
          max_files.
        - The total supported count, or max_files + 1 if the scan
          found more supported files than the limit allows.

    The second value is a truncation indicator when it exceeds
    the number of returned files.
    """
    root = Path(root)

    if max_files < 1:
        raise ValueError("max_files must be greater than or equal to 1")

    manager = get_language_config_manager()
    found: list[tuple[Path, str]] = []
    limit_exceeded = False

    def consider(file_path: Path) -> None:
        nonlocal limit_exceeded

        try:
            if not file_path.is_file():
                return
        except OSError:
            return

        detected = language

        if detected == "auto":
            detected = manager.detect_language_from_filename(
                str(file_path)
            )

        if not detected or detected not in ADAPTERS:
            return

        # One additional supported file is enough to indicate truncation.
        if len(found) >= max_files:
            limit_exceeded = True
            return

        found.append((file_path, detected))

    if root.is_file():
        consider(root)

    elif root.is_dir() and recursive:
        for dirpath, dirnames, filenames in os.walk(
            root,
            onerror=lambda _error: None,
        ):
            # Prevent traversal into dependency, generated, and hidden
            # directories.
            dirnames[:] = sorted(
                name
                for name in dirnames
                if name not in IGNORED_DIRECTORIES
                and not name.startswith(".")
            )

            for name in sorted(filenames):
                consider(Path(dirpath) / name)

                if limit_exceeded:
                    break

            if limit_exceeded:
                break

    elif root.is_dir():
        try:
            entries = sorted(root.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            entries = []

        for entry in entries:
            if entry.is_file():
                consider(entry)

                if limit_exceeded:
                    break

    found.sort(key=lambda item: str(item[0]).lower())

    reported_count = (
        max_files + 1 if limit_exceeded else len(found)
    )

    return found, reported_count


# ============================================================
# SINGLE-FILE ANALYSIS
# ============================================================

def analyze_file(
    file_path: Path,
    language: str,
) -> tuple[Optional[CodeState], Optional[str], int]:
    """Parse one file and return (state, error, line_count)."""
    file_path = Path(file_path)

    try:
        size = file_path.stat().st_size
    except OSError as exc:
        return None, f"Cannot access file: {exc}", 0

    if size > MAX_FILE_BYTES:
        return (
            None,
            f"Skipped: file exceeds {MAX_FILE_BYTES} bytes",
            0,
        )

    try:
        source = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            source = file_path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            return None, f"Cannot read file: {exc}", 0
    except OSError as exc:
        return None, f"Cannot read file: {exc}", 0

    line_count = len(source.splitlines())

    try:
        state = parse_code(
            source,
            path=str(file_path),
            language=language,
        )
    except Exception as exc:
        # A parser failure for one file must not abort a folder scan.
        return None, f"Parse failed: {exc}", line_count

    if state is None:
        return None, "Parser returned no result", line_count

    return state, None, line_count


# ============================================================
# FOLDER SCAN
# ============================================================

def analyze_folder(
    root: str | Path,
    language: str = "auto",
    max_files: int = MAX_FILES,
    recursive: bool = True,
) -> Iterator[dict]:
    """Analyze a single source file or a directory of source files.

    Yields progress events and then exactly one result event.

    Progress event:
        {"type": "progress", ...}

    Result event:
        {"type": "result", "result": ...}
    """
    root = Path(root).expanduser().resolve()

    if not root.exists():
        raise FileNotFoundError(f"Path not found: {root}")

    if not root.is_file() and not root.is_dir():
        raise ValueError(f"Path is neither a file nor a directory: {root}")

    if max_files < 1:
        raise ValueError("max_files must be greater than or equal to 1")

    files, total_found = discover_source_files(
        root=root,
        language=language,
        max_files=max_files,
        recursive=recursive,
    )

    total = len(files)
    truncated_scan = total_found > total
    scan_root = root if root.is_dir() else root.parent

    yield {
        "type": "progress",
        "stage": "discover",
        "percent": 2.0 if total else 100.0,
        "current": 0,
        "total": total,
        "message": (
            f"Discovered {max_files}+ supported source files; "
            f"scanning the first {total}"
            if truncated_scan
            else f"Discovered {total_found} supported source file(s)"
        ),
    }

    states: list[tuple[str, CodeState]] = []
    failures: list[dict] = []
    total_lines = 0

    for index, (file_path, detected) in enumerate(files, start=1):
        rel = relative_name(file_path, root)

        yield {
            "type": "progress",
            "stage": "parse",
            "percent": round(
                3 + ((index - 1) / total) * 92,
                1,
            ),
            "current": index - 1,
            "total": total,
            "file": rel,
            "language": detected,
            "message": f"Parsing {rel} ({index}/{total})",
        }

        try:
            state, error, line_count = analyze_file(
                file_path,
                detected,
            )

            if state is None:
                failures.append({
                    "file": rel,
                    "language": detected,
                    "error": error or "Analysis returned no result",
                })
            else:
                states.append((rel, state))
                total_lines += line_count

        except Exception as exc:
            failures.append({
                "file": rel,
                "language": detected,
                "error": str(exc),
            })

    yield {
        "type": "progress",
        "stage": "aggregate",
        "percent": 97.0,
        "current": total,
        "total": total,
        "message": "Aggregating project results...",
    }

    result = aggregate_folder_states(
        root=root,
        scan_root=scan_root,
        states=states,
        failures=failures,
        total_found=total_found,
        total_lines=total_lines,
        truncated_scan=truncated_scan,
        language_filter=language,
    )

    yield {
        "type": "result",
        "result": result,
    }


# ============================================================
# AGGREGATION
# ============================================================

def aggregate_folder_states(
    *,
    root: Path,
    scan_root: Path,
    states: list[tuple[str, CodeState]],
    failures: list[dict],
    total_found: int,
    total_lines: int,
    truncated_scan: bool,
    language_filter: str = "auto",
) -> dict:
    """Merge per-file CodeStates into a project-level summary."""
    languages: Counter[str] = Counter()

    functions: list[dict] = []
    classes: list[dict] = []
    loops: list[dict] = []
    calls: list[dict] = []
    io_operations: list[dict] = []
    dependencies: set[str] = set()
    data_structures: set[str] = set()
    file_details: list[dict] = []

    conditionals = 0
    allocations = 0
    complexity_measured = 0
    complexity_total = 0
    complexity_max = 0

    for rel, state in states:
        languages[state.language] += 1

        conditionals += state.conditionals
        allocations += state.allocations
        dependencies.update(state.dependencies)
        data_structures.update(state.data_structures)

        complexity = state.complexity or {}

        if complexity:
            complexity_measured += int(complexity.get("measured", 0))
            complexity_total += int(complexity.get("total", 0))
            complexity_max = max(
                complexity_max,
                int(complexity.get("max", 0)),
            )

        for function in state.functions:
            if len(functions) >= MAX_FUNCTIONS:
                break

            entry = asdict(function)
            entry["file"] = rel
            entry["language"] = state.language
            functions.append(entry)

        for klass in state.classes:
            if len(classes) >= MAX_CLASSES:
                break

            entry = asdict(klass)
            entry["file"] = rel
            entry["language"] = state.language
            classes.append(entry)

        for loop in state.loops:
            if len(loops) >= MAX_LOOPS:
                break

            entry = asdict(loop)
            entry["file"] = rel
            loops.append(entry)

        for call in state.function_calls:
            if len(calls) >= MAX_CALLS:
                break

            entry = asdict(call)
            entry["file"] = rel
            calls.append(entry)

        for operation in state.io_operations:
            if len(io_operations) >= MAX_IO_OPERATIONS:
                break

            io_operations.append({
                "file": rel,
                "operation": operation,
            })

        if len(file_details) < MAX_FILE_DETAIL:
            file_details.append({
                "file": rel,
                "language": state.language,
                "functions": len(state.functions),
                "classes": len(state.classes),
                "loops": len(state.loops),
                "conditionals": state.conditionals,
                "calls": len(state.function_calls),
                "dependencies": len(set(state.dependencies)),
                "complexity": state.complexity or {},
                "failed": False,
            })

    for failure in failures:
        if len(file_details) >= MAX_FILE_DETAIL:
            break

        file_details.append({
            "file": failure["file"],
            "language": failure.get("language"),
            "failed": True,
            "error": failure.get("error"),
        })

    notes: list[str] = []

    if truncated_scan:
        notes.append(
            f"Scan capped at {len(states) + len(failures)} processed "
            f"files; at least {total_found} supported files were found"
        )

    if len(functions) >= MAX_FUNCTIONS:
        notes.append(f"Function list capped at {MAX_FUNCTIONS} entries")

    if len(classes) >= MAX_CLASSES:
        notes.append(f"Class list capped at {MAX_CLASSES} entries")

    if len(loops) >= MAX_LOOPS:
        notes.append(f"Loop list capped at {MAX_LOOPS} entries")

    if len(calls) >= MAX_CALLS:
        notes.append(f"Call list capped at {MAX_CALLS} entries")

    if len(io_operations) >= MAX_IO_OPERATIONS:
        notes.append(
            f"I/O operation list capped at {MAX_IO_OPERATIONS} entries"
        )

    if len(file_details) >= MAX_FILE_DETAIL:
        notes.append(
            f"File detail list capped at {MAX_FILE_DETAIL} entries"
        )

    if failures:
        notes.append(f"{len(failures)} file(s) could not be analyzed")

    if not states:
        notes.append("No file was parsed successfully")

    distinct_languages = list(languages.keys())

    return {
        "mode": "file" if root.is_file() else "folder",
        "language": (
            distinct_languages[0]
            if len(distinct_languages) == 1
            else "mixed"
            if distinct_languages
            else (
                None
                if language_filter == "auto"
                else language_filter
            )
        ),
        "language_filter": language_filter,
        "languages": dict(languages),
        "scan_path": str(root),
        "project_path": str(scan_root),
        "file_count": len(states) + len(failures),
        "analyzed_files": len(states),
        "failed_files": len(failures),
        "total_files_found": total_found,
        "total_lines": total_lines,
        "functions": functions,
        "classes": classes,
        "loops": loops,
        "conditionals": conditionals,
        "function_calls": calls,
        "io_operations": io_operations,
        "data_structures": sorted(data_structures),
        "dependencies": sorted(dependencies),
        "allocations": allocations,
        "complexity": {
            "measured": complexity_measured,
            "max": complexity_max,
            "total": complexity_total,
        },
        "files": file_details,
        "failures": failures,
        "notes": notes,
    }
