"""Small, conservative helpers for keeping local details out of shareable artifacts."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse, urlunparse

_REDACTION_PATTERNS = (
    # Common credential formats and high-signal assignment forms. This is a
    # guardrail, not a replacement for deliberate review of selected sources.
    (re.compile(r"\b(?:sk|rk|pk)-[A-Za-z0-9_-]{16,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
    (
        re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/-]{12,}"),
        r"\1[REDACTED_TOKEN]",
    ),
    (
        re.compile(r"(?i)\b(password|secret|token|api[_-]?key)\s*[:=]\s*[^\s'\"]+"),
        r"\1=[REDACTED]",
    ),
)


def redact_sensitive_text(text: str) -> str:
    """Remove common credentials before source text crosses the model boundary."""
    for pattern, replacement in _REDACTION_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def local_path_label(path: Path | str) -> str:
    """Return a shareable label without an absolute local path."""
    name = Path(path).name or "local source"
    return f"local file: {name}"


def repository_label(path: Path) -> str:
    """Return a shareable local repository label."""
    return f"local repository: {path.name or 'project'}"


def reference_label(reference: str) -> str:
    """Drop local path details and URL query/fragment values from reports."""
    parsed = urlparse(reference)
    if parsed.scheme in {"http", "https"}:
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
    return local_path_label(reference)
