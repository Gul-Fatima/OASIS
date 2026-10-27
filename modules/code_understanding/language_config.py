"""Language-agnostic configuration system for OASIS.

Loads per-language JSON config files that define:
- Which tree-sitter node types map to which concepts
- File extensions and detection patterns
- AST navigation rules
- Formatting and analysis patterns

Adding a new language = adding one JSON file in configs/.
No Python code changes needed.

Based on: SMART-Dal/codegreen (MPL-2.0)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class LanguageConfig:
    """Configuration for a specific programming language."""

    name: str
    extensions: list[str]
    tree_sitter_name: str

    # AST structure
    ast_config: dict[str, Any] = field(default_factory=dict)

    # Node type mappings (the key part for language independence)
    node_types: dict[str, Any] = field(default_factory=dict)

    # Analysis patterns (fallback regex)
    analysis_patterns: dict[str, Any] = field(default_factory=dict)

    # Language detection patterns
    detection_patterns: dict[str, Any] = field(default_factory=dict)

    # Formatting rules
    formatting_config: dict[str, Any] = field(default_factory=dict)

    # Language-specific rules
    rules: dict[str, Any] = field(default_factory=dict)

    # Processing limits
    processing_limits: dict[str, Any] = field(default_factory=dict)

    # Query configuration
    query_config: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LanguageConfig:
        """Create from a dictionary, filtering out comment keys."""
        filtered = {k: v for k, v in data.items() if not k.startswith('_')}
        return cls(**{k: v for k, v in filtered.items() if k in cls.__dataclass_fields__})


class LanguageConfigManager:
    """Manages language configurations loaded from JSON files."""

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path(__file__).parent / "configs"
        self._configs: dict[str, LanguageConfig] = {}
        self._load_configs()

    def _load_configs(self):
        """Load all language configurations from JSON files."""
        if not self.config_dir.exists():
            return

        for config_file in self.config_dir.glob("*.json"):
            if config_file.name in ("TEMPLATE.json",):
                continue
            try:
                lang_id = config_file.stem
                with open(config_file, "r") as f:
                    data = json.load(f)
                self._configs[lang_id] = LanguageConfig.from_dict(data)
            except Exception as e:
                print(f"Warning: Failed to load config {config_file}: {e}")

    def get_config(self, language: str) -> Optional[LanguageConfig]:
        """Get configuration for a specific language."""
        return self._configs.get(language)

    def get_supported_languages(self) -> list[str]:
        """Get list of supported languages."""
        return list(self._configs.keys())

    def get_node_types(self, language: str) -> dict[str, Any]:
        """Get AST node type mappings for a language."""
        config = self.get_config(language)
        return config.node_types if config else {}

    def get_formatting_config(self, language: str) -> dict[str, Any]:
        """Get formatting configuration."""
        config = self.get_config(language)
        return config.formatting_config if config else {}

    def get_analysis_patterns(self, language: str) -> dict[str, Any]:
        """Get fallback regex analysis patterns."""
        config = self.get_config(language)
        return config.analysis_patterns if config else {}

    def detect_language_from_filename(self, filename: str) -> Optional[str]:
        """Detect language from file extension."""
        ext = Path(filename).suffix.lower()
        for language, config in self._configs.items():
            if ext in config.extensions:
                return language
        return None

    def detect_language_from_content(self, content: str) -> Optional[str]:
        """Detect language from file content using detection patterns."""
        for language, config in self._configs.items():
            patterns = config.detection_patterns
            if not patterns:
                continue
            for pattern_name, pattern in patterns.items():
                if isinstance(pattern, str) and pattern in content:
                    return language
                elif isinstance(pattern, list) and any(p in content for p in pattern):
                    return language
                elif isinstance(pattern, dict) and 'regex' in pattern:
                    if re.search(pattern['regex'], content):
                        return language
        return None

    def get_supported_extensions(self) -> list[str]:
        """Get all supported file extensions."""
        extensions = []
        for config in self._configs.values():
            extensions.extend(config.extensions)
        return list(set(extensions))


# Singleton
_manager: Optional[LanguageConfigManager] = None


def get_language_config_manager() -> LanguageConfigManager:
    """Get the global language configuration manager."""
    global _manager
    if _manager is None:
        _manager = LanguageConfigManager()
    return _manager
