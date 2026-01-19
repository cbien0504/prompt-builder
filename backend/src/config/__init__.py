"""Configuration management for cursorlite."""

from .manager import (
    DEFAULT_CONFIG,
    DEFAULT_INCLUDE_PATTERNS,
    DEFAULT_EXCLUDE_PATTERNS,
    load_config,
    cfg_fingerprint,
    expand_pattern,
)

__all__ = [
    "DEFAULT_CONFIG",
    "DEFAULT_INCLUDE_PATTERNS",
    "DEFAULT_EXCLUDE_PATTERNS",
    "load_config",
    "cfg_fingerprint",
    "expand_pattern",
]
