"""Shared configuration for OASIS modules.

Loads environment variables from ``OASIS/.env`` (if present) and exposes
small typed accessors. This is the only place configuration is read from,
so modules never hardcode secrets or paths.

The parser is intentionally dependency-free: OASIS ships without
``python-dotenv`` and a .env file is a handful of ``KEY=value`` lines.
"""

from __future__ import annotations

import os
from pathlib import Path

OASIS_ROOT = Path(__file__).resolve().parent.parent

_ENV_FILE = OASIS_ROOT / ".env"
_loaded = False


def load_env(path: Path | None = None, override: bool = False) -> Path | None:
    """Populate ``os.environ`` from ``OASIS/.env``.

    Existing environment variables win unless ``override`` is True, so a
    value exported in the shell is never silently replaced by the file.

    Returns the path that was read, or None if no file exists.
    """
    global _loaded

    env_path = Path(path) if path is not None else _ENV_FILE
    if not env_path.exists():
        _loaded = True
        return None

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()

        # Strip one layer of matching quotes.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]

        if not key:
            continue
        if override or key not in os.environ:
            os.environ[key] = value

    _loaded = True
    return env_path


def _ensure_loaded() -> None:
    if not _loaded:
        load_env()


def get_env(name: str, default: str | None = None) -> str | None:
    """Read a string setting, treating blank values as absent."""
    _ensure_loaded()
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def get_env_first(names: list[str], default: str | None = None) -> str | None:
    """Return the first non-empty variable from ``names``."""
    for name in names:
        value = get_env(name)
        if value:
            return value
    return default


def get_env_int(name: str, default: int) -> int:
    value = get_env(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def get_env_float(name: str, default: float) -> float:
    value = get_env(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def get_env_bool(name: str, default: bool = False) -> bool:
    value = get_env(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def results_dir(subdir: str | None = None) -> Path:
    """Absolute path to ``OASIS/results`` (created on demand)."""
    path = OASIS_ROOT / "results"
    if subdir:
        path = path / subdir
    path.mkdir(parents=True, exist_ok=True)
    return path
