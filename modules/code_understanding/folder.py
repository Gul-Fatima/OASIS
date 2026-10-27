"""Folder-level code understanding.

Parses every supported source file under a directory and merges the
per-file :class:`CodeState` objects into a single project-level summary.
A single file path is also accepted, in which case only that file is
scanned.

Files that fail to parse (syntax errors, decoding errors, oversized
files) are recorded as failures and skipped instead of aborting the
whole run — one broken file must not invalidate a project scan.

``analyze_folder`` is a generator so the API layer can stream progress
events (SSE) and the dashboard can render a live progress bar. Static
parsing of a large project is slow enough that silence looks like a hang.

This module makes no energy claims.
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

# Directories that never hold first-party source worth analyzing.
IGNORED_DIRECTORIES = frozenset({
    ".git", ".hg", ".svn", ".idea", ".vscode", ".vs",
    "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", ".tox", ".nox", ".venv", "venv", "env", "virtualenv",
    "site-packages", "dist", "build", "target", "out", "vendor",
    ".next", ".gradle", ".terraform", "coverage", "htmlcov",
})

# Skip minified bundles / generated blobs.
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_FILES = 1000

# Payload caps: a whole-project scan can produce tens of thousands of
# entries while the dashboard only ever shows summaries.
MAX_FUNCTIONS = 2000
MAX_CLASSES = 1000
MAX_LOOPS = 2000
MAX_CALLS = 500
MAX_IO_OPERATIONS = 200
MAX_FILE_DETAIL = 500


# ============================================================
# DISCOVERY
# ============================================================

def discover_source_files(
    root: Path,
    language: str = "auto",
    max_files: int = MAX_FILES,
    recursive: bool = True,
) -> tuple[list[tuple[Path, str]], int]:
    """Return ``((path, language) pairs, total_supported_found)``.

    ``language`` may be a concrete language (only files of that language
    are kept) or ``"auto"`` (every file whose extension maps to a
    language with an installed adapter).
    """
    manager = get_language_config_manager()
    found: list[tuple[Path, str]] = []

    def consider(file_path: Path) -> None:
        detected = None if language == "auto" else language
        if detected is None:
            detected = manager.detect_language_from_filename(str(file_path))
        if detected is None or detected not in ADAPTERS:
            return
        if language != "auto" and detected != language:
            return
        found.append((file_path, detected))

    if root.is_file():
        consider(root)
    elif recursive:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(
                name for name in dirnames
                if name not in IGNORED_DIRECTORIES and not name.startswith(".")
            )
            for name in sorted(filenames):
                consider(Path(dirpath) / name)
    else:
        for entry in sorted(root.iterdir()):
            if entry.is_file():
                consider(entry)

    found.sort(key=lambda item: str(item[0]).lower())
    return found[:max_files], len(found)


def relative_name(path: Path, root: Path) -> str:
    """Path relative to ``root`` with forward slashes, for display."""
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


# ============================================================
# SINGLE FILE
# ============================================================

def analyze_file(
    file_path: Path,
    language: str,
) -> tuple[Optional[CodeState], Optional[str], int]:
    """Parse one file. Returns ``(state, error, line_count)``."""
    try:
        size = file_path.stat().st_size
    except OSError as exc:
        return None, f"cannot read file: {exc}", 0

    if size > MAX_FILE_BYTES:
        return None, f"skipped: file larger than {MAX_FILE_BYTES} bytes", 0

    try:
        source = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return None, f"cannot read file: {exc}", 0
    except OSError as exc:
        return None, f"cannot read file: {exc}", 0

    line_count = len(source.splitlines())
    try:
        state = parse_code(source, path=str(file_path), language=language)
    except ValueError as exc:
        return None, str(exc), line_count
    return state, None, line_count


# ============================================================
# FOLDER SCAN (generator: progress events, then the result)
# ============================================================

def analyze_folder(
    root: str | Path,
    language: str = "auto",
    max_files: int = MAX_FILES,
    recursive: bool = True,
) -> Iterator[dict]:
    """Walk ``root``, parse every supported file, and yield events.

    Yields progress dicts (``{"type": "progress", ...}``) per discovered
    file, then exactly one result event (``{"type": "result", ...}``).
    """
    root = Path(root)

    if not root.exists():
        raise FileNotFoundError(f"Path not found: {root}")

    files, total_found = discover_source_files(
        root, language, max_files, recursive
    )

    total = len(files)
    truncated_scan = total_found > total

    yield {
        "type": "progress",
        "stage": "discover",
        "percent": 2.0,
        "current": 0,
        "total": total,
        "message": (
            f"Discovered {total_found} supported source file(s)"
            + (f" — scanning first {total}" if truncated_scan else "")
        ),
    }

    scan_root = root if root.is_dir() else root.parent
    states: list[tuple[str, CodeState]] = []
    failures: list[dict] = []
    total_lines = 0

    for index, (file_path, detected) in enumerate(files, start=1):
        rel = relative_name(file_path, root)

        # Emitted *before* parsing so the dashboard names the file that
        # is currently being worked on rather than the previous one.
        yield {
            "type": "progress",
            "stage": "parse",
            "percent": round(3 + ((index - 1) / total) * 92, 1) if total else 95.0,
            "current": index - 1,
            "total": total,
            "file": rel,
            "language": detected,
            "message": f"Parsing {rel} ({index}/{total})",
        }

        state, error, line_count = analyze_file(file_path, detected)
        if state is None:
            failures.append({"file": rel, "language": detected, "error": error})
        else:
            states.append((rel, state))
            total_lines += line_count

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
    yield {"type": "result", "result": result}


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
    """Merge per-file CodeStates into one project-level summary."""
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

        cx = state.complexity or {}
        if cx:
            complexity_measured += int(cx.get("measured", 0))
            complexity_total += int(cx.get("total", 0))
            complexity_max = max(complexity_max, int(cx.get("max", 0)))

        for function in state.functions:
            if len(functions) < MAX_FUNCTIONS:
                entry = asdict(function)
                entry["file"] = rel
                entry["language"] = state.language
                functions.append(entry)
        for klass in state.classes:
            if len(classes) < MAX_CLASSES:
                entry = asdict(klass)
                entry["file"] = rel
                entry["language"] = state.language
                classes.append(entry)
        for loop in state.loops:
            if len(loops) < MAX_LOOPS:
                entry = asdict(loop)
                entry["file"] = rel
                loops.append(entry)
        for call in state.function_calls:
            if len(calls) < MAX_CALLS:
                entry = asdict(call)
                entry["file"] = rel
                calls.append(entry)
        for operation in state.io_operations:
            if len(io_operations) < MAX_IO_OPERATIONS:
                io_operations.append({"file": rel, "operation": operation})

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
        if len(file_details) < MAX_FILE_DETAIL:
            file_details.append({
                "file": failure["file"],
                "language": failure.get("language"),
                "failed": True,
                "error": failure.get("error"),
            })

    notes: list[str] = []
    if truncated_scan:
        notes.append(f"Scan capped at {len(states) + len(failures)} of {total_found} files")
    if len(functions) >= MAX_FUNCTIONS:
        notes.append(f"Function list truncated to {MAX_FUNCTIONS} entries")
    if len(calls) >= MAX_CALLS:
        notes.append(f"Call list truncated to {MAX_CALLS} entries")
    if failures:
        notes.append(f"{len(failures)} file(s) could not be parsed")
    if not states:
        notes.append("No file was parsed successfully")

    distinct_languages = list(languages.keys())
    mode = "file" if root.is_file() else "folder"

    return {
        "mode": mode,
        "language": (
            distinct_languages[0] if len(distinct_languages) == 1
            else "mixed" if distinct_languages
            else (None if language_filter == "auto" else language_filter)
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
